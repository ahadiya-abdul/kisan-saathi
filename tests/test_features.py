import io
import uuid
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def auth_headers():
    email = f"features-{uuid.uuid4().hex}@example.com"
    result = client.post("/api/auth/register", json={"name": "Feature Farmer", "email": email, "password": "secure-pass-123"})
    return {"Authorization": f"Bearer {result.json()['access_token']}"}

def test_image_demo_and_validation():
    response = client.post("/api/image-analyze", files={"file": ("leaf.png", io.BytesIO(b"png"), "image/png")})
    assert response.status_code == 200
    assert response.json()["demo"] is True
    assert client.post("/api/image-analyze", files={"file": ("x.txt", io.BytesIO(b"x"), "text/plain")}).status_code == 415

def test_weather_budget_outbreak_supplier_planner_compatibility():
    weather = client.post("/api/weather-recommend", json={"district":"Dharwad","crop":"Maize","pest":"Fall Armyworm","humidity":80})
    assert weather.status_code == 200 and "weather" in weather.json()
    budget = client.post("/api/budget-optimize", json={"budget":200,"area_acres":1,"crop":"Maize","pest":"Fall Armyworm"})
    assert budget.status_code == 200 and "estimated_total" in budget.json()
    outbreak = client.post("/api/outbreak-warning", json={"district":"Dharwad","crop":"Maize","pest":"Fall Armyworm","reports_last_7_days":12})
    assert outbreak.json()["risk_level"] == "high"
    assert client.post("/api/local-suppliers", json={"district":"Dharwad","product":"Neem Oil"}).status_code == 200
    assert client.post("/api/pest-planner", json={"crop":"Maize","pest":"Fall Armyworm","start_date":"2026-09-17"}).status_code == 200
    compatibility = client.post("/api/treatment-compatibility", json={"products":["Trichogramma","Neem Oil"]})
    assert compatibility.status_code == 200 and compatibility.json()["compatible"] is True

def test_dashboard_requires_auth_and_returns_history():
    assert client.get("/api/farmer/dashboard").status_code == 401
    headers = auth_headers()
    assert client.get("/api/farmer/dashboard", headers=headers).json()["chat_history"] == []
