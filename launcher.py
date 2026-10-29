"""Spouštěč pro .exe: najde volný port, otevře prohlížeč a spustí server."""
from __future__ import annotations

import socket
import threading
import webbrowser

from app import OUTPUT_DIR, create_app


def free_port(start: int = 5000, tries: int = 20) -> int:
    for port in range(start, start + tries):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:  # nikdo neposlouchá -> volný
                return port
    raise RuntimeError("Nenašel jsem volný port")


def main() -> None:
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    print("Kick Chat Downloader běží na", url)
    print("Staženého chaty najdeš ve složce:", OUTPUT_DIR)
    print("Okno nech otevřené. Zavřením (nebo Ctrl+C) appku ukončíš.")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    create_app().run(host="127.0.0.1", port=port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
