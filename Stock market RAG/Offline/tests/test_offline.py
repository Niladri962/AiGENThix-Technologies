from __future__ import annotations

import socket

from app.pipeline import answer


def test_at16_pipeline_runs_fully_offline(built_index, monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("network access attempted during an offline run")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)

    resp = answer("What is a demat account?")
    assert resp.refused is False
    assert resp.citations
