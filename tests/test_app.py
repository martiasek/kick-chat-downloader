import time

from app import create_app
from tests.fakes import VOD, FakeClient


def test_web_flow(tmp_path, monkeypatch):
    import app as appmod
    monkeypatch.setattr(appmod, "OUTPUT_DIR", tmp_path)
    c = create_app(client_factory=FakeClient).test_client()
    assert c.get("/").status_code == 200
    assert c.post("/api/jobs", json={"url": "nesmysl"}).status_code == 400
    r = c.post("/api/jobs", json={"url": f"https://kick.com/haiset/videos/{VOD}"})
    assert r.status_code == 202
    jid = r.get_json()["id"]
    for _ in range(100):
        s = c.get(f"/api/jobs/{jid}").get_json()
        if s["ready"]:
            break
        time.sleep(0.1)
    assert s["phase"] == "done" and s["messages"] == 4
    d = c.get(f"/api/jobs/{jid}/download")
    assert d.status_code == 200 and "attachment" in d.headers["Content-Disposition"]
    assert len(d.get_json()["comments"]) == 4
    assert list(tmp_path.glob("*_chat.json"))
