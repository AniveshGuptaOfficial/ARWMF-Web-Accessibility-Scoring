"""Web UI API tests (no browser launches — job worker is only started in main).

Covers request validation, job lookup, static serving, and health.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("flask", reason="web extra not installed: pip install -e .[web]")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))

import server  # noqa: E402


@pytest.fixture()
def client():
    server.app.config["TESTING"] = True
    return server.app.test_client()


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_index_served(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"A-RWMF" in resp.data


def test_rejects_missing_and_bad_urls(client):
    assert client.post("/api/analyze", json={}).status_code == 400
    assert client.post("/api/analyze", json={"url": "not a url"}).status_code == 400
    assert client.post("/api/analyze", json={"url": "ftp://example.com"}).status_code == 400
    assert client.post("/api/analyze", json={"url": "x" * 3000}).status_code == 400


def test_analyze_queues_job(client):
    resp = client.post("/api/analyze",
                       json={"url": "https://example.com", "viewport": "mobile"})
    assert resp.status_code == 202
    job_id = resp.get_json()["job_id"]

    status = client.get(f"/api/jobs/{job_id}")
    assert status.status_code == 200
    body = status.get_json()
    assert body["status"] == "queued"
    assert body["viewport"] == "mobile"
    assert body["url"] == "https://example.com"

    # drain the queue entry so a later real run doesn't pick up a stale job
    try:
        server.QUEUE.get_nowait()
        server.QUEUE.task_done()
        server.JOBS.pop(job_id, None)
    except Exception:
        pass


def test_unknown_job_404(client):
    assert client.get("/api/jobs/does-not-exist").status_code == 404
