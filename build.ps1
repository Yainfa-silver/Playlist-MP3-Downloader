$ErrorActionPreference = "Stop"

python -m pip install --upgrade flask pystray pillow pyinstaller

python -m PyInstaller `
    --noconfirm --clean --onefile --noconsole `
    --name "PlaylistMP3Downloader" `
    --add-data "templates;templates" `
    --hidden-import "pystray._win32" `
    main.py

Write-Host ""
Write-Host "EXE generado en: dist\PlaylistMP3Downloader.exe"
