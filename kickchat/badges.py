"""Vlastní jednoduché ikony pro badge kanálu (moderátor, VIP…).

Kick API u těchto badgů posílá jen typ, ne obrázek (a ikony Kicku zde nedistribuujeme).
Kreslíme proto vlastní, jednoduché PNG v podobných barvách: barevný čtverec s písmenem.
Subscriber badge je výjimka: jeho obrázky dává API (channel.subscriber_badges).
"""
from __future__ import annotations

import io

# typ: (barva pozadí, popisek)
_STYLE: dict[str, tuple[str, str]] = {
    "vip": ("#ffb21e", "V"),
    "moderator": ("#00aef5", "M"),
    "sub_gifter": ("#53fc18", "G"),
    "verified": ("#53fc18", "✓"),
    "founder": ("#ff6b35", "F"),
    "og": ("#ffd400", "OG"),
    "broadcaster": ("#e91916", "B"),
    "staff": ("#9146ff", "S"),
    "subscriber": ("#53fc18", "S"),
}
_INK = "#0b0e0f"
_SIZE = 72


def icon_png(badge_type: str) -> bytes:
    """PNG ikona pro daný typ badge. Neznámý typ dostane šedou ikonu s prvním písmenem."""
    from PIL import Image, ImageDraw, ImageFont

    color, label = _STYLE.get(badge_type, ("#9aa0a6", (badge_type[:1] or "?").upper()))
    img = Image.new("RGBA", (_SIZE, _SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, _SIZE - 3, _SIZE - 3), radius=14, fill=color)
    if label == "✓":  # fajfku kreslíme čarou, font ji nemusí mít
        d.line([(18, 38), (31, 51), (54, 22)], fill=_INK, width=9, joint="curve")
    else:
        font = ImageFont.load_default(size=44 if len(label) == 1 else 32)
        d.text((_SIZE / 2, _SIZE / 2 + 1), label, font=font, fill=_INK, anchor="mm")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
