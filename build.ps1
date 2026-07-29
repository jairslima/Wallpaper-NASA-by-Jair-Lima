$ErrorActionPreference = "Stop"
pyinstaller --onefile --windowed --name "Wallpaper NASA by Jair Lima" --clean app.py
Write-Host "Executável criado em dist\Wallpaper NASA by Jair Lima.exe"

