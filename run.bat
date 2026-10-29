@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Vytvarim virtualni prostredi...
  python -m venv .venv || (echo Nainstaluj Python 3.10+ z python.org & pause & exit /b 1)
)
call .venv\Scripts\activate
pip install -q -r requirements.txt
start "" http://127.0.0.1:5000
python app.py
pause
