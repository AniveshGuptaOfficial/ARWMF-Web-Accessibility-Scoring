"""A-RWMF web UI: Flask API + single-worker job queue over the offline pipeline.

Run:
    python webapp/server.py             # serves http://127.0.0.1:5000

API:
    POST /api/analyze        {url, viewport}      -> {job_id}
    GET  /api/jobs/<id>                          -> {status, phase, result?, error?}
    GET  /api/health                             -> {ok: true}
    GET  /captures/<dir>/<file>                  -> stored screenshot
    GET  /                                       -> static/index.html

Jobs run one at a time in a background worker thread (scoring loads CLIP/MiniLM
once per process; serial jobs keep that cache warm and avoid parallel browsers).
"""
from __future__ import annotations

import ipaddress
import os
import queue
import re
import socket
import sys
import threading
import time
import uuid
from pathlib import Path

# this must happen before arwmf imports: bundled Playwright Chromium was never
# downloaded on this machine, so default to the installed Chrome/Edge
os.environ.setdefault("A11Y_BROWSER_CHANNEL", "chrome")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from flask import Flask, jsonify, request, send_from_directory  # noqa: E402

from arwmf.baselines import run_axe_and_score  # noqa: E402
from arwmf.capture import capture_page  # noqa: E402
from arwmf.pipeline import score_capture  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
JOB_CAPTURES = ROOT / "page_captures" / "web_jobs"
JOB_CAPTURES.mkdir(parents=True, exist_ok=True)
MAX_JOBS = 200

app = Flask(__name__, static_folder="static", static_url_path="/static")

JOBS: dict[str, dict] = {}
QUEUE: "queue.Queue[str]" = queue.Queue()
_URL_RE = re.compile(r"^https?://[^\s/]+\.[^\s/]+", re.IGNORECASE)


def _slug(url: str) -> str:
    host = re.sub(r"[^a-z0-9.-]", "", url.split("//", 1)[-1].split("/", 1)[0].lower())
    return host or "page"


def _is_private_host(url: str) -> bool:
    """True when the URL targets loopback/private/link-local space.

    The server is exposed publicly (Cloudflare Tunnel), so a visitor must not be
    able to point the embedded browser at this machine's internal network.
    """
    host = url.split("//", 1)[-1].split("/", 1)[0].split("@")[-1].split(":")[0].lower()
    if not host or host == "localhost" or host.endswith((".local", ".internal", ".lan")):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False  # unresolvable — the pipeline will surface its own error
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


@app.after_request
def _allow_cors(resp):
    # lets the hosted front end (Vercel demo) call this backend from any origin
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


def _worker() -> None:
    """Consume queued jobs: capture -> score -> axe, recording each phase."""
    while True:
        job_id = QUEUE.get()
        job = JOBS.get(job_id)
        if job is None:
            QUEUE.task_done()
            continue
        out = JOB_CAPTURES / f"{job['id8']}_{job['slug']}"
        try:
            job["status"] = "running"

            job["phase"] = "capturing"
            cap = capture_page(job["url"], out, viewport=job["viewport"])

            job["phase"] = "scoring"
            score = score_capture(cap)

            job["phase"] = "axe"
            axe = run_axe_and_score(job["url"])

            job["phase"] = "done"
            job["result"] = {
                **score,
                "axe": axe,
                "screenshot": f"/captures/{out.name}/capture.png",
                "total_seconds": round(time.time() - job["created"], 1),
            }
            job["status"] = "done"
        except Exception as exc:  # recorded so the UI can show a real message
            job["status"] = "error"
            job["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            QUEUE.task_done()


@app.post("/api/analyze")
def analyze():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify(error="missing url"), 400
    if not _URL_RE.match(url):
        return jsonify(error="url must start with http:// or https:// and contain a host"), 400
    if len(url) > 2048:
        return jsonify(error="url too long"), 400
    if _is_private_host(url):
        return jsonify(error="private or internal hosts are not allowed"), 400

    viewport = "mobile" if data.get("viewport") == "mobile" else "desktop"
    job_id = uuid.uuid4().hex

    # prune history so long-lived servers don't grow forever
    if len(JOBS) >= MAX_JOBS:
        for old in [k for k, v in JOBS.items() if v.get("status") in ("done", "error")][:50]:
            JOBS.pop(old, None)

    JOBS[job_id] = {
        "id": job_id,
        "id8": job_id[:8],
        "url": url,
        "viewport": viewport,
        "slug": _slug(url),
        "status": "queued",
        "phase": "queued",
        "created": time.time(),
    }
    QUEUE.put(job_id)
    return jsonify(job_id=job_id), 202


@app.get("/api/jobs/<job_id>")
def job_status(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        return jsonify(error="unknown job"), 404
    return jsonify({
        k: job[k]
        for k in ("id", "url", "viewport", "status", "phase", "result", "error")
        if k in job
    })


@app.get("/api/health")
def health():
    return jsonify(ok=True)


@app.get("/captures/<path:rel>")
def capture_file(rel: str):
    # send_from_directory refuses paths escaping JOB_CAPTURES
    return send_from_directory(JOB_CAPTURES, rel)


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


def main() -> None:
    port = int(os.environ.get("PORT", "5000"))
    threading.Thread(target=_worker, daemon=True, name="arwmf-worker").start()
    print(f"A-RWMF web UI: http://127.0.0.1:{port}  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
