"""Stažení celého VOD chatu (řízení běhu, progress, zrušení)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Protocol

from . import convert
from .client import KickError
from .urls import parse_kick_date, parse_vod_url, uuid7_datetime

WINDOW = timedelta(seconds=5)
CHUNK = 16                 # kolik oken stahujeme paralelně v jedné dávce
IDLE_STOP_S = 30 * 60      # bez délky VOD: konec po tolika sekundách bez jediné zprávy
MAX_LENGTH_S = 48 * 3600   # bezpečnostní strop


class Client(Protocol):
    def get_channel(self, slug: str) -> dict: ...
    def list_videos(self, channel_id) -> list[dict]: ...
    def history(self, channel_id, at: datetime) -> list[dict]: ...
    def fetch_emote(self, emote_id) -> bytes: ...
    def fetch_image(self, url: str) -> bytes: ...


class Cancelled(Exception):
    pass


@dataclass
class Progress:
    phase: str = "queued"      # queued | meta | chat | emotes | done | error | cancelled
    message: str = ""
    done: int = 0
    total: int = 0             # 0 = neznámý
    messages: int = 0
    failed_windows: int = 0
    cancel: bool = field(default=False, repr=False)


def _duration_s(vod: dict | None) -> int | None:
    """Délka VOD z API. Hodnota může být v ms nebo s, proto heuristika."""
    if not vod:
        return None
    for key in ("duration", "length"):
        v = vod.get(key)
        if isinstance(v, (int, float)) and v > 0:
            return int(v / 1000) if v > 172_800 else int(v)
    ls = vod.get("livestream") or {}
    v = ls.get("duration")
    if isinstance(v, (int, float)) and v > 0:
        return int(v / 1000) if v > 172_800 else int(v)
    return None


def run(
    client: Client,
    url: str,
    *,
    with_emotes: bool = True,
    length_override_s: int | None = None,
    progress: Progress | None = None,
    workers: int = 4,
) -> dict:
    p = progress or Progress()

    def check():
        if p.cancel:
            raise Cancelled()

    # --- metadata ---
    p.phase, p.message = "meta", "Zjišťuju informace o videu…"
    slug, vod_uuid = parse_vod_url(url)
    channel = client.get_channel(slug)
    channel_id = channel.get("id")
    if not channel_id:
        raise KickError(f"Kanál „{slug}“ nemá v API žádné id.")
    vod = next((v for v in client.list_videos(channel_id) if v.get("id") == vod_uuid), None)
    if vod and vod.get("start_time"):
        start = parse_kick_date(vod["start_time"])
    else:
        start = uuid7_datetime(vod_uuid)
    if start is None:
        raise KickError("Nepodařilo se zjistit čas startu VOD (není v seznamu a UUID není v7).")
    length_s = length_override_s or _duration_s(vod)
    title = (vod or {}).get("title") or (vod or {}).get("session_title") or f"{slug} {vod_uuid}"
    cats = (vod or {}).get("categories") or []
    game = (cats[0].get("name") if cats and isinstance(cats[0], dict) else None) or (
        ((vod or {}).get("category") or {}).get("name")
    )
    views = int((vod or {}).get("views") or (vod or {}).get("view_count") or 0)

    # --- chat ---
    p.phase = "chat"
    p.total = (length_s + 4) // 5 if length_s else 0
    p.message = "Stahuju chat…"
    raw: dict[str, dict] = {}
    idx = 0
    idle_windows = 0
    max_idx = MAX_LENGTH_S // 5
    now = datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while True:
            check()
            last_idx = (p.total if p.total else max_idx)
            batch = list(range(idx, min(idx + CHUNK, last_idx)))
            if not batch:
                break
            ats = [start + WINDOW * i for i in batch]
            if length_s is None and ats[0] > now:
                break

            def fetch(at):
                try:
                    return client.history(channel_id, at)
                except KickError:
                    return None

            results = list(pool.map(fetch, ats))
            for msgs in results:
                if msgs is None:
                    p.failed_windows += 1
                    continue
                if msgs:
                    idle_windows = 0
                else:
                    idle_windows += 1
                for m in msgs:
                    if m.get("id"):
                        raw[m["id"]] = m
            idx += len(batch)
            p.done = idx
            p.messages = len(raw)
            if length_s is None and idle_windows * 5 >= IDLE_STOP_S:
                break

    ordered = sorted(raw.values(), key=lambda m: (parse_kick_date(m["created_at"]), m["id"]))
    if length_s is None:
        last = parse_kick_date(ordered[-1]["created_at"]) if ordered else start
        length_s = int((last - start).total_seconds())
    comments = [convert.convert_message(m, start, str(channel_id), vod_uuid) for m in ordered]

    # --- emoty ---
    third: list[dict] = []
    if with_emotes:
        emotes = convert.collect_emotes(ordered)
        p.phase, p.done, p.total = "emotes", 0, len(emotes)
        p.message = "Stahuju obrázky emotů…"

        def get_emote(item):
            name, eid = item
            try:
                return convert.embed_emote(name, client.fetch_emote(eid))
            except KickError:
                return None

        with ThreadPoolExecutor(max_workers=8) as pool:
            for res in pool.map(get_emote, emotes.items()):
                check()
                p.done += 1
                if res:
                    third.append(res)

    # --- badge (collectibles, level…) ---
    badge_docs: list[dict] = []
    if with_emotes:
        badges = convert.collect_badges(ordered)
        p.phase, p.done, p.total = "emotes", 0, len(badges)
        p.message = "Stahuju obrázky badgů…"

        def get_badge(item):
            key, url = item
            try:
                return key, client.fetch_image(url)
            except KickError:
                return key, None

        images: dict[tuple[str, str], bytes] = {}
        with ThreadPoolExecutor(max_workers=8) as pool:
            for key, data in pool.map(get_badge, badges.items()):
                check()
                p.done += 1
                if data:
                    images[key] = data
        badge_docs = convert.embed_badges(images)

    doc = convert.build_document(
        channel=channel, slug=slug, video_id=vod_uuid, title=title, start=start,
        length_s=length_s, game=game, view_count=views, comments=comments, third_party=third,
        twitch_badges=badge_docs,
    )
    p.phase, p.message = "done", f"Hotovo: {len(comments)} zpráv."
    return doc
