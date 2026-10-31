import uuid
from fastapi.testclient import TestClient
from backend import main
from backend.main import app

client = TestClient(app)

def test_health_and_catalogues():
    assert client.get("/health").json()["status"] == "ok"
    assert "Maize" in client.get("/api/crops").json()
    assert client.get("/api/kg/query?node=Dharwad").status_code == 200

def test_register_login_me_and_chat_refuses_unverified_sample_advice():
    email = f"farmer-{uuid.uuid4().hex}@example.com"
    body = {"name":"Farmer","email":email,"password":"secure-pass-123"}
    registered = client.post("/api/auth/register", json=body)
    assert registered.status_code == 200
    token = registered.json()["access_token"]
    headers = {"Authorization":f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.post("/api/auth/login", json={"email":email,"password":body["password"]}).status_code == 200
    response = client.post("/api/chat", headers=headers, json={
        "question":"I farm maize in Dharwad and have Fall Armyworm. What should I do?"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is False
    assert data["sources"] == []
    assert "verified" in data["answer"].lower() or "सत्यापित" in data["answer"]

def test_no_corpus_never_returns_canned_recommendation(monkeypatch):
    monkeypatch.setattr(main, "retrieve_evidence", lambda *args, **kwargs: [])
    result = main.answer("Fall Armyworm on maize in Dharwad", {})
    assert result["available"] is False
    assert "Trichogramma" not in result["answer"]
    assert result["sources"] == []
