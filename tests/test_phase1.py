import uuid
from fastapi.testclient import TestClient
from backend import main
from backend.main import app

client = TestClient(app)

def test_health_and_catalogues():
    assert client.get("/health").json()["status"] == "ok"
    assert "Maize" in client.get("/api/crops").json()
    assert client.get("/api/kg/query?node=Dharwad").status_code == 200

def test_register_login_me_and_chat_canonical_example():
    email = f"demo-{uuid.uuid4().hex}@example.com"
    body = {"name":"Demo Farmer","email":email,"password":"secure-pass-123"}
    registered = client.post("/api/auth/register", json=body)
    assert registered.status_code == 200
    token = registered.json()["access_token"]
    assert client.get("/api/auth/me", headers={"Authorization":f"Bearer {token}"}).status_code == 200
    assert client.post("/api/auth/login", json={"email":email,"password":body["password"]}).status_code == 200
    response = client.post("/api/chat", headers={"Authorization":f"Bearer {token}"}, json={
        "question":"I farm maize in Dharwad and have Fall Armyworm. Budget 200 per acre."
    })
    assert response.status_code == 200
    data = response.json()
    assert data["recommendation"]["primary"] == "Trichogramma"
    assert data["recommendation"]["alternative"] == "Neem Oil"
    assert "KVK-Dharwad" in data["recommendation"]["sources"]

def test_offline_recommendation_is_direct_and_concise(monkeypatch):
    monkeypatch.setattr(main, "generate_advice", lambda *args: None)
    result = main.answer("Fall Armyworm on maize in Dharwad", {})
    assert result["answer"].startswith("Use Trichogramma")
    assert len(result["answer"].split()) <= 35
