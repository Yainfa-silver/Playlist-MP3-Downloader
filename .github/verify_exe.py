"""Verifica que el .exe compilado contiene la interfaz con las opciones
de Formato y Calidad de audio. Sale con código != 0 si algo falla."""
import subprocess
import sys
from pathlib import Path

EXE = Path("dist/PlaylistMP3Downloader.exe")


def shell(cmd, stdin=None):
    return subprocess.run(
        cmd, capture_output=True, text=True,
        input=stdin, encoding="utf-8", errors="replace",
    )


def main():
    if not EXE.exists():
        print("ERROR: no existe", EXE)
        return 1

    listing = shell([sys.executable, "-m", "PyInstaller.utils.cliutils.archive_viewer", "-l", str(EXE)]).stdout
    if "index.html" not in listing.replace("\\", "/"):
        print("ERROR: la plantilla index.html NO esta dentro del .exe")
        return 1

    # Extraer la plantilla desde el .exe
    extract_dir = Path("_check")
    extract_dir.mkdir(exist_ok=True)
    cmds = f"x\ntemplates\\index.html\n{extract_dir / 'index_extracted.html'}\nq\n"
    shell([sys.executable, "-m", "PyInstaller.utils.cliutils.archive_viewer", str(EXE)], stdin=cmds)

    html_path = extract_dir / "index_extracted.html"
    if not html_path.exists():
        print("ERROR: no se pudo extraer index.html del .exe")
        return 1

    html = html_path.read_text(encoding="utf-8", errors="replace")
    checks = {
        "selector Formato": "id=\"format\"" in html,
        "Calidad de audio": "Calidad de audio" in html,
        "opcion MP4": "MP4 (video)" in html,
        "version v2.0": "v2.0" in html,
    }
    print("VERIFICACION:", checks)
    if not all(checks.values()):
        print("FALLO: el .exe no incluye las opciones esperadas")
        return 1
    print("OK: el .exe contiene Formato, Calidad de audio y version v2.0")
    return 0


if __name__ == "__main__":
    sys.exit(main())