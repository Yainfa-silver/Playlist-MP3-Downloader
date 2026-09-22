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
import hashlib
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
    + "%(info.title)s" + SEP
    + "%(info.playlist_index)s" + SEP
    + "%(info.playlist_count)s"
)
# Extensiones de archivos multimedia que pueden quedar en la carpeta del job
# (ej. descarga OK pero conversión a MP3 fallida -> queda .m4a/.webm).
MEDIA_EXTS = {
    ".mp3", ".mp4", ".opus", ".flac", ".m4a",
    ".webm", ".ogg", ".aac", ".wav", ".mka",
}

COOKIES_FILE = DATA_DIR / "cookies.txt"

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))

JOBS = {}
JOBS_LOCK = threading.Lock()


def ytdlp_exe():
    if os.name == "nt":
        return BIN_DIR / "yt-dlp.exe"
    path = shutil.which("yt-dlp")
    if path:
        return Path(path)
    return Path(sys.executable).parent / "yt-dlp"


def ffmpeg_exe():
    if os.name == "nt":
        return BIN_DIR / "ffmpeg.exe"
    return Path(shutil.which("ffmpeg") or "")


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
    if os.name != "nt":
        return
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
    fields = line[len(PROG_PREFIX):].split(SEP, 8)
    if len(fields) < 7:
        return
    status = fields[0]
    title = fields[6]
    playlist_index = _num(fields[7]) if len(fields) > 7 else None
    playlist_count = _num(fields[8]) if len(fields) > 8 else None
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
        if playlist_count:
            job["total"] = int(playlist_count)
        if playlist_index:
            job["current_index"] = int(playlist_index)
    elif status == "finished":
        job.update({"status": "converting", "current": title})
        job["ok_count"] = job.get("ok_count", 0) + 1


MAX_ATTEMPTS = 3
RETRY_PAUSE = 30


def _build_cmd(url, fmt, quality, audio_quality, job_dir):
    cmd = [
        str(ytdlp_exe()),
        "--newline",
        "--ignore-errors",
        "--retries", "10",
        "--retry-sleep", "linear=1:5",
        "--socket-timeout", "30",
        "--fragment-retries", "10",
        "--windows-filenames",
    ]
    ffmpeg_path = ffmpeg_exe()
    if ffmpeg_path.exists():
        cmd += ["--ffmpeg-location", str(ffmpeg_path.parent)]
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
    cookies_file = COOKIES_FILE
    if cookies_file.exists():
        cmd += ["--cookies", str(cookies_file)]
    cookies_browser = os.environ.get("COOKIES_BROWSER", "").strip()
    if cookies_browser:
        cmd += ["--cookies-from-browser", cookies_browser]
    cmd += ["-o", str(job_dir / "%(playlist_index&{} - |)s%(title)s.%(ext)s"), url]
    return cmd


def _run_pass(job, cmd):
    """Ejecuta una pasada de yt-dlp y devuelve (errores, codigo_salida)."""
    errors = []
    # Los contadores de fallos reflejan SIEMPRE la última pasada.
    job["failed_count"] = 0
    job["failed"] = []
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        for line in proc.stdout:
            line = line.rstrip("\r\n")
            parse_progress_line(job, line)
            if line.startswith("[download] Destination:"):
                job["started_count"] = job.get("started_count", 0) + 1
            elif line.startswith("ERROR:"):
                err = line[len("ERROR:"):].strip()
                errors.append(err)
                errors = errors[-200:]
                job["failed_count"] = job.get("failed_count", 0) + 1
                title = job.get("current") or "desconocida"
                failed = job.setdefault("failed", [])
                failed.append({"title": title, "error": err})
                job["failed"] = failed[-200:]
        rc = proc.wait()
    except Exception as e:
        errors.append("excepción: {}".format(e))
        rc = -1
    return errors, rc


