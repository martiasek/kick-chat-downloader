@echo off
rem Sestavi jeden soubor dist\KickChatDownloader.exe (spustit na Windows).
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv || (echo Nainstaluj Python 3.10+ z python.org & pause & exit /b 1)
)
call .venv\Scripts\activate
pip install -q -r requirements.txt pyinstaller || (echo Instalace selhala & pause & exit /b 1)
pyinstaller --noconfirm --clean --onefile --name KickChatDownloader ^
  --add-data "templates;templates" ^
  --collect-all curl_cffi ^
  launcher.py || (echo Build selhal & pause & exit /b 1)
echo.
echo Hotovo: dist\KickChatDownloader.exe
pause
