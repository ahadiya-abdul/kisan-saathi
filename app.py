from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time
from dataclasses import asdict, dataclass
from functools import wraps
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "fieldwise.sqlite3"
app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("FIELDWISE_SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FIELDWISE_COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=1800,
    MAX_CONTENT_LENGTH=16 * 1024,
)
LOGIN_WINDOW_SECONDS = 900
MAX_LOGIN_ATTEMPTS = 5


@dataclass(frozen=True)
class AdvisoryRecord:
    id: str
    title: str
    crop: str
    pest: str
    agent: str
    district: str
    soil: str
    stage: str
    cost: int
    distance_km: int
    availability: str
    text: str
    source: str


RECORDS = [
    AdvisoryRecord("icar-001", "Trichogramma cards for maize", "Maize", "Fall armyworm", "Trichogramma", "Mandya", "Loamy", "Vegetative", 150, 8, "Available", "Release Trichogramma cards at 50,000 parasitoids per hectare every 10 days from 20-25 days after sowing. Remove cards before irrigation and avoid broad-spectrum insecticides for at least five days.", "ICAR biocontrol field guidance"),
    AdvisoryRecord("kvk-002", "Neem IPM for maize aphids", "Maize", "Aphids", "Neem extract", "Mandya", "Loamy", "Vegetative", 120, 5, "Available", "For early aphid hotspots, use an approved neem-based product in the evening and conserve ladybird beetles. Scout five plants in five locations twice per week.", "Mandya KVK IPM advisory"),
    AdvisoryRecord("icar-003", "Beauveria for tomato whitefly", "Tomato", "Whitefly", "Beauveria bassiana", "Bengaluru Rural", "Sandy loam", "Flowering", 180, 18, "Available", "Apply an approved Beauveria formulation in the evening when humidity is high and sunlight is mild. Repeat after 7-10 days only if scouting still finds live pests.", "ICAR bioprotection profile"),
    AdvisoryRecord("kvk-004", "Bt for cabbage caterpillars", "Cabbage", "Caterpillars", "Bacillus thuringiensis", "Nashik", "Loamy", "Vegetative", 160, 12, "Limited", "Bt is most effective against young caterpillar larvae. Spray in the late afternoon, ensure leaf coverage, and avoid strongly alkaline tank mixes.", "Nashik KVK vegetable IPM guide"),
    AdvisoryRecord("icar-005", "Trichoderma soil application", "Tomato", "Root disease", "Trichoderma viride", "Bengaluru Rural", "Sandy loam", "Transplanting", 140, 10, "Available", "Apply registered Trichoderma through treated compost or soil at transplanting. Use healthy seedlings and avoid mixing with fungicides that harm beneficial fungi.", "ICAR natural farming bulletin"),
]

GRAPH_EDGES = [
    ("Maize", "affected_by", "Fall armyworm"), ("Fall armyworm", "controlled_by", "Trichogramma"),
    ("Maize", "affected_by", "Aphids"), ("Aphids", "controlled_by", "Neem extract"),
    ("Tomato", "affected_by", "Whitefly"), ("Whitefly", "controlled_by", "Beauveria bassiana"),
    ("Cabbage", "affected_by", "Caterpillars"), ("Caterpillars", "controlled_by", "Bacillus thuringiensis"),
]


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY, query TEXT NOT NULL, context TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        connection.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        connection.execute("CREATE TABLE IF NOT EXISTS login_attempts (ip TEXT PRIMARY KEY, failures INTEGER NOT NULL DEFAULT 0, first_failure REAL NOT NULL DEFAULT 0)")


def csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def valid_csrf() -> bool:
    supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    return bool(supplied and secrets.compare_digest(supplied, session.get("_csrf_token", "")))


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required."}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def login_blocked(ip: str) -> bool:
    with sqlite3.connect(DB_PATH) as connection:
        row = connection.execute("SELECT failures, first_failure FROM login_attempts WHERE ip = ?", (ip,)).fetchone()
    if not row or time.time() - row[1] > LOGIN_WINDOW_SECONDS:
        return False
    return row[0] >= MAX_LOGIN_ATTEMPTS


