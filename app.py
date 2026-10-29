"""Webová appka: vložíš URL Kick VOD, stáhne se chat jako TwitchDownloader JSON."""
from __future__ import annotations

import argparse
import json
import threading
import uuid
from pathlib import Path

from flask import Flask, Response, abort, jsonify, render_template, request

from kickchat import job as jobmod
from kickchat.client import KickClient, KickError
from kickchat.urls import BadUrl, parse_vod_url

OUTPUT_DIR = Path(__file__).parent / "output"
MAX_JOBS = 20


def create_app(client_factory=KickClient) -> Flask:
    app = Flask(__name__)
    jobs: dict[str, dict] = {}
    lock = threading.Lock()

    def worker(job_id: str, url: str, with_emotes: bool, length_s: int | None):
        j = jobs[job_id]
        try:
            doc = jobmod.run(
                client_factory(), url, with_emotes=with_emotes,
                length_override_s=length_s, progress=j["progress"],
            )
            OUTPUT_DIR.mkdir(exist_ok=True)
            slug, vod = parse_vod_url(url)
            fname = f"{slug}_{vod[:8]}_chat.json"
            data = json.dumps(doc, ensure_ascii=False).encode("utf-8")
            (OUTPUT_DIR / fname).write_bytes(data)
            j.update(data=data, filename=fname)
        except jobmod.Cancelled:
            j["progress"].phase, j["progress"].message = "cancelled", "Zrušeno."
        except (KickError, BadUrl) as e:
            j["progress"].phase, j["progress"].message = "error", str(e)
        except Exception as e:  # neočekávaná chyba nesmí zůstat tichá
            app.logger.exception("job selhal")
            j["progress"].phase, j["progress"].message = "error", f"Neočekávaná chyba: {e}"

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/jobs")
    def start():
        body = request.get_json(silent=True) or {}
        url = body.get("url", "")
        try:
            parse_vod_url(url)
        except BadUrl as e:
            return jsonify(error=str(e)), 400
        length_s = None
        if body.get("length_hours"):
            try:
                length_s = int(float(body["length_hours"]) * 3600)
            except (TypeError, ValueError):
                return jsonify(error="Délka musí být číslo (hodiny)."), 400
            if not 0 < length_s <= jobmod.MAX_LENGTH_S:
                return jsonify(error="Délka musí být mezi 0 a 48 hodinami."), 400
        job_id = uuid.uuid4().hex
        with lock:
            while len(jobs) >= MAX_JOBS:
                jobs.pop(next(iter(jobs)))
            jobs[job_id] = {"progress": jobmod.Progress(), "data": None, "filename": None}
        threading.Thread(
            target=worker, args=(job_id, url, bool(body.get("emotes", True)), length_s), daemon=True
        ).start()
        return jsonify(id=job_id), 202

    @app.get("/api/jobs/<job_id>")
    def status(job_id):
        j = jobs.get(job_id) or abort(404)
        p = j["progress"]
        return jsonify(
            phase=p.phase, message=p.message, done=p.done, total=p.total,
            messages=p.messages, failed_windows=p.failed_windows,
            ready=j["data"] is not None,
        )

    @app.post("/api/jobs/<job_id>/cancel")
    def cancel(job_id):
        j = jobs.get(job_id) or abort(404)
        j["progress"].cancel = True
        return "", 204

    @app.get("/api/jobs/<job_id>/download")
    def download(job_id):
        j = jobs.get(job_id) or abort(404)
        if j["data"] is None:
            abort(409)
        return Response(
            j["data"], mimetype="application/json",
            headers={"Content-Disposition": f'attachment; filename="{j["filename"]}"'},
        )

    return app


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 pro přístup z LAN")
    ap.add_argument("--port", type=int, default=5000)
    a = ap.parse_args()
    create_app().run(host=a.host, port=a.port, threaded=True)
