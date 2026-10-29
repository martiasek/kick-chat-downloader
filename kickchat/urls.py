"""Parsování Kick URL a práce s UUIDv7."""
from __future__ import annotations

import re
from datetime import datetime, timezone

_VOD_RE = re.compile(
    r"(?:https?://)?(?:www\.)?kick\.com/(?P<slug>[^/?#]+)/videos/(?P<uuid>[0-9a-fA-F-]{36})",
    re.IGNORECASE,
)


class BadUrl(ValueError):
    pass


def parse_vod_url(url: str) -> tuple[str, str]:
    """Vrátí (slug kanálu, uuid videa) z URL typu https://kick.com/<kanal>/videos/<uuid>."""
    m = _VOD_RE.search((url or "").strip())
    if not m:
        raise BadUrl("Očekávám URL ve tvaru https://kick.com/<kanál>/videos/<uuid>")
    return m["slug"].lower(), m["uuid"].lower()


def uuid7_datetime(uuid: str) -> datetime | None:
    """UUIDv7 má v prvních 48 bitech unix čas v ms. Pro VOD je to čas startu streamu."""
    hexstr = uuid.replace("-", "")
    if len(hexstr) != 32 or hexstr[12] != "7":
        return None
    try:
        ms = int(hexstr[:12], 16)
    except ValueError:
        return None
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    if not (datetime(2020, 1, 1, tzinfo=timezone.utc) < dt < datetime(2100, 1, 1, tzinfo=timezone.utc)):
        return None
    return dt


def parse_kick_date(s: str) -> datetime:
    """Kick posílá "2026-09-26 08:00:00" nebo ISO; bez zóny je to UTC."""
    s = s.strip().replace(" ", "T", 1) if "T" not in s else s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def to_api_iso(dt: datetime) -> str:
    """API chce "2026-09-26T08:00:00Z" (bez milisekund)."""
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
