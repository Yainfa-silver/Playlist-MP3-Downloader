import os
import sys
import time
import re
import shutil
import subprocess
import threading
import uuid
import urllib.request
import zipfile
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, render_template

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent

if os.environ.get("LOCALAPPDATA"):
    DATA_DIR = Path(os.environ["LOCALAPPDATA"]) / "PlaylistMP3Downloader"
else:
    DATA_DIR = Path.home() / ".playlistmp3downloader"

BIN_DIR = DATA_DIR / "bin"
DOWNLOADS_DIR = DATA_DIR / "downloads"
DATA_DIR.mkdir(exist_ok=True)
BIN_DIR.mkdir(exist_ok=True)
DOWNLOADS_DIR.mkdir(exist_ok=True)

YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-lgpl.zip"

PROG_PREFIX = "@@PROG@@"
SEP = "\x1f"
DOWNLOAD_TEMPLATE = (
    "download:" + PROG_PREFIX
    + "%(progress.status)s" + SEP
    + "%(progress.downloaded_bytes)s" + SEP
    + "%(progress.total_bytes)s" + SEP
    + "%(progress.total_bytes_estimate)s" + SEP
    + "%(progress.speed)s" + SEP
    + "%(progress.eta)s" + SEP
    + "%(info.title)s"
)

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))

JOBS = {}
JOBS_LOCK = threading.Lock()


def ytdlp_exe():
    return BIN_DIR / "yt-dlp.exe"


def ffmpeg_exe():
    return BIN_DIR / "ffmpeg.exe"


def download_file(url, dest, progress_cb=None):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    tmp = str(dest) + ".part"
    with urllib.request.urlopen(req, timeout=180) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(tmp, "wb") as f:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)
    os.replace(tmp, dest)


def ensure_ffmpeg(progress_cb=None):
    exe = ffmpeg_exe()
    if exe.exists():
        return exe
    zip_path = BIN_DIR / "ffmpeg.zip"
    download_file(FFMPEG_URL, zip_path, progress_cb)
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.replace("\\", "/").endswith("/bin/ffmpeg.exe"):
                with zf.open(name) as src, open(exe, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                break
    zip_path.unlink(missing_ok=True)
    return exe


def ensure_binaries(progress_cb=None):
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    if not ytdlp_exe().exists():
        download_file(
            YTDLP_URL, ytdlp_exe(),
            lambda d, t: progress_cb and progress_cb(d, t, "Descargando yt-dlp"),
        )
    if not ffmpeg_exe().exists():
        ensure_ffmpeg(
            lambda d, t: progress_cb and progress_cb(d, t, "Descargando ffmpeg"),
        )


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def parse_progress_line(job, line):
    if not line.startswith(PROG_PREFIX):
        return
    fields = line[len(PROG_PREFIX):].split(SEP, 6)
    if len(fields) < 7:
        return
    status = fields[0]
    title = fields[6]
    if status == "downloading":
        downloaded = _num(fields[1]) or 0
        total = _num(fields[2]) or _num(fields[3]) or 0
        pct = (downloaded / total * 100) if total else 0
        job.update({
            "status": "downloading",
            "percent": round(pct, 1),
            "current": title,
            "speed": _num(fields[4]),
            "eta": _num(fields[5]),
        })
    elif status == "finished":
        job.update({"status": "converting", "current": title})


def run_download(job_id, url, fmt, quality, audio_quality):
    job = JOBS[job_id]
    job["status"] = "extracting"
    job_dir = DOWNLOADS_DIR / job_id
    job_dir.mkdir(exist_ok=True)

    cmd = [
        str(ytdlp_exe()),
        "--newline",
        "--ignore-errors",
        "--retries", "3",
        "--windows-filenames",
        "--ffmpeg-location", str(BIN_DIR),
    ]
    if fmt == "mp4":
        if not quality or quality == "best":
            fsel = "bestvideo+bestaudio/best"
        else:
            fsel = "bestvideo[height<={}]+bestaudio/best[height<={}]/best".format(quality, quality)
        cmd += ["-f", fsel, "--merge-output-format", "mp4"]
    else:
        cmd += [
            "-f", "bestaudio/best",
            "-x", "--audio-format", fmt,
        ]
        if fmt != "flac":
            cmd += ["--audio-quality", audio_quality]
    cmd += [
        "--progress-template", DOWNLOAD_TEMPLATE,
        "--extractor-args",
        "youtube:player_client=tv,web_embedded,web_safari,android,ios,web",
    ]
    cookies_browser = os.environ.get("COOKIES_BROWSER", "").strip()
    if cookies_browser:
        cmd += ["--cookies-from-browser", cookies_browser]
    cmd += ["-o", str(job_dir / "%(playlist_index&{} - |)s%(title)s.%(ext)s"), url]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for line in proc.stdout:
            parse_progress_line(job, line.rstrip("\r\n"))
        proc.wait()

        ext = fmt
        files = sorted(job_dir.glob("*.{}".format(ext)))
        if files:
            job.update({
                "status": "done",
                "percent": 100,
                "total": len(files),
                "files": [f.name for f in files],
            })
        else:
            job.update({"status": "error", "error": "No se descargó ningún archivo"})
    except Exception as e:
        job.update({"status": "error", "error": str(e)})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "URL vacía"}), 400
    if not re.match(r"https?://", url):
        return jsonify({"error": "URL inválida"}), 400

    fmt = (data.get("format") or "mp3").strip().lower()
    if fmt not in ("mp3", "mp4", "opus", "flac"):
        fmt = "mp3"
    quality = (data.get("quality") or "").strip() or "best"
    audio_quality = (data.get("audio_quality") or "").strip() or "192"
    if audio_quality not in ("128", "192", "256", "320"):
        audio_quality = "192"

    job_id = uuid.uuid4().hex
    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "status": "queued",
            "percent": 0,
            "url": url,
            "format": fmt,
            "quality": quality,
            "audio_quality": audio_quality,
            "files": [],
            "total": 0,
            "current": "",
            "error": None,
        }
    threading.Thread(target=run_download, args=(job_id, url, fmt, quality, audio_quality), daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def api_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job no encontrado"}), 404
    return jsonify(job)


@app.route("/api/zip/<job_id>")
def api_zip(job_id):
    job_dir = DOWNLOADS_DIR / job_id
    if not job_dir.exists():
        return jsonify({"error": "No encontrado"}), 404
    mp3_files = sorted(job_dir.glob("*.mp3"))
    mp4_files = sorted(job_dir.glob("*.mp4"))
    opus_files = sorted(job_dir.glob("*.opus"))
    flac_files = sorted(job_dir.glob("*.flac"))
    if not mp3_files and not mp4_files and not opus_files and not flac_files:
        return jsonify({"error": "Sin archivos"}), 404

    zip_path = DOWNLOADS_DIR / f"{job_id}.zip"
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", job_dir)
    return send_from_directory(DOWNLOADS_DIR, f"{job_id}.zip", as_attachment=True)


@app.route("/api/file/<job_id>/<path:filename>")
def api_file(job_id, filename):
    job_dir = DOWNLOADS_DIR / job_id
    return send_from_directory(job_dir, filename, as_attachment=True)


@app.route("/api/shutdown", methods=["POST"])
def api_shutdown():
    def _exit():
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=_exit, daemon=True).start()
    return jsonify({"ok": True})


if __name__ == "__main__":
    ensure_binaries()
    app.run(debug=True, host="127.0.0.1", port=5000)
