import json
from pathlib import Path

import pytest

from kickchat import convert, job
from kickchat.urls import BadUrl, parse_kick_date, parse_vod_url, uuid7_datetime
from tests.fakes import START, VOD, FakeClient

URL = f"https://kick.com/Haiset/videos/{VOD}"


def test_parse_url():
    assert parse_vod_url(URL) == ("haiset", VOD)
    assert parse_vod_url(f"kick.com/x/videos/{VOD}?t=1")[1] == VOD
    with pytest.raises(BadUrl):
        parse_vod_url("https://kick.com/haiset")


def test_uuid7_and_dates():
    assert uuid7_datetime("00000000-0000-4000-8000-000000000000") is None  # v4
    assert uuid7_datetime(VOD).year >= 2020
    assert parse_kick_date("2026-09-06 19:02:13") == START
    assert parse_kick_date("2026-09-06T19:02:13Z") == START


def test_fragments_like_sample():
    f = convert.split_fragments("[emote:1:A] [emote:2:B]")
    assert [x["text"] for x in f] == ["A", " ", "B"]
    assert convert.split_fragments("jen text") == [{"text": "jen text", "emoticon": None}]


def test_full_run():
    p = job.Progress()
    doc = job.run(FakeClient(), URL, progress=p)
    c = doc["comments"]
    assert [x["_id"] for x in c] == ["m1", "m2", "m3", "m4"]
    assert [x["content_offset_seconds"] for x in c] == [0, 7, 7, 58]
    assert doc["video"]["length"] == 600 and doc["video"]["game"] == "Just Chatting"
    assert doc["streamer"] == {"name": "Haiset", "login": "haiset", "id": 12345}
    assert p.failed_windows == 1 and p.phase == "done"
    names = {e["name"] for e in doc["embeddedData"]["thirdParty"]}
    assert names == {"POLICE"}  # emote 5 spadl a neshodil job
    assert c[0]["message"]["user_badges"] == [
        {"_id": "subscriber", "version": "3"},
        {"_id": "moderator", "version": "1"},
        {"_id": "GOAT", "version": "1"},       # collectible, vybraný
        {"_id": "level", "version": "7"},      # level badge, verze = level
    ]                                          # FLYBY není selected -> vynechán
    tb = {b["name"]: b["versions"] for b in doc["embeddedData"]["twitchBadges"]}
    assert set(tb) == {"GOAT", "subscriber", "moderator"}   # level spadl (404) -> neembeduje se
    assert tb["subscriber"].keys() == {"3"} and tb["moderator"].keys() == {"1"}
    # TwitchDownloader čte každou verzi jako objekt ChatBadgeData (ne holý řetězec)
    v = tb["subscriber"]["3"]
    assert set(v) == {"title", "description", "bytes"} and v["title"] == "3-Month Subscriber"
    import base64
    assert base64.b64decode(v["bytes"])[:4] == b"\x89PNG"


def test_without_duration_stops_on_idle():
    cl = FakeClient(with_duration=False)
    doc = job.run(cl, URL, with_emotes=False)
    assert len(doc["comments"]) == 4
    assert doc["video"]["length"] == 58
    # 30 min / 5 s = 360 prázdných oken + okna se zprávami, zaokrouhleno na dávky
    assert cl.calls < 450


def test_cancel():
    p = job.Progress(cancel=True)
    with pytest.raises(job.Cancelled):
        job.run(FakeClient(), URL, progress=p)


SAMPLE = Path("/mnt/user-data/attachments/b2a86a7e-de1b-51aa-88be-5c5c8ac04c09/aac36e5d-haiset_6.9_part_3_twitch.json")


@pytest.mark.skipif(not SAMPLE.exists(), reason="vzorový soubor není k dispozici")
def test_same_schema_as_sample():
    sample = json.loads(SAMPLE.read_text())
    doc = job.run(FakeClient(), URL)

    def shape(o):
        if isinstance(o, dict):
            return {k: shape(v) for k, v in o.items()}
        if isinstance(o, list):
            return [shape(o[0])] if o else []
        return type(o).__name__ if o is not None else "null"

    s, d = shape(sample), shape(doc)
    for key in ("FileInfo", "streamer", "clipper"):
        assert s[key] == d[key] or key == "clipper"
    assert set(s["video"]) == set(d["video"])
    assert s["comments"][0].keys() == d["comments"][0].keys()
    assert s["comments"][0]["message"].keys() == d["comments"][0]["message"].keys()
    assert s["comments"][0]["commenter"].keys() == d["comments"][0]["commenter"].keys()
    assert s["embeddedData"]["thirdParty"][0].keys() == d["embeddedData"]["thirdParty"][0].keys()


def test_badge_icons_are_valid_pngs():
    import base64, io
    from PIL import Image
    from kickchat import badges
    for t in ["vip", "moderator", "verified", "og", "neznamy_typ"]:
        im = Image.open(io.BytesIO(badges.icon_png(t)))
        assert im.size == (72, 72) and im.format == "PNG"


def test_pick_sub_tier():
    tiers = [{"months": 1, "badge_image": {"src": "a"}}, {"months": 6, "badge_image": {"src": "b"}}]
    assert convert.pick_sub_tier(tiers, 5) == "a"
    assert convert.pick_sub_tier(tiers, 9) == "b"
    assert convert.pick_sub_tier([], 3) is None
