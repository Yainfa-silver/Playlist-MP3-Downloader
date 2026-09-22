@echo off
chcp 65001 >nul
title Playlist MP3 Downloader - Compilador
cd /d "%~dp0"

echo ============================================================
echo   Playlist MP3 Downloader - Generador del .exe
echo ============================================================
echo.

rem ---- Comprobar que Python esta instalado ----
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] No se encontro Python en el sistema.
    echo.
    echo Debes instalar Python 3.9 o superior antes de compilar:
    echo   1. Ve a  https://www.python.org/downloads/
    echo   2. Descarga e instala Python
    echo   3. IMPORTANTE: marca la casilla "Add Python to PATH"
    echo   4. Cierra y vuelve a abrir esta ventana, y ejecuta build.bat otra vez
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Instalando librerias necesarias...
python -m pip install --upgrade pip >nul
python -m pip install flask pystray pillow pyinstaller
if errorlevel 1 (
    echo [ERROR] Fallo al instalar las librerias. Revisa tu conexion a internet.
    pause
    exit /b 1
)

echo.
echo [2/3] Compilando el programa (esto puede tardar varios minutos)...
python -m PyInstaller --noconfirm --clean --onefile --noconsole ^
    --name "PlaylistMP3Downloader" ^
    --add-data "templates;templates" ^
    --hidden-import "pystray._win32" ^
    main.py
if errorlevel 1 (
    echo [ERROR] Fallo la compilacion del .exe.
    pause
    exit /b 1
)

echo.
echo [3/3] Terminado.
echo.
echo ============================================================
echo   EXE generado en:  dist\PlaylistMP3Downloader.exe
echo ============================================================
echo.
echo Puedes cerrar esta ventana.
echo El archivo dist\PlaylistMP3Downloader.exe es el unico que
echo necesitas para usar el programa (o regalarselo a quien quieras).
pause