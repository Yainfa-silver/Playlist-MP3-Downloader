import os
import sys
import socket
import time
import threading
import webbrowser
import subprocess
import urllib.request

from app import (
    app, DATA_DIR, BIN_DIR, DOWNLOADS_DIR,
    ensure_binaries, ytdlp_exe, ffmpeg_exe,
)

import pystray
from PIL import Image, ImageDraw

HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}"


def make_icon():
    img = Image.new("RGB", (64, 64), (255, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(24, 16), (24, 48), (50, 32)], fill="white")
    return img


def port_in_use(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((HOST, port))
        s.close()
        return False
    except OSError:
        return True


def find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, 0))
    p = s.getsockname()[1]
    s.close()
    return p


def run_setup_window():
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("Playlist MP3 Downloader")
    root.geometry("440x130")
    root.resizable(False, False)
    tk.Label(root, text="Preparando el primer arranque...",
             font=("Segoe UI", 11)).pack(pady=(16, 4))
    bar = ttk.Progressbar(root, mode="determinate", maximum=100)
    bar.pack(fill="x", padx=20, pady=8)
    detail = tk.Label(root, text="", fg="#666666")
    detail.pack()

    state = {"pct": 0, "msg": "", "err": None, "done": False}

    def progress_cb(done, total, label):
        state["pct"] = int(done / total * 100) if total else 0
        state["msg"] = "{}: {} MB / {} MB".format(
            label, done // (1024 * 1024), total // (1024 * 1024))

    def worker():
        try:
            ensure_binaries(progress_cb)
        except Exception as e:
            state["err"] = str(e)
        state["done"] = True

    threading.Thread(target=worker, daemon=True).start()

    def poll():
        bar["value"] = state["pct"]
        detail.config(text=state.get("msg", ""))
        if state["done"]:
            root.destroy()
        else:
            root.after(100, poll)

    root.after(100, poll)
    root.mainloop()

    if state["err"]:
        import tkinter.messagebox as mb
        r = tk.Tk()
        r.withdraw()
        mb.showerror("Error", state["err"])
        r.destroy()
        sys.exit(1)


def wait_for_server():
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://{HOST}:{PORT}", timeout=1)
            return
        except Exception:
            time.sleep(0.2)


def run_tray():
    def open_web(icon, item):
        webbrowser.open(URL)

    def open_folder(icon, item):
        os.startfile(str(DOWNLOADS_DIR))

    def update_ytdlp(icon, item):
        subprocess.run(
            [str(ytdlp_exe()), "-U"],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        icon.notify("yt-dlp actualizado")

    def quit_app(icon, item):
        icon.stop()
        os._exit(0)

    icon = pystray.Icon(
        "playlist_mp3_downloader",
        make_icon(),
        "Playlist MP3 Downloader",
        menu=pystray.Menu(
            pystray.MenuItem("Abrir web", open_web, default=True),
            pystray.MenuItem("Abrir carpeta de descargas", open_folder),
            pystray.MenuItem("Actualizar yt-dlp", update_ytdlp),
            pystray.MenuItem("Salir", quit_app),
        ),
    )
    icon.run()


def main():
    global URL, PORT
    if port_in_use(PORT):
        PORT = find_free_port()
    URL = f"http://{HOST}:{PORT}"

    if not ytdlp_exe().exists() or not ffmpeg_exe().exists():
        run_setup_window()

    threading.Thread(
        target=lambda: app.run(host=HOST, port=PORT, debug=False,
                               use_reloader=False, threaded=True),
        daemon=True,
    ).start()

    wait_for_server()
    webbrowser.open(URL)
    run_tray()


if __name__ == "__main__":
    main()
