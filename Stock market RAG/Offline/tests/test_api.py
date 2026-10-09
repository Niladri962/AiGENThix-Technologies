from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import app


def test_at15_health_and_ask_match_schema(built_index):
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert isinstance(body["provider"], str)
    assert isinstance(body["model"], str)
    assert body["chunks"] > 0

    resp = client.post("/ask", json={"question": "What is a demat account?", "session_id": None})
    assert resp.status_code == 200
    data = resp.json()
    for field in ("answer", "citations", "refused", "refusal_category", "trace_id", "provider", "model"):
        assert field in data


def test_at15_empty_question_returns_422(built_index):
    client = TestClient(app)
    resp = client.post("/ask", json={"question": ""})
    assert resp.status_code == 422