def record_login_failure(ip: str) -> None:
    now = time.time()
    with sqlite3.connect(DB_PATH) as connection:
        row = connection.execute("SELECT failures, first_failure FROM login_attempts WHERE ip = ?", (ip,)).fetchone()
        if not row or now - row[1] > LOGIN_WINDOW_SECONDS:
            connection.execute("INSERT OR REPLACE INTO login_attempts (ip, failures, first_failure) VALUES (?, 1, ?)", (ip, now))
        else:
            connection.execute("UPDATE login_attempts SET failures = failures + 1 WHERE ip = ?", (ip,))


def clear_login_failures(ip: str) -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("DELETE FROM login_attempts WHERE ip = ?", (ip,))


def score(record: AdvisoryRecord, context: dict[str, Any], query: str) -> int:
    query_lower = query.lower()
    haystack = " ".join(str(value) for value in asdict(record).values()).lower()
    words = {word.strip(".,?!:;") for word in query_lower.split() if len(word) > 2}
    value = sum(2 for word in words if word in haystack)
    value += 8 if context["crop"].lower() == record.crop.lower() else 0
    value += 8 if context["pest"].lower() == record.pest.lower() else 0
    value += 6 if context["district"].lower() == record.district.lower() else 0
    value += 3 if context["soil"].lower() == record.soil.lower() else 0
    value += 3 if context["stage"].lower() == record.stage.lower() else 0
    value += 4 if record.cost <= context["budget"] else -7
    if record.crop.lower() in query_lower:
        value += 12 if record.crop.lower() == context["crop"].lower() else -12
    if record.pest.lower() in query_lower:
        value += 14 if record.pest.lower() == context["pest"].lower() else -14
    return value


def retrieve(query: str, context: dict[str, Any]) -> list[AdvisoryRecord]:
    ranked = sorted(RECORDS, key=lambda record: score(record, context, query), reverse=True)
    return [record for record in ranked if score(record, context, query) > 0][:3]


def graph_for(context: dict[str, Any], primary: AdvisoryRecord | None) -> list[dict[str, str]]:
    terms = {context["crop"].lower(), context["pest"].lower()}
    if primary:
        terms.add(primary.agent.lower())
    return [{"from": start, "relationship": relation, "to": end} for start, relation, end in GRAPH_EDGES if start.lower() in terms or end.lower() in terms]


def build_answer(query: str, context: dict[str, Any], records: list[AdvisoryRecord]) -> str:
    if not records:
        return "I could not find a verified local match. Please provide the district, crop stage, pest, and budget so I can avoid generic or unsafe advice."
    primary = records[0]
    budget_note = "within your stated budget" if primary.cost <= context["budget"] else "above your stated budget; ask your KVK about a lower-cost alternative"
    query_lower = query.lower()
    if any(word in query_lower for word in ("when", "timing", "time", "evening", "apply")):
        action = f"**Timing for this field:** {primary.text.split('.')[0]}. Prefer the evening when applying a microbial or botanical product, unless its label says otherwise."
    elif any(word in query_lower for word in ("cost", "cheap", "budget", "price", "afford")):
        alternatives = [f"{record.agent} (₹{record.cost}/acre)" for record in records if record.cost <= context["budget"]]
        action = f"**Budget view:** {', '.join(alternatives) or 'No retrieved option is within this budget'}. The nearest recorded source is {primary.distance_km} km away."
    elif any(word in query_lower for word in ("scout", "identify", "symptom", "look", "check")):
        action = f"**Scout before treating:** inspect five plants at five points in the field during the {context['stage'].lower()} stage. Record live pest counts and re-check in 2-3 days before escalating."
    elif any(word in query_lower for word in ("prevent", "next", "avoid", "control")):
        action = f"**Next field action:** use {primary.agent} only after confirming the pest, avoid broad-spectrum products that harm beneficials, and reassess after the label interval."
    else:
        action = f"**Decision for this field:** because the crop is {context['crop']}, the stage is {context['stage'].lower()}, and the budget is ₹{context['budget']}/acre, start with {primary.agent} and compare the alternatives shown in the evidence panel."
    return (
        f"For {context['crop']} at the {context['stage'].lower()} stage in {context['district']}, "
        f"**{primary.agent}** is the strongest verified match ({budget_note}).\n\n"
        f"{primary.text}\n\n"
        f"{action}\n\n"
        f"**Why this was ranked:** {primary.agent} is {primary.distance_km} km away, "
        f"has {primary.availability.lower()} local availability, and costs about ₹{primary.cost}/acre.\n\n"
        "**Safety:** confirm local registration and label directions, scout before applying, protect pollinators, and contact your KVK for a field diagnosis."
    )