def _collect_files(job_dir, fmt):
    """Archivos del formato pedido + posibles archivos de audio que
    quedaron sin convertir (ej. la descarga funcionó pero ffmpeg falló)."""
    files = sorted(job_dir.glob("*.{}".format(fmt)))
    if fmt != "mp4":
        leftovers = sorted(
            p for p in job_dir.iterdir()
            if p.is_file()
            and p.suffix.lower() in MEDIA_EXTS
            and p.suffix.lower() != "." + fmt
        )
        files += leftovers
    return sorted(set(files))


def run_download(job_id, url, fmt, quality, audio_quality):
    job = JOBS[job_id]
    # Carpeta persistente por URL: si se reintenta la misma playlist,
    # yt-dlp salta lo que ya está descargado y baja solo lo que falta.
    job_dir = DOWNLOADS_DIR / job.get("dir_id", job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    cmd = _build_cmd(url, fmt, quality, audio_quality, job_dir)

    job["attempts"] = 1
    job["attempts_used"] = 0
    all_errors = []
    try:
        while True:
            job["status"] = "extracting" if job["attempts"] == 1 else "retrying"
            job["attempt"] = job["attempts"]
            pass_errors, _rc = _run_pass(job, cmd)
            all_errors += pass_errors

            files = _collect_files(job_dir, fmt)
            expected = job.get("total") or 0
            still_missing = (expected - len(files)) if (expected and expected > len(files)) else 0
            should_retry = (job.get("failed_count") or 0) > 0 or still_missing > 0

            job["attempts_used"] = job["attempts"]
            if not should_retry or job["attempts"] >= MAX_ATTEMPTS:
                break

            job["attempts"] += 1
            job["status"] = "retrying"
            job["current"] = "Pausa de {}s antes del reintento {}/{}...".format(
                RETRY_PAUSE, job["attempts"], MAX_ATTEMPTS)
            time.sleep(RETRY_PAUSE)
            job["status"] = "retrying"

        files = _collect_files(job_dir, fmt)
        if files:
            job.update({
                "status": "done",
                "percent": 100,
                "downloaded": len(files),
                "files": [f.name for f in files],
            })
        else:
            msg = "No se descargó ningún archivo"
            if all_errors:
                msg += ": " + " | ".join(all_errors[-3:])
            job.update({"status": "error", "error": msg})
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
    dir_id = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "dir_id": dir_id,
            "status": "queued",
            "percent": 0,
            "url": url,
            "format": fmt,
            "quality": quality,
            "audio_quality": audio_quality,
            "files": [],
            "total": 0,
            "downloaded": 0,
            "current": "",
            "current_index": None,
            "started_count": 0,
            "ok_count": 0,
            "failed_count": 0,
            "failed": [],
            "attempts": 0,
            "attempts_used": 0,
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


@app.route("/api/cookies", methods=["GET", "POST"])
def api_cookies():
    if request.method == "GET":
        return jsonify({"enabled": COOKIES_FILE.exists()})
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "No se recibió ningún archivo"}), 400
    data = f.read()
    if not data:
        return jsonify({"error": "El archivo está vacío"}), 400
    COOKIES_FILE.write_bytes(data)
    return jsonify({"ok": True, "filename": f.filename})


@app.route("/api/zip/<job_id>")
def api_zip(job_id):
    job = JOBS.get(job_id)
    dir_id = (job and job.get("dir_id")) or job_id
    job_dir = DOWNLOADS_DIR / dir_id
    if not job_dir.exists():
        return jsonify({"error": "No encontrado"}), 404
    media_files = sorted(
        p for p in job_dir.iterdir()
        if p.is_file() and p.suffix.lower() in MEDIA_EXTS
    )
    if not media_files:
        return jsonify({"error": "Sin archivos"}), 404

    zip_path = DOWNLOADS_DIR / f"{dir_id}.zip"
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", job_dir)
    return send_from_directory(DOWNLOADS_DIR, f"{dir_id}.zip", as_attachment=True)


@app.route("/api/file/<job_id>/<path:filename>")
def api_file(job_id, filename):
    job = JOBS.get(job_id)
    dir_id = (job and job.get("dir_id")) or job_id
    job_dir = DOWNLOADS_DIR / dir_id
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
