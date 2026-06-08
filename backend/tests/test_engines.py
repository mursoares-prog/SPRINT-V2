"""Testes dos endpoints do espelho dos engines (/api/schedule e /validate)."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.engines.sequence_engine import generate_schedule

client = TestClient(app)

# Reaproveita um caso real do golden de cronograma como inputs válidos.
_FIX = json.loads((Path(__file__).parent / "fixtures" / "sequence_engine.json").read_text(encoding="utf-8"))
SAMPLE_INPUTS = _FIX[0]["inputs"]


def test_post_schedule_generates():
    r = client.post("/api/schedule", json={"inputs": SAMPLE_INPUTS})
    assert r.status_code == 200
    body = r.json()
    expected = generate_schedule(SAMPLE_INPUTS)
    assert body["count"] == len(expected) > 0
    assert [i["packageId"] for i in body["schedule"]] == [i["packageId"] for i in expected]


def test_post_schedule_missing_input():
    r = client.post("/api/schedule", json={"inputs": {"rigType": "DP"}})
    assert r.status_code == 400


def test_validate_identical():
    schedule = generate_schedule(SAMPLE_INPUTS)
    r = client.post("/api/schedule/validate", json={"inputs": SAMPLE_INPUTS, "schedule": schedule})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["identical"] is True
    assert body["firstDivergence"] is None
    assert body["serverCount"] == body["clientCount"] == len(schedule)


def test_validate_divergence():
    schedule = generate_schedule(SAMPLE_INPUTS)
    edited = [dict(it) for it in schedule]
    edited.pop(1)  # remove um item → diverge a partir do índice 1
    r = client.post("/api/schedule/validate", json={"inputs": SAMPLE_INPUTS, "schedule": edited})
    body = r.json()
    assert body["ok"] is True
    assert body["identical"] is False
    assert body["firstDivergence"]["index"] == 1
    assert body["clientCount"] == len(schedule) - 1


def test_validate_bad_inputs():
    r = client.post("/api/schedule/validate", json={"inputs": {"rigType": "DP"}, "schedule": []})
    body = r.json()
    assert body["ok"] is False
    assert "error" in body
