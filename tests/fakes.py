from datetime import datetime, timedelta, timezone

from kickchat.client import KickError

VOD = "0199c1e0-b000-7000-8000-000000000000"
START = datetime(2026, 9, 6, 19, 2, 13, tzinfo=timezone.utc)
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cfc0f01f0005000201a5f645400000000049454e44ae426082"
)


BADGES_V2 = [
    {"name": "GOAT", "image_url": "https://img.kick/goat.png", "selected": True, "sort_order": 1},
    {"name": "level", "image_url": "https://img.kick/lvl7.png", "selected": True, "sort_order": 2, "metadata": {"level": 7}},
    {"name": "FLYBY", "image_url": "https://img.kick/flyby.png", "selected": False},
]


def make_msg(i: int, offset_s: float, content: str) -> dict:
    return {
        "id": f"m{i}",
        "created_at": (START + timedelta(seconds=offset_s)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "content": content,
        "type": "message",
        "sender": {"id": 100 + i, "username": f"User_{i}", "slug": f"user-{i}",
                   "identity": {"color": "#ff00ff", "badges": [{"type": "subscriber", "count": 3}],
                                "badges_v2": BADGES_V2}},
    }


class FakeClient:
    """Falešné Kick API: 10 minut VOD, zprávy v pár oknech, jedno okno spadne."""
    def __init__(self, with_duration=True):
        self.msgs = [make_msg(1, 0, "ahoj"), make_msg(2, 7, "[emote:37230:POLICE] hello [emote:5:Kek]"),
                     make_msg(3, 7.5, "dvě v jednom okně"), make_msg(4, 58, "konec")]
        self.with_duration = with_duration
        self.calls = 0

    def get_channel(self, slug):
        return {"id": 12345, "slug": slug, "user": {"username": "Haiset"}}

    def list_videos(self, channel_id):
        v = {"id": VOD, "start_time": "2026-09-06 19:02:13", "title": "Test stream",
             "views": 42, "categories": [{"name": "Just Chatting"}]}
        if self.with_duration:
            v["duration"] = 600_000
        return [v]

    def history(self, channel_id, at):
        self.calls += 1
        if at == START + timedelta(seconds=30):
            raise KickError("boom")
        return [m for m in self.msgs
                if at <= datetime.fromisoformat(m["created_at"]) < at + timedelta(seconds=5)]

    def fetch_image(self, url):
        if "lvl7" in url:
            raise KickError("404")
        return PNG

    def fetch_emote(self, emote_id):
        if str(emote_id) == "5":
            raise KickError("404")
        return PNG