@app.get("/login")
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))
    return render_template("login.html", csrf_token=csrf_token(), error=None)


@app.post("/login")
def login_submit():
    if not valid_csrf():
        return render_template("login.html", csrf_token=csrf_token(), error="Your session expired. Refresh the page and try again."), 400
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    ip = request.remote_addr or "unknown"
    if login_blocked(ip):
        return render_template("login.html", csrf_token=csrf_token(), error="Too many attempts. Please try again in 15 minutes."), 429
    with sqlite3.connect(DB_PATH) as connection:
        user = connection.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    if not user or not check_password_hash(user[1], password):
        record_login_failure(ip)
        return render_template("login.html", csrf_token=csrf_token(), error="Invalid email or password."), 401
    clear_login_failures(ip)
    session.clear()
    session.permanent = True
    session["user_id"] = user[0]
    session["email"] = email
    csrf_token()
    return redirect(url_for("index"))


@app.post("/register")
def register():
    if not valid_csrf():
        return render_template("login.html", csrf_token=csrf_token(), error="Your session expired. Refresh the page and try again."), 400
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if "@" not in email or len(email) > 254 or len(password) < 12:
        return render_template("login.html", csrf_token=csrf_token(), error="Use a valid email and a password of at least 12 characters."), 400
    try:
        with sqlite3.connect(DB_PATH) as connection:
            cursor = connection.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, generate_password_hash(password)))
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return render_template("login.html", csrf_token=csrf_token(), error="That email is already registered."), 409
    session.clear()
    session.permanent = True
    session["user_id"] = user_id
    session["email"] = email
    csrf_token()
    return redirect(url_for("index"))


@app.post("/logout")
@auth_required
def logout():
    if not valid_csrf():
        return jsonify({"error": "Invalid security token."}), 400
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
@auth_required
def index():
    init_db()
    return render_template("index.html", csrf_token=csrf_token(), email=session.get("email", ""))


@app.post("/api/chat")
@auth_required
def chat():
    if not valid_csrf():
        return jsonify({"error": "Invalid security token."}), 400
    payload: dict[str, Any] = request.get_json(silent=True) or {}
    query = str(payload.get("message", "")).strip()
    if not query:
        return jsonify({"error": "Please enter a question about your crop or pest."}), 400
    try:
        budget = max(0, int(payload.get("budget", 200)))
    except (TypeError, ValueError):
        return jsonify({"error": "Budget must be a whole number."}), 400
    context = {
        "crop": str(payload.get("crop", "Maize")).strip() or "Maize",
        "pest": str(payload.get("pest", "Fall armyworm")).strip() or "Fall armyworm",
        "district": str(payload.get("district", "Mandya")).strip() or "Mandya",
        "soil": str(payload.get("soil", "Loamy")).strip() or "Loamy",
        "stage": str(payload.get("stage", "Vegetative")).strip() or "Vegetative",
        "budget": budget,
        "language": str(payload.get("language", "English")).strip() or "English",
    }
    records = retrieve(query, context)
    init_db()
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("INSERT INTO conversations (query, context) VALUES (?, ?)", (query, json.dumps(context)))
    return jsonify({
        "answer": build_answer(query, context, records),
        "context": context,
        "sources": [{"id": r.id, "title": r.title, "source": r.source, "confidence": "High" if r.availability == "Available" else "Medium", "cost": r.cost, "distance_km": r.distance_km, "availability": r.availability} for r in records],
        "graph": graph_for(context, records[0] if records else None),
        "weather": {"condition": "Warm and partly cloudy", "humidity": "68%", "advice": "Evening application is preferred."},
        "market": {"neem_extract": "₹120/acre", "trichogramma": "₹150/acre", "source": "Local availability index (demo)"},
    })


@app.get("/api/knowledge")
@auth_required
def knowledge():
    return jsonify([asdict(record) for record in RECORDS])


init_db()

if __name__ == "__main__":
    app.run(debug=True)
