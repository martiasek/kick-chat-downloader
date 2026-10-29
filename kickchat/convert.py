"""Převod zpráv z Kicku do formátu TwitchDownloader JSON (verze 1.4.0)."""
from __future__ import annotations

import base64
import io
import re
import uuid as uuidlib
from datetime import datetime, timezone
from typing import Callable, Iterable

from .urls import parse_kick_date

EMOTE_RE = re.compile(r"\[emote:(\d+):([^\]]*)\]")


def split_fragments(content: str) -> list[dict]:
    """Rozdělí text na fragmenty. Emote [emote:ID:Název] se stane fragmentem s textem Název
    (stejně jako ve vzorovém souboru; obrázek se páruje podle jména přes embeddedData)."""
    out: list[dict] = []
    last = 0
    for m in EMOTE_RE.finditer(content):
        if m.start() > last:
            out.append({"text": content[last : m.start()], "emoticon": None})
        out.append({"text": m.group(2), "emoticon": None})
        last = m.end()
    if last < len(content):
        out.append({"text": content[last:], "emoticon": None})
    if not out:
        out.append({"text": content, "emoticon": None})
    return out


def _v2_key(b: dict) -> tuple[str, str] | None:
    """(název, verze) globálního badge z badges_v2. Level badge má verzi = číslo levelu."""
    name = b.get("name")
    if not name:
        return None
    level = (b.get("metadata") or {}).get("level")
    return str(name), str(level) if level is not None else "1"


def _selected_v2(sender: dict) -> list[dict]:
    """Globální badge (collectibles, level…), které má uživatel vybrané k zobrazení."""
    return [
        b for b in (sender.get("identity") or {}).get("badges_v2") or []
        if b.get("selected") and b.get("image_url") and _v2_key(b)
    ]


def _badges(sender: dict) -> list[dict]:
    res = []
    for b in (sender.get("identity") or {}).get("badges") or []:
        if b.get("type"):
            res.append({"_id": str(b["type"]), "version": str(b.get("count", 1))})
    for b in sorted(_selected_v2(sender), key=lambda b: b.get("sort_order", 50)):
        name, version = _v2_key(b)
        res.append({"_id": name, "version": version})
    return res


def convert_message(m: dict, start: datetime, channel_id: str, video_id: str) -> dict:
    sender = m.get("sender") or {}
    created = parse_kick_date(m["created_at"])
    content = m.get("content") or ""
    name = sender.get("username") or "???"
    return {
        "_id": m["id"],
        "created_at": created.isoformat(timespec="seconds"),
        "channel_id": channel_id,
        "content_type": "video",
        "content_id": video_id,
        "content_offset_seconds": max(0, int((created - start).total_seconds())),
        "commenter": {
            "display_name": name,
            "_id": str(sender.get("id", "")),
            "name": (sender.get("slug") or name).lower(),
            "bio": None,
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2020-01-01T00:00:00Z",
        },
        "message": {
            "body": content,
            "bits_spent": 0,
            "fragments": split_fragments(content),
            "user_badges": _badges(sender),
            "user_color": (sender.get("identity") or {}).get("color") or "#53fc18",
            "emoticons": [],
        },
    }


def collect_emotes(messages: Iterable[dict]) -> dict[str, str]:
    """{název emote: id emote} ze všech zpráv."""
    found: dict[str, str] = {}
    for m in messages:
        for mt in EMOTE_RE.finditer(m.get("content") or ""):
            found.setdefault(mt.group(2), mt.group(1))
    return found


def collect_badges(messages: Iterable[dict]) -> dict[tuple[str, str], str]:
    """{(název, verze): URL obrázku} pro všechny globální badge ve zprávách."""
    found: dict[tuple[str, str], str] = {}
    for m in messages:
        for b in _selected_v2(m.get("sender") or {}):
            found.setdefault(_v2_key(b), b["image_url"])
    return found


def embed_badges(images: dict[tuple[str, str], bytes]) -> list[dict]:
    """Seskupí obrázky podle názvu do formátu embeddedData.twitchBadges."""
    grouped: dict[str, dict[str, str]] = {}
    for (name, version), data in images.items():
        grouped.setdefault(name, {})[version] = base64.b64encode(data).decode("ascii")
    return [{"name": n, "versions": v} for n, v in grouped.items()]


def embed_emote(name: str, data: bytes) -> dict:
    width = height = 56
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as im:
            width, height = im.size
    except Exception:
        pass
    return {
        "id": str(uuidlib.uuid4()),
        "imageScale": 2,
        "data": base64.b64encode(data).decode("ascii"),
        "name": name,
        "width": width,
        "height": height,
        "isZeroWidth": False,
    }


def build_document(
    *,
    channel: dict,
    slug: str,
    video_id: str,
    title: str,
    start: datetime,
    length_s: int,
    game: str | None,
    view_count: int,
    comments: list[dict],
    third_party: list[dict],
    twitch_badges: list[dict] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict:
    channel_id = str(channel.get("id", ""))
    user = channel.get("user") or {}
    return {
        "FileInfo": {
            "Version": {"Major": 1, "Minor": 4, "Patch": 0},
            "CreatedAt": now().isoformat(),
            "UpdatedAt": "0001-01-01T00:00:00",
        },
        "streamer": {
            "name": user.get("username") or channel.get("slug") or slug,
            "login": slug,
            "id": int(channel_id) if channel_id.isdigit() else 0,
        },
        "clipper": None,
        "video": {
            "title": title,
            "description": None,
            "id": video_id,
            "created_at": start.isoformat(timespec="seconds"),
            "start": 0,
            "end": length_s,
            "length": length_s,
            "viewCount": view_count,
            "game": game or "",
            "chapters": [
                {
                    "id": "",
                    "startMilliseconds": 0,
                    "lengthMilliseconds": length_s * 1000,
                    "type": "GAME_CHANGE",
                    "description": game or "",
                    "subDescription": "",
                    "thumbnailUrl": None,
                    "gameId": "",
                    "gameDisplayName": game or "",
                }
            ],
        },
        "comments": comments,
        "embeddedData": {"thirdParty": third_party, "twitchBadges": twitch_badges or [], "twitchBits": []},
    }
