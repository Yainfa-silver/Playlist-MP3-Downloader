# Playlist MP3 Downloader

App de escritorio para descargar playlists de YouTube en MP3.

## Uso (versión compilada)

1. Ejecuta `dist\PlaylistMP3Downloader.exe` con doble clic.
2. La primera vez descarga automáticamente lo que necesita (`yt-dlp.exe` y `ffmpeg.exe`, ~160 MB) en `%LOCALAPPDATA%\PlaylistMP3Downloader`.
3. Se abre el navegador en http://127.0.0.1:5000.
4. Pega la URL de una playlist y descarga cada MP3 o todo como ZIP.
5. Para cerrar: icono en la bandeja del sistema > `Salir`.

## Ejecutar desde código fuente

Requisitos: Python 3.9+.

```bash
pip install -r requirements.txt
python main.py
```

## Compilar el .exe

```bash
powershell -ExecutionPolicy Bypass -File build.ps1
```

El ejecutable queda en `dist\PlaylistMP3Downloader.exe`.

## Opciones

- Si YouTube bloquea con 403, activa las cookies del navegador (debes haber iniciado sesión en YouTube ahí). Para la versión compilada, define la variable de entorno `COOKIES_BROWSER` (ej. `chrome`, `edge`, `firefox`) antes de abrir el .exe.

> Nota: descarga solo contenido permitido por los términos de YouTube.
# playlist-mp3-converter
