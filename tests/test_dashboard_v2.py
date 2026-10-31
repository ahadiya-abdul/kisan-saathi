import io
import uuid
from PIL import Image

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def new_user():
    email = f"v2-{uuid.uuid4().hex}@example.com"
    r = client.post("/api/auth/register", json={"name": "V2 Farmer", "email": email, "password": "secure-pass-123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_home_serves_new_dashboard_and_classic_still_available():
    home = client.get("/")
    assert home.status_code == 200 and 'id="view-language"' in home.text
    assert client.get("/classic").status_code == 200


def test_image_analysis_failure_is_explicit(monkeypatch):
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    headers = new_user()
    buf = io.BytesIO(); Image.new("RGB", (120, 120), (80, 130, 70)).save(buf, format="PNG")
    r = client.post("/api/image-analyze", files={"file": ("leaf.png", io.BytesIO(buf.getvalue()), "image/png")}, headers=headers)
    body = r.json()
    assert r.status_code == 200 and body["live"] is False and body["reason"] == "not_configured"
    assert "confidence" not in body  # no fabricated confidence on failure


def test_field_context_round_trip_and_isolation():
    a, b = new_user(), new_user()
    ctx = {"v": 1, "lang": "ml", "field": {"crop": "Maize", "district": "Dharwad", "area": "2", "unit": "hectares"}}
    assert client.put("/api/farmer/context", json={"context": ctx}, headers=a).status_code == 200
    got = client.get("/api/farmer/dashboard", headers=a).json()["context"]
    assert got["field"]["crop"] == "Maize" and got["lang"] == "ml"
    assert client.get("/api/farmer/dashboard", headers=b).json()["context"] == {}


def test_context_requires_login():
    client.cookies.clear()
    assert client.put("/api/farmer/context", json={"context": {}}).status_code in (401, 403)
    assert client.get("/api/farmer/dashboard").status_code in (401, 403)
