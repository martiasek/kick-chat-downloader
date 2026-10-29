#!/usr/bin/env bash
# Sestaví binárku pro aktuální OS (Linux/macOS). Windows .exe se staví build_exe.bat na Windows.
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean --onefile --name KickChatDownloader \
  --add-data "templates:templates" --collect-all curl_cffi launcher.py
echo "Hotovo: dist/KickChatDownloader"
