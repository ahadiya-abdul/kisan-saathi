import io
import uuid
from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.rag import local_corpus


def test_phone_registration_persistent_cookie_and_logout():
    client = TestClient(app)
    phone = "+9198" + uuid.uuid4().int.__str__()[-8:]
    registered = client.post("/api/auth/register", json={"name": "Phone Farmer", "identifier": phone, "password": "strong-passphrase-2026"})
    assert registered.status_code == 200
    assert "fieldwise_session" in registered.cookies
    assert registered.headers.get("set-cookie", "").lower().find("httponly") >= 0
    assert client.get("/api/auth/me").status_code == 200
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401
    login = client.post("/api/auth/login", json={"identifier": phone, "password": "strong-passphrase-2026"})
    assert login.status_code == 200
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_rag_requires_explicit_verified_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(local_corpus, "DOC_DIR", tmp_path)
    monkeypatch.setattr(local_corpus, "MANIFEST", tmp_path / "sources.json")
    (tmp_path / "advice.txt").write_text("Tomato whitefly may be managed through integrated pest management and careful field scouting. " * 5, encoding="utf-8")
    (tmp_path / "sources.json").write_text('{"advice.txt":{"title":"Advisory","source":"Official source","url":"https://example.gov/advice","verified":false}}', encoding="utf-8")
    local_corpus._CACHE_SIGNATURE = None
    assert local_corpus.retrieve("tomato whitefly", {"crop": "Tomato"}) == []
    (tmp_path / "sources.json").write_text('{"advice.txt":{"title":"Advisory","source":"Official source","url":"https://example.gov/advice","verified":true,"crop":"Tomato"}}', encoding="utf-8")
    local_corpus._CACHE_SIGNATURE = None
    assert local_corpus.retrieve("tomato whitefly", {"crop": "Tomato"})
    local_corpus._CACHE_SIGNATURE = None


def test_knowledge_graph_never_uses_unverified_demo_edges():
    from knowledge_graph.evidence_graph import query_graph
    result = query_graph("Dharwad", {})
    assert result["available"] is False
    assert result["relationships"] == []
