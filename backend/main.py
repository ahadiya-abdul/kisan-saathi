"""Canonical FastAPI application for Fieldwise."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib, hmac, os, sqlite3, json
import jwt
import networkx as nx
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from backend.services.gemini import analyze_image, generate_advice

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "fieldwise.sqlite3"
SECRET = os.getenv("FIELDWISE_JWT_SECRET", "demo-only-change-this-secret-32-bytes")
app = FastAPI(title="Fieldwise Biocontrol Advisor", version="1.0")
app.mount("/static", StaticFiles(directory=ROOT/"static"), name="static")
GRAPH = nx.Graph()
GRAPH.add_edges_from([
 ("Dharwad", "Maize"), ("Maize", "Fall Armyworm"), ("Fall Armyworm", "Trichogramma"),
 ("Fall Armyworm", "Neem Oil"), ("Dharwad", "KVK-Dharwad"), ("Trichogramma", "ICAR"),
 ("Neem Oil", "KVK-Dharwad")
])
ADVICE = {"crop":"Maize","pest":"Fall Armyworm","district":"Dharwad","primary":"Trichogramma",
 "alternative":"Neem Oil","source":"KVK-Dharwad","cost":"₹150/acre",
 "sources":["ICAR","KVK-Dharwad"],"confidence":0.94}

def db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, password TEXT, context TEXT)")
    # The preserved Flask prototype used a smaller users table; migrate it in place.
    columns = {row[1] for row in con.execute("PRAGMA table_info(users)")}
    for name, definition in (("name", "TEXT"), ("password", "TEXT"), ("password_hash", "TEXT"), ("context", "TEXT")):
        if name not in columns:
            con.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")
    con.execute("UPDATE users SET name=COALESCE(name, email), context=COALESCE(context, '{}')")
    con.execute("CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY, user_id INTEGER, question TEXT, answer TEXT, created_at TEXT)")
    con.commit(); return con
def pw(value):
    salt = os.urandom(16); return salt.hex()+":"+hashlib.pbkdf2_hmac("sha256", value.encode(), salt, 180000).hex()
def verify(value, encoded):
    salt, digest = encoded.split(":"); return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", value.encode(), bytes.fromhex(salt), 180000).hex(), digest)
def token(user):
    return jwt.encode({"sub": str(user["id"]), "email": user["email"], "exp": datetime.now(timezone.utc)+timedelta(hours=12)}, SECRET, algorithm="HS256")
def current(authorization: str|None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "): raise HTTPException(401, "Authentication required")
    try: payload=jwt.decode(authorization.split()[1], SECRET, algorithms=["HS256"])
    except jwt.PyJWTError: raise HTTPException(401, "Invalid token")
    con = db()
    row = con.execute("SELECT id,name,email,context FROM users WHERE id=?", (payload["sub"],)).fetchone()
    con.close()
    if not row: raise HTTPException(401, "User not found")
    return dict(row)

class Register(BaseModel): name: str = Field(min_length=1, max_length=80); email: str; password: str = Field(min_length=8)
class Login(BaseModel): email: str; password: str
class Chat(BaseModel): question: str = Field(min_length=1); context: dict = {}
class Context(BaseModel): context: dict
class WeatherRequest(BaseModel):
    district: str = Field(min_length=1, max_length=80)
    crop: str = Field(min_length=1, max_length=80)
    pest: str = Field(min_length=1, max_length=80)
    rain_probability: float = Field(default=0.35, ge=0, le=1)
    humidity: float = Field(default=65, ge=0, le=100)
    temperature_c: float = Field(default=28, ge=-20, le=60)
class BudgetRequest(BaseModel):
    budget: float = Field(gt=0, le=100000)
    area_acres: float = Field(default=1, gt=0, le=10000)
    pest: str = Field(min_length=1, max_length=80)
    crop: str = Field(min_length=1, max_length=80)
class OutbreakRequest(BaseModel):
    district: str = Field(min_length=1, max_length=80)
    crop: str = Field(min_length=1, max_length=80)
    pest: str = Field(min_length=1, max_length=80)
    reports_last_7_days: int = Field(default=0, ge=0, le=100000)
class SupplierRequest(BaseModel):
    district: str = Field(min_length=1, max_length=80)
    product: str = Field(min_length=1, max_length=80)
class PlannerRequest(BaseModel):
    crop: str = Field(min_length=1, max_length=80)
    pest: str = Field(min_length=1, max_length=80)
    start_date: str = Field(min_length=8, max_length=20)
    duration_days: int = Field(default=28, ge=1, le=365)
class CompatibilityRequest(BaseModel):
    products: list[str] = Field(min_length=2, max_length=8)

@app.get("/health")
def health(): return {"status":"ok","service":"fieldwise-fastapi"}
@app.get("/")
def home(): return FileResponse(ROOT/"frontend/modern-index.html")
@app.post("/api/auth/register")
def register(body:Register):
    con=db()
    try:
        encoded = pw(body.password)
        cur=con.execute("INSERT INTO users(name,email,password,password_hash,context) VALUES(?,?,?,?,?)",(body.name,body.email.lower(),encoded,encoded,"{}")); con.commit()
    except sqlite3.IntegrityError:
        con.close()
        raise HTTPException(409,"Email already registered")
    con.close()
    user={"id":cur.lastrowid,"name":body.name,"email":body.email.lower()}
    return {"access_token":token(user),"token_type":"bearer","user":user}
@app.post("/api/auth/login")
def login(body:Login):
    con = db()
    row = con.execute("SELECT * FROM users WHERE email=?", (body.email.lower(),)).fetchone()
    con.close()
    encoded = row["password"] or row["password_hash"] if row else None
    if not encoded or not verify(body.password, encoded): raise HTTPException(401,"Invalid email or password")
    return {"access_token":token(row),"token_type":"bearer","user":{"id":row["id"],"name":row["name"],"email":row["email"]}}
@app.get("/api/auth/me")
def me(user=Depends(current)): return user
def answer(question, context):
    text=(question+" "+json.dumps(context)).lower()
    canonical=all(x in text for x in ("dharwad","maize","armyworm")) or ("budget" in text and "maize" in text)
    a=ADVICE.copy() if canonical else {**ADVICE,"confidence":0.72}
    evidence = {
        "recommendation": a,
        "reasoning_path": ["Dharwad → Maize → Fall Armyworm", f"Fall Armyworm → {a['primary']}", "evidence → cost and local availability"],
        "sources": a["sources"],
    }
    fallback = {
        "answer": f"Use {a['primary']} for {a['pest']} in {a['crop']}. {a['alternative']} is an alternative. Sample cost: {a['cost']}; confirm local availability and label directions with {a['source']}.",
        "recommendation": a,
        "reasoning_path": evidence["reasoning_path"],
        "confidence": a["confidence"],
        "explanation": {
            "matched_context": ["crop", "pest", "district"],
            "why": f"Matches {a['crop']} and {a['pest']} in the local advisory data.",
            "limitations": "Demo/sample evidence only; confirm label, dose, timing and local availability with an agronomist.",
            "generation": "offline",
        },
    }
    generated = generate_advice(question, context, evidence)
    if generated is None:
        return fallback
    return {
        **fallback,
        "answer": generated["answer"],
        "confidence": generated["confidence"],
        "explanation": {
            **fallback["explanation"],
            "why": generated["why_recommended"],
            "limitations": generated["uncertainty"],
            "generation": "gemini",
        },
    }
@app.post("/api/chat")
def chat(body:Chat,user=Depends(current)):
    result=answer(body.question,body.context)
    con=db()
    con.execute("INSERT INTO chats(user_id,question,answer,created_at) VALUES(?,?,?,?)",(user["id"],body.question,result["answer"],datetime.now(timezone.utc).isoformat()))
    con.commit()
    con.close()
    return result
@app.post("/api/retrieve")
def retrieve(body:Chat): return {"results":[ADVICE], "query":body.question}
@app.get("/api/kg/query")
def kg_query(node: str = "Dharwad"):
    return {"node":node,"neighbors":list(GRAPH.neighbors(node)) if node in GRAPH else [],"path":nx.shortest_path(GRAPH,"Dharwad","Trichogramma") if node=="Dharwad" else []}
@app.post("/api/recommend")
def recommend(body:Chat): return answer(body.question,body.context)
@app.put("/api/farmer/context")
def farmer_context(body:Context,user=Depends(current)):
    con=db()
    con.execute("UPDATE users SET context=? WHERE id=?",(json.dumps(body.context),user["id"]))
    con.commit()
    con.close()
    return {"context":body.context}
@app.get("/api/sources")
def sources(): return [{"name":"ICAR","type":"research"},{"name":"KVK-Dharwad","type":"local advisory"}]
@app.get("/api/crops")
def crops(): return ["Maize","Cotton","Sorghum","Pigeon pea"]
@app.get("/api/pests")
def pests(): return ["Fall Armyworm","Aphids","Stem borer","Whitefly"]
@app.get("/api/biocontrols")
def biocontrols(): return [{"name":"Trichogramma","kind":"parasitoid"},{"name":"Neem Oil","kind":"botanical"}]

@app.post("/api/image-analyze")
async def image_analyze(file: UploadFile = File(...)):
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Upload a JPEG, PNG, or WebP image")
    content = await file.read()
    if not content or len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "Image must be between 1 byte and 10 MB")
    result = analyze_image(content, file.content_type)
    if result is None:
        return {"demo": True, "live": False, "filename": file.filename,
                "label": "IMAGE ANALYSIS UNAVAILABLE",
                "analysis": "The cloud image model did not return an analysis. Try again or verify the crop with a local agronomist.",
                "suggested_next_step": "Use a clear, well-lit photo showing the affected plant and contact a KVK before treatment."}
    return {"demo": False, "live": True, "filename": file.filename,
            "label": result["candidate_issue"],
            "analysis": result["safety_note"],
            **result}

@app.post("/api/weather-recommend")
@app.post("/api/weather")
def weather_recommend(body: WeatherRequest):
    factor = "higher fungal/pest pressure" if body.humidity >= 75 or body.rain_probability >= .6 else "moderate weather pressure"
    result = answer(f"{body.district} {body.crop} {body.pest}", {})
    result["weather"] = {"inputs": body.model_dump(), "factor": factor, "demo": True}
    result["answer"] += f" Weather factor (offline demo): {factor}; adjust scouting frequency and confirm locally."
    result["explanation"]["weather_factor"] = factor
    return result

@app.post("/api/budget-optimize")
@app.post("/api/budget/optimize")
def budget_optimize(body: BudgetRequest):
    per_acre = 150.0 if "armyworm" in body.pest.lower() else 120.0
    estimated = round(per_acre * body.area_acres, 2)
    return {"demo": True, "budget": body.budget, "area_acres": body.area_acres,
            "plan": [{"product": "Trichogramma", "quantity": body.area_acres, "estimated_cost": estimated}],
            "estimated_total": estimated, "within_budget": estimated <= body.budget,
            "note": "Sample planning price, not a supplier quote; confirm current local prices."}

@app.post("/api/outbreak-warning")
@app.post("/api/pests/outbreak")
def outbreak_warning(body: OutbreakRequest):
    level = "high" if body.reports_last_7_days >= 10 else "watch" if body.reports_last_7_days >= 3 else "low"
    return {"demo": True, "risk_level": level, "reports_last_7_days": body.reports_last_7_days,
            "warning": "Sample threshold only; this is not a surveillance alert.",
            "actions": ["Scout 10 plants in multiple field spots", "Record fresh symptoms", "Contact your local KVK if spread increases"]}

@app.post("/api/local-suppliers")
@app.post("/api/suppliers/local")
def local_suppliers(body: SupplierRequest):
    return {"demo": True, "district": body.district, "product": body.product,
            "suppliers": [{"name": f"{body.district} KVK (sample)", "type": "advisory centre", "availability": "verify locally"}],
            "note": "Sample directory; no live inventory or endorsement."}

@app.post("/api/pest-planner")
@app.post("/api/planner")
def pest_planner(body: PlannerRequest):
    return {"demo": True, "plan": [
        {"day": 0, "task": "Scout and record pest incidence"},
        {"day": 7, "task": "Review scouting notes and apply only locally approved control if needed"},
        {"day": 14, "task": "Re-scout and check beneficial insects"},
        {"day": body.duration_days, "task": "Evaluate results and consult an agronomist"}],
        "crop": body.crop, "pest": body.pest, "start_date": body.start_date,
        "note": "Sample schedule; follow product labels and local guidance."}

@app.get("/api/farmer/dashboard")
@app.get("/api/dashboard")
def farmer_dashboard(user=Depends(current)):
    con = db()
    chats = [dict(row) for row in con.execute(
        "SELECT question,answer,created_at FROM chats WHERE user_id=? ORDER BY id DESC LIMIT 20", (user["id"],))]
    con.close()
    return {"user": {"id": user["id"], "name": user["name"], "email": user["email"]},
            "context": json.loads(user.get("context") or "{}"), "chat_history": chats}

@app.post("/api/treatment-compatibility")
@app.post("/api/compatibility")
def treatment_compatibility(body: CompatibilityRequest):
    normalized = [x.strip().lower() for x in body.products]
    known = {"trichogramma", "neem oil"}
    unknown = [x for x in body.products if x.strip().lower() not in known]
    compatible = not unknown and len(set(normalized)) == len(normalized)
    return {"demo": True, "compatible": compatible, "products": body.products,
            "warnings": (["Unknown product(s); verify label and expert guidance: " + ", ".join(unknown)] if unknown else []),
            "note": "Offline rule-based checker, not a substitute for a label or agronomist."}
