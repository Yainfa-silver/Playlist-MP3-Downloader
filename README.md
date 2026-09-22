# Playlist MP3 Downloader

Aplicación de escritorio **open source** para descargar playlists de YouTube en **MP3** o **MP4**, con control total sobre la calidad de audio y video.

Desarrollada en Python, se ejecuta localmente y ofrece una interfaz web ligera y un icono en la bandeja del sistema. Está pensada para que cualquier persona pueda usarla, modificarla y distribuirla libremente.

---

## Características

- 🎵 **Descarga en MP3** con calidad configurable (128, 192, 256 o 320 kbps).
- 🎬 **Descarga en MP4** con calidad de video configurable (360p hasta 4K, o "mejor calidad").
- 📃 **Soporte de playlists completas** de YouTube.
- 📦 **Descarga individual** de cada archivo o todo en un **ZIP**.
- ⏱️ **Barra de progreso en tiempo real** (velocidad, porcentaje y ETA).
- 📊 **Resumen final con fallos**: muestra cuántas canciones se descargaron, cuántas faltaron y el motivo de cada fallo.
- 🔁 **Reintentos automáticos**: si quedan canciones sin bajar, la app espera y vuelve a intentarlo hasta 3 veces.
- 📂 **Descarga reanudable**: cada playlist se guarda en su propia carpeta; si pulsas *Descargar* de nuevo, solo baja las canciones que faltan.
- 🍪 **Subida de `cookies.txt` desde la interfaz** para evitar bloqueos de YouTube en playlists grandes.
- 🖥️ **Interfaz web local** con diseño oscuro moderno.
- 📥 **Instalación automática** de dependencias (`yt-dlp` y `ffmpeg`) en el primer arranque.
- 🔁 **Actualización de `yt-dlp`** desde la bandeja del sistema.
- 🔒 **Procesamiento 100 % local**: tus URLs y archivos no salen de tu equipo.

---

## Cómo funciona

