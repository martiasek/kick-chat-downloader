import importlib
import shutil
import socket
import sys
from pathlib import Path

import launcher


def test_free_port_skips_busy():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        busy = s.getsockname()[1]
        assert launcher.free_port(busy) != busy


def test_templates_found_when_frozen(tmp_path, monkeypatch):
    """V .exe jsou šablony v sys._MEIPASS a výstup vedle sys.executable."""
    shutil.copytree(Path(__file__).parent.parent / "templates", tmp_path / "templates")
    fake_exe = tmp_path / "KickChatDownloader.exe"
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    import app as appmod
    try:
        appmod = importlib.reload(appmod)
        assert appmod.OUTPUT_DIR == tmp_path / "output"
        assert appmod.create_app().test_client().get("/").status_code == 200
    finally:
        monkeypatch.undo()
        importlib.reload(appmod)
