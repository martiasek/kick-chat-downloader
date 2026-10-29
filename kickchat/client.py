"""HTTP klient pro neoficiální Kick API.

Kick je za Cloudflare, který blokuje běžné HTTP klienty (requests, urllib) podle TLS otisku.
Proto používáme curl_cffi, který se tváří jako Chrome.
"""
from __future__ import annotations

import random
import time
from datetime import datetime
from typing import Any

from .urls import to_api_iso

KICK_API = "https://kick.com/api/v2"
WEB_API = "https://web.kick.com/api/v1"
EMOTE_URL = "https://files.kick.com/emotes/{id}/fullsize"


class KickError(RuntimeError):
    pass


class KickClient:
    def __init__(self, retries: int = 4, timeout: float = 20.0):
        try:
            from curl_cffi import requests as cffi_requests
        except ImportError as e:  # pragma: no cover
            raise KickError("Chybí balíček curl_cffi (pip install -r requirements.txt)") from e
        self._session = cffi_requests.Session(impersonate="chrome")
        self._retries = retries
        self._timeout = timeout

    # --- nízká úroveň -------------------------------------------------
    def _get(self, url: str, *, binary: bool = False) -> Any:
        last: Exception | None = None
        for attempt in range(self._retries):
            try:
                r = self._session.get(
                    url, headers={"Accept": "application/json"}, timeout=self._timeout
                )
            except Exception as e:  # síťová chyba
                last = e
            else:
                if r.status_code == 200:
                    return r.content if binary else r.json()
                if r.status_code == 404:
                    raise KickError(f"404 Nenalezeno: {url.split('?')[0]}")
                if r.status_code == 403:
                    last = KickError(
                        "403 – Kick (Cloudflare) požadavek odmítl. Zkus to znovu nebo z jiné sítě/IP."
                    )
                elif r.status_code == 429 or r.status_code >= 500:
                    last = KickError(f"HTTP {r.status_code} u {url.split('?')[0]}")
                    ra = r.headers.get("Retry-After")
                    if ra and ra.isdigit():
                        time.sleep(min(int(ra), 30))
                else:
                    raise KickError(f"HTTP {r.status_code} u {url.split('?')[0]}")
            time.sleep(1.0 * 2**attempt + random.random() * 0.3)
        raise KickError(str(last) if last else "Neznámá chyba")

    # --- API ----------------------------------------------------------
    def get_channel(self, slug: str) -> dict:
        return self._get(f"{KICK_API}/channels/{slug}")

    def list_videos(self, channel_id: int | str) -> list[dict]:
        j = self._get(f"{WEB_API}/channels/{channel_id}/videos")
        return j.get("data") or []

    def history(self, channel_id: int | str, at: datetime) -> list[dict]:
        """Zprávy v okně [at, at+5s)."""
        j = self._get(f"{WEB_API}/chat/{channel_id}/history?start_time={to_api_iso(at)}")
        msgs = (j.get("data") or {}).get("messages")
        return msgs if isinstance(msgs, list) else []

    def fetch_emote(self, emote_id: str | int) -> bytes:
        return self._get(EMOTE_URL.format(id=emote_id), binary=True)

    def fetch_image(self, url: str) -> bytes:
        if not url.startswith("https://"):
            raise KickError(f"Nepodporovaná URL obrázku: {url}")
        return self._get(url, binary=True)