La aplicación levanta un pequeño servidor web local (`http://127.0.0.1:5000`) y delega la descarga en [`yt-dlp`](https://github.com/yt-dlp/yt-dlp), que se encarga de extraer y descargar el contenido de YouTube. [`ffmpeg`](https://ffmpeg.org/) se usa para convertir el audio a MP3 y para combinar las pistas de audio y video en un único archivo MP4.

```
Tu navegador  ──►  Flask (servidor local)  ──►  yt-dlp  ──►  ffmpeg  ──►  MP3 / MP4
```

---

## Requisitos

### Versión compilada (Windows)

Ninguno. Solo descarga y ejecuta el `.exe`.

### Ejecución desde el código fuente

- **Python 3.9+**
- **Windows** (la app usa APIs específicas de Windows para la bandeja del sistema)
- Conexión a internet la primera vez (para descargar `yt-dlp` y `ffmpeg`)

```bash
pip install -r requirements.txt
```

---

## Instalación y uso

### Opción A — Ejecutable compilado

1. Descarga el archivo `dist\PlaylistMP3Downloader.exe`.
2. Haz doble clic para abrirlo.
3. La primera vez descargará automáticamente lo necesario (`yt-dlp.exe` y `ffmpeg.exe`, ~160 MB) en `%LOCALAPPDATA%\PlaylistMP3Downloader`.
4. Se abrirá tu navegador en `http://127.0.0.1:5000`.
5. Pega la URL de una playlist, elige formato y calidad, y pulsa **Descargar**.
6. Para cerrar: icono en la bandeja del sistema → **Salir**.

### Opción B — Desde el código fuente

```bash
git clone <url-del-repositorio>
cd playlist-mp3-converter
pip install -r requirements.txt
python main.py
```

---

## Uso de la interfaz

1. **URL**: pega el enlace de una playlist de YouTube (ej. `https://www.youtube.com/playlist?list=...`).
2. **Formato**: elige entre `MP3 (solo audio)` o `MP4 (video)`.
3. **Calidad**:
   - En MP3: bitrate de audio (128, 192, 256 o 320 kbps).
   - En MP4: resolución de video (360p, 480p, 720p, 1080p, 2K, 4K o "Mejor calidad").
4. Pulsa **Descargar** y observa el progreso en tiempo real.
5. Al terminar podrás descargar cada archivo por separado o **todos juntos en un ZIP**.

---

## Compilar el ejecutable

Genera el `.exe` con [PyInstaller](https://pyinstaller.org/):

```bash
powershell -ExecutionPolicy Bypass -File build.ps1
```

El ejecutable se genera en `dist\PlaylistMP3Downloader.exe`.

---

## Configuración

### Cookies del navegador (evita el error 403)

Si YouTube bloquea las descargas con un error `403` o faltan canciones en medio de una playlist larga, activa el uso de cookies (debes haber iniciado sesión en YouTube para poder exportarlas):

- **Desde la interfaz web (recomendado)**: exporta tus cookies en formato Netscape con una extensión como *Get cookies.txt LOCALLY* (para Chrome/Firefox/Edge) y sube el archivo `cookies.txt` desde el botón **"Subir cookies.txt"** de la app. Las cookies se guardan en `%LOCALAPPDATA%\PlaylistMP3Downloader\cookies.txt` (Windows) o `~/.playlistmp3downloader/cookies.txt` (Linux/macOS).

- **Con variable de entorno `COOKIES_BROWSER`** (usa las cookies de tu navegador directamente):

  - **Versión compilada**:

    ```powershell
    $env:COOKIES_BROWSER = "chrome"   # o "edge", "firefox", "brave", etc.
    .\PlaylistMP3Downloader.exe
    ```

  - **Desde código fuente**:

    ```powershell
    $env:COOKIES_BROWSER = "chrome"
    python main.py
    ```

> ⚠️ Las cookies caducan: si vuelven a faltar canciones, vuelve a exportarlas y súbelas de nuevo.

### ¿Por qué faltan canciones en playlists grandes?

YouTube limita las descargas sin sesión. Después de un número de canciones (a veces ~100-200), empieza a devolver errores (`403`, *"Sign in to confirm you're not a bot"*, etc.). La app **salta esas canciones y sigue con el resto** (para no abortar toda la playlist), y ahora te muestra exactamente **qué canciones fallaron y por qué** en el resumen final. Con cookies subidas e iniciando sesión, la práctica totalidad de esos fallos desaparece.

---

## Estructura del proyecto

```
├── app.py              # Servidor Flask y lógica de descarga
├── main.py             # Bandeja del sistema y arranque de la app
├── templates/
│   └── index.html      # Interfaz web
├── requirements.txt    # Dependencias de Python
├── build.ps1           # Script para compilar el .exe
└── README.md
```

---

## Licencia

Este proyecto es **software libre y de código abierto**. Puedes usarlo, estudiarlo, modificarlo y redistribuirlo libremente, siempre que respetes las licencias de las herramientas que utiliza (`yt-dlp` y `ffmpeg`).

---

## Contribuir

¡Las contribuciones son bienvenidas! Puedes:

1. Hacer un **fork** del repositorio.
2. Crear una rama para tu función o corrección: `git checkout -b mi-cambio`.
3. Realizar tus cambios y hacer **commit**.
4. Abrir un **Pull Request** describiendo qué hiciste.

También puedes abrir **issues** para reportar errores o proponer mejoras.

---

## Agradecimientos

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — motor de descarga.
- [ffmpeg](https://ffmpeg.org/) — conversión y combinación de audio/video.
- [Flask](https://flask.palletsprojects.com/) — servidor web local.
- [pystray](https://github.com/moses-palmer/pystray) — icono en la bandeja del sistema.

---

## Aviso legal

> Esta aplicación se distribuye únicamente con fines educativos y de uso personal. El usuario es responsable de descargar únicamente contenido del que posea los derechos o que esté permitido por los términos de servicio de YouTube. Los autores de este software no se hacen responsables del uso que se le dé a la aplicación.
