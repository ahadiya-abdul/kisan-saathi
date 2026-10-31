"""Regression tests for evidence-first behavior (no canned/sample agricultural results)."""
import io
import uuid
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def auth_headers():
    email = f"features-{uuid.uuid4().hex}@example.com"
    result = client.post("/api/auth/register", json={"name": "Feature Farmer", "email": email, "password": "secure-pass-123"})
    return {"Authorization": f"Bearer {result.json()['access_token']}"}


def test_image_requires_auth_and_validates_format(monkeypatch):
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    client.cookies.clear()
    buf = io.BytesIO(); Image.new("RGB", (120, 120), (80, 130, 70)).save(buf, format="PNG")
    files = {"file": ("leaf.png", io.BytesIO(buf.getvalue()), "image/png")}
    assert client.post("/api/image-analyze", files=files).status_code == 401
    files = {"file": ("leaf.png", io.BytesIO(buf.getvalue()), "image/png")}
    response = client.post("/api/image-analyze", files=files, headers=auth_headers())
    assert response.status_code == 200
    assert response.json()["live"] is False
    assert "confidence" not in response.json()
    bad = client.post("/api/image-analyze", files={"file": ("x.png", io.BytesIO(b"not an image"), "image/png")}, headers=auth_headers())
    assert bad.status_code == 415


def test_decision_endpoints_never_return_sample_answers():
    headers = auth_headers()
    weather = client.post("/api/weather-recommend", json={"district":"Dharwad","crop":"Maize","pest":"unknown","humidity":80}, headers=headers)
    assert weather.status_code == 200 and weather.json()["available"] is False
    budget = client.post("/api/budget-optimize", json={"budget":200,"area_acres":1,"crop":"Maize","pest":"unknown"}, headers=headers)
    assert budget.status_code == 200 and budget.json()["available"] is False
    outbreak = client.post("/api/outbreak-warning", json={"district":"Dharwad","crop":"Maize","pest":"unknown","reports_last_7_days":12}, headers=headers)
    assert outbreak.status_code == 200 and outbreak.json()["available"] is False
    supplier = client.post("/api/local-suppliers", json={"district":"Dharwad","product":"evidence-supported control"}, headers=headers)
    assert supplier.status_code == 200 and supplier.json()["suppliers"] == []
    plan = client.post("/api/pest-planner", json={"crop":"Maize","pest":"unknown","start_date":"2026-10-30"}, headers=headers)
    assert plan.status_code == 200 and plan.json()["available"] is False
    compatibility = client.post("/api/treatment-compatibility", json={"products":["unknown option","unknown option 2"]}, headers=headers)
    assert compatibility.status_code == 200 and compatibility.json()["available"] is False


def test_retrieve_ignores_demo_document_and_reports_empty_corpus(monkeypatch):
    headers = auth_headers()
    response = client.post("/api/retrieve", json={"question":"maize fall armyworm", "context":{"crop":"Maize"}}, headers=headers)
    assert response.status_code == 200
    assert response.json()["available"] is False
    assert all("demo" not in item.get("filename", "").lower() for item in response.json()["results"])


def test_weather_endpoint_needs_authenticated_user():
    client.cookies.clear()
    assert client.get("/api/weather/current?latitude=12.9&longitude=77.6").status_code == 401
