"""Canonical FastAPI application for Fieldwise."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib, hmac, os, sqlite3, json, logging, secrets, re
import jwt
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Form, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
try:
    from werkzeug.security import check_password_hash
except ImportError:  # Flask/Werkzeug is installed from requirements in a full setup
    check_password_hash = None
from pydantic import BaseModel, Field
from backend.services.gemini import analyze_image, generate_advice, model_status, translate_query_for_retrieval
from backend.services.rag.local_corpus import retrieve as retrieve_evidence, corpus_status
from backend.services.image_quality import inspect_and_enhance
from knowledge_graph.evidence_graph import query_graph
import httpx

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "fieldwise.sqlite3"
SECRET = os.getenv("FIELDWISE_JWT_SECRET") or secrets.token_hex(32)  # no predictable committed secret
SESSION_COOKIE = "fieldwise_session"
SESSION_DAYS = 30
COOKIE_SECURE = os.getenv("FIELDWISE_COOKIE_SECURE", "0").lower() in {"1", "true", "yes"}
app = FastAPI(title="Fieldwise Biocontrol Advisor", version="1.1")
app.mount("/static", StaticFiles(directory=ROOT/"static"), name="static")
LANGUAGE_FALLBACKS = {
    "en": "I do not have enough verified crop-specific evidence to recommend a treatment yet. Please upload a clear plant photo and add an official ICAR/KVK crop advisory document, or contact your local KVK before applying treatment.",
    "hi": "अभी मेरे पास इस फसल के लिए उपचार सुझाने हेतु पर्याप्त सत्यापित जानकारी नहीं है। कृपया पौधे की साफ़ तस्वीर दें और आधिकारिक ICAR/KVK सलाह जोड़ें, या उपचार करने से पहले स्थानीय कृषि विज्ञान केंद्र से संपर्क करें।",
    "kn": "ಈ ಬೆಳೆಗೆ ಚಿಕಿತ್ಸೆ ಸೂಚಿಸಲು ಸಾಕಷ್ಟು ಪರಿಶೀಲಿತ ಮಾಹಿತಿ ಈಗ ಲಭ್ಯವಿಲ್ಲ. ಸ್ಪಷ್ಟವಾದ ಸಸ್ಯದ ಚಿತ್ರವನ್ನು ನೀಡಿ ಮತ್ತು ಅಧಿಕೃತ ICAR/KVK ಸಲಹೆಯನ್ನು ಸೇರಿಸಿ, ಅಥವಾ ಚಿಕಿತ್ಸೆ ಮಾಡುವ ಮೊದಲು ಸ್ಥಳೀಯ ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರವನ್ನು ಸಂಪರ್ಕಿಸಿ.",
    "ta": "இந்தப் பயிருக்கு சிகிச்சையை பரிந்துரைக்க போதுமான சரிபார்க்கப்பட்ட ஆதாரம் இப்போது இல்லை. தெளிவான தாவரப் படத்தை வழங்கி அதிகாரப்பூர்வ ICAR/KVK ஆலோசனையைச் சேர்க்கவும் அல்லது சிகிச்சைக்கு முன் உள்ளூர் வேளாண் அறிவியல் மையத்தை அணுகவும்.",
    "te": "ఈ పంటకు చికిత్సను సూచించడానికి ప్రస్తుతం సరిపడిన ధృవీకరించిన ఆధారాలు లేవు. స్పష్టమైన మొక్క ఫోటోను ఇవ్వండి, అధికారిక ICAR/KVK సలహాను జోడించండి లేదా చికిత్సకు ముందు స్థానిక కృషి విజ్ఞాన కేంద్రాన్ని సంప్రదించండి.",
    "ml": "ഈ വിളയ്ക്ക് ചികിത്സ നിർദേശിക്കാൻ മതിയായ സ്ഥിരീകരിച്ച തെളിവുകൾ ഇപ്പോൾ ലഭ്യമല്ല. വ്യക്തമായ ചെടിയുടെ ചിത്രം നൽകുകയും ഔദ്യോഗിക ICAR/KVK ഉപദേശം ചേർക്കുകയും ചെയ്യുക; അല്ലെങ്കിൽ ചികിത്സയ്ക്ക് മുമ്പ് പ്രാദേശിക കൃഷി വിജ്ഞാന കേന്ദ്രവുമായി ബന്ധപ്പെടുക."
}


def db():
    """Open the shared SQLite database and apply additive, data-preserving migrations."""
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, password TEXT, context TEXT)")
    columns = {row[1] for row in con.execute("PRAGMA table_info(users)")}
    table_sql = (con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone() or [""])[0] or ""
    # Older versions declared email NOT NULL, which prevents phone-only accounts.
    # Rebuild only that table, preserving IDs, existing identifiers, hashes, contexts and timestamps.
    if re.search(r"email\s+TEXT\s+(?:UNIQUE\s+NOT\s+NULL|NOT\s+NULL\s+UNIQUE)", table_sql, re.I):
        old_cols = columns
        def old_expr(col, fallback="NULL"):
            return col if col in old_cols else fallback
        con.execute("CREATE TABLE users_v5 (id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, phone TEXT UNIQUE, password TEXT, password_hash TEXT, context TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        fields = ["id", old_expr("name"), old_expr("email"), "NULL", old_expr("password"), old_expr("password_hash"), old_expr("context", "'{}'"), old_expr("created_at", "CURRENT_TIMESTAMP")]
        con.execute("INSERT INTO users_v5 (id,name,email,phone,password,password_hash,context,created_at) SELECT " + ",".join(fields) + " FROM users")
        con.execute("DROP TABLE users")
        con.execute("ALTER TABLE users_v5 RENAME TO users")
        columns = {row[1] for row in con.execute("PRAGMA table_info(users)")}
    for name, definition in (("name", "TEXT"), ("password", "TEXT"), ("password_hash", "TEXT"), ("context", "TEXT"), ("phone", "TEXT"), ("created_at", "TIMESTAMP")):
        if name not in columns:
            con.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")
    con.execute("UPDATE users SET name=COALESCE(name, email, phone), context=COALESCE(context, '{}')")
    con.execute("CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY, user_id INTEGER, question TEXT, answer TEXT, created_at TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS auth_sessions (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, token_hash TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, last_seen_at TEXT NOT NULL)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id)")
    con.execute("CREATE TABLE IF NOT EXISTS login_attempts (ip TEXT PRIMARY KEY, failures INTEGER NOT NULL DEFAULT 0, first_failure REAL NOT NULL DEFAULT 0)")
    con.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (datetime.now(timezone.utc).isoformat(),))
    con.commit()
    return con


def pw(value):
    salt = os.urandom(16)
    iterations = 600000
    return f"pbkdf2_sha256${iterations}${salt.hex()}${hashlib.pbkdf2_hmac('sha256', value.encode(), salt, iterations).hex()}"


def verify(value, encoded):
    try:
        if encoded.startswith("pbkdf2_sha256$"):
            _, rounds, salt_hex, digest = encoded.split("$", 3)
            candidate = hashlib.pbkdf2_hmac("sha256", value.encode(), bytes.fromhex(salt_hex), int(rounds)).hex()
            return hmac.compare_digest(candidate, digest)
        if encoded.startswith(("pbkdf2:", "scrypt:")):
            return bool(check_password_hash and check_password_hash(encoded, value))  # accounts created by the preserved Flask prototype
        # Migrate legacy salt:hex hashes on successful login.
        salt_hex, digest = encoded.split(":", 1)
        candidate = hashlib.pbkdf2_hmac("sha256", value.encode(), bytes.fromhex(salt_hex), 180000).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


def token(user):
    return jwt.encode({"sub": str(user["id"]), "email": user.get("email") if isinstance(user, dict) else user["email"], "exp": datetime.now(timezone.utc)+timedelta(hours=12)}, SECRET, algorithm="HS256")


def _session_cookie(response: Response, user_id: int):
    raw = secrets.token_urlsafe(48)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    con = db()
    con.execute("INSERT INTO auth_sessions(user_id,token_hash,created_at,expires_at,last_seen_at) VALUES(?,?,?,?,?)",
                (user_id, digest, now.isoformat(), (now + timedelta(days=SESSION_DAYS)).isoformat(), now.isoformat()))
    con.commit(); con.close()
    response.set_cookie(SESSION_COOKIE, raw, max_age=SESSION_DAYS*24*60*60, httponly=True,
                        secure=COOKIE_SECURE, samesite="lax", path="/")


def current(request: Request, authorization: str | None = Header(default=None)):
    # Prefer an explicitly supplied legacy bearer credential; browser UI uses only the HttpOnly cookie.
    con = db()
    row = None
    if authorization and authorization.lower().startswith("bearer "):
        try:
            payload = jwt.decode(authorization.split()[1], SECRET, algorithms=["HS256"])
        except jwt.PyJWTError:
            con.close(); raise HTTPException(401, "Invalid token")
        row = con.execute("SELECT id,name,email,phone,context FROM users WHERE id=?", (payload["sub"],)).fetchone()
    raw_session = request.cookies.get(SESSION_COOKIE)
    if row is None and raw_session:
        # SameSite=Lax is the default CSRF barrier; reject cross-origin unsafe requests when Origin is present.
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
                con.close(); raise HTTPException(403, "Cross-origin request rejected")
        digest = hashlib.sha256(raw_session.encode()).hexdigest()
        session_row = con.execute("SELECT user_id FROM auth_sessions WHERE token_hash=? AND expires_at> ?", (digest, datetime.now(timezone.utc).isoformat())).fetchone()
        if session_row:
            con.execute("UPDATE auth_sessions SET last_seen_at=? WHERE token_hash=?", (datetime.now(timezone.utc).isoformat(), digest))
            row = con.execute("SELECT id,name,email,phone,context FROM users WHERE id=?", (session_row["user_id"],)).fetchone()
            con.commit()
    con.close()
    if not row:
        raise HTTPException(401, "Authentication required")
    return dict(row)


def _normalize_identifier(value: str) -> tuple[str | None, str | None]:
    value = (value or "").strip()
    if "@" in value:
        email = value.lower()
        if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise HTTPException(422, "Enter a valid email address or phone number")
        return email, None
    phone = re.sub(r"[\s()\-]", "", value)
    if not re.fullmatch(r"\+?[0-9]{7,15}", phone):
        raise HTTPException(422, "Enter a valid email address or phone number")
    return None, phone


class Register(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=24)
    identifier: str | None = Field(default=None, max_length=254)
    password: str = Field(min_length=8, max_length=256)


class Login(BaseModel):
    email: str | None = None
    phone: str | None = None
    identifier: str | None = None
    password: str = Field(min_length=1, max_length=256)

class Chat(BaseModel): question: str = Field(default="", max_length=2000); context: dict = {}
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

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=(self)")
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path.startswith("/api/auth/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def _login_blocked(ip: str) -> bool:
    con = db(); row = con.execute("SELECT failures, first_failure FROM login_attempts WHERE ip=?", (ip,)).fetchone(); con.close()
    if not row:
        return False
    is_local = ip in {"127.0.0.1", "::1", "localhost", "testclient", "unknown"}
    window = 60 if is_local else 900
    max_fails = 25 if is_local else 5
    return bool(datetime.now(timezone.utc).timestamp() - row["first_failure"] < window and row["failures"] >= max_fails)


def _record_login_failure(ip: str):
    now = datetime.now(timezone.utc).timestamp(); con = db()
    row = con.execute("SELECT failures, first_failure FROM login_attempts WHERE ip=?", (ip,)).fetchone()
    if not row or now - row["first_failure"] > 900:
        con.execute("INSERT OR REPLACE INTO login_attempts(ip,failures,first_failure) VALUES(?,1,?)", (ip, now))
    else:
        con.execute("UPDATE login_attempts SET failures=failures+1 WHERE ip=?", (ip,))
    con.commit(); con.close()


def _clear_login_failures(ip: str):
    con = db(); con.execute("DELETE FROM login_attempts WHERE ip=?", (ip,)); con.commit(); con.close()


@app.get("/health")
def health(): return {"status":"ok","service":"fieldwise-fastapi"}

@app.get("/api/system/status")
def system_status():
    return {"service": "fieldwise-fastapi", "authentication": "HttpOnly persistent session cookie (legacy bearer tokens remain supported)", "llm_status": model_status(), "evidence_corpus": corpus_status(),
            "weather_provider": "Open-Meteo (requires internet and location permission)",
            "advice_policy": "No relevant evidence means no agronomic recommendation is generated."}
@app.get("/")
def home(): return FileResponse(ROOT/"frontend/dashboard-v2.html")
@app.get("/classic")
def classic(): return FileResponse(ROOT/"frontend/modern-index.html")  # previous dashboard, kept unchanged
@app.post("/api/auth/register")
def register(body: Register, response: Response):
    identifier = body.identifier or body.email or body.phone or ""
    if body.email and body.phone:
        raise HTTPException(422, "Register with either email or phone, not both")
    email, phone = _normalize_identifier(identifier)
    con = db()
    try:
        encoded = pw(body.password)
        cur = con.execute("INSERT INTO users(name,email,phone,password,password_hash,context) VALUES(?,?,?,?,?,?)",
                          (body.name.strip(), email, phone, encoded, encoded, "{}"))
        con.commit(); user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        con.close()
        raise HTTPException(409, "An account with this identifier already exists")
    con.close()
    user = {"id": user_id, "name": body.name.strip(), "email": email, "phone": phone}
    _session_cookie(response, user_id)
    return {"access_token": token(user), "token_type": "bearer", "user": user, "session_persistent": True}


@app.post("/api/auth/login")
def login(body: Login, request: Request, response: Response):
    ip = request.client.host if request.client else "unknown"
    if _login_blocked(ip):
        raise HTTPException(429, "Too many login attempts. Wait 15 minutes and try again.")
    identifier = body.identifier or body.email or body.phone or ""
    email, phone = _normalize_identifier(identifier)
    con = db()
    if email:
        row = con.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
    else:
        row = con.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
    if not row:
        con.close(); _record_login_failure(ip)
        raise HTTPException(401, "No account found with this identifier. Please click 'Create account' to sign up.")
    encoded = (row["password"] or row["password_hash"])
    if not encoded or not verify(body.password, encoded):
        con.close(); _record_login_failure(ip)
        raise HTTPException(401, "Incorrect password. Please try again.")
    # Upgrade old low-iteration hashes to the current password-hashing format after a valid login.
    if not encoded.startswith("pbkdf2_sha256$"):
        upgraded = pw(body.password)
        con.execute("UPDATE users SET password=?, password_hash=? WHERE id=?", (upgraded, upgraded, row["id"]))
        con.commit()
    user = {"id": row["id"], "name": row["name"], "email": row["email"], "phone": row["phone"]}
    con.close(); _clear_login_failures(ip)
    _session_cookie(response, user["id"])
    return {"access_token": token(user), "token_type": "bearer", "user": user, "session_persistent": True}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    raw = request.cookies.get(SESSION_COOKIE)
    if raw:
        digest = hashlib.sha256(raw.encode()).hexdigest()
        con = db(); con.execute("DELETE FROM auth_sessions WHERE token_hash=?", (digest,)); con.commit(); con.close()
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=COOKIE_SECURE, samesite="lax")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user=Depends(current)):
    return user

def answer(question, context):
    """Evidence-first advisor: never substitute a canned/sample recommendation."""
    context = dict(context or {})
    question = (question or "").strip()
    retrieval_query = translate_query_for_retrieval(question, str(context.get("language", "en")))
    evidence = retrieve_evidence(retrieval_query, context, top_k=5)
    if not evidence:
        lang = str(context.get("language", "en")).lower()
        if lang not in LANGUAGE_FALLBACKS:
            lang = {"hindi": "hi", "kannada": "kn", "tamil": "ta", "telugu": "te", "malayalam": "ml", "english": "en"}.get(lang, "en")
        return {
            "available": False,
            "answer": LANGUAGE_FALLBACKS[lang],
            "recommended_actions": [],
            "recommendation": {},
            "sources": [],
            "reasoning_path": [],
            "explanation": {"why": "No relevant, non-demo local evidence was retrieved.",
                            "limitations": "The system will not invent a treatment, price, supplier, or risk level.",
                            "generation": "evidence_unavailable"},
        }
    kg_result = query_graph(" ".join([question, str(context.get("crop", "")), str(context.get("pest", ""))]), context, limit=12)
    kg_relationships = kg_result.get("relationships", []) if kg_result.get("available") else []
    evidence_payload = {"passages": evidence, "knowledge_graph": kg_relationships, "corpus": corpus_status()}
    generated = generate_advice(question, context, evidence_payload)
    if generated is None:
        fallback_lang = str(context.get("language", "en")).lower()
        fallback_lang = {"hindi": "hi", "kannada": "kn", "tamil": "ta", "telugu": "te", "malayalam": "ml", "english": "en"}.get(fallback_lang, fallback_lang)
        return {
            "available": False,
            "answer": LANGUAGE_FALLBACKS.get(fallback_lang, LANGUAGE_FALLBACKS["en"]),
            "recommended_actions": [], "recommendation": {},
            "sources": [{"id": e["id"], "title": e["title"], "source": e["source"], "url": e.get("url")} for e in evidence],
            "reasoning_path": [],
            "explanation": {"why": "Evidence was retrieved, but the configured language model did not return a validated response.",
                            "limitations": "No recommendation was generated. Check model configuration and retry.",
                            "generation": "model_unavailable"},
        }
    sources = generated.get("sources", [])
    return {
        "available": True,
        "answer": generated["answer"],
        "recommended_actions": generated.get("recommended_actions", []),
        "recommendation": {},
        "sources": sources,
        "reasoning_path": [f"{r['from']} —{r['relationship']}→ {r['to']}" for r in kg_relationships],
        "knowledge_graph": kg_relationships,
        "confidence": None,
        "explanation": {"why": generated.get("why", ""),
                        "limitations": generated.get("uncertainty", ""),
                        "generation": "gemini_rag",
                        "needs_human_review": generated.get("needs_human_review", True),
                        "price_supported": generated.get("price_supported", False)},
    }
def merge_farmer_context(user: dict, supplied: dict | None) -> dict:
    """Use the authenticated farmer's saved field as canonical context.

    Client-supplied image observations and the selected language are retained,
    but client-supplied crop/location/budget cannot override saved profile data.
    """
    supplied = dict(supplied or {})
    try:
        account_context = json.loads(user.get("context") or "{}")
    except (TypeError, ValueError):
        account_context = {}
    field = account_context.get("field") or {}
    if field:
        crop = field.get("crop", "")
        if crop == "__other": crop = field.get("crop_other", "")
        pest = field.get("pest", "")
        if pest == "__other": pest = field.get("pest_other", "")
        if crop: supplied["crop"] = crop
        if pest: supplied["pest"] = pest
        for key in ("variety", "stage", "sowing_date", "soil", "state", "district", "village"):
            if field.get(key): supplied[key] = field[key]
        try:
            area = float(field.get("area", 0) or 0)
            if area > 0:
                supplied["area"] = area * (2.47105 if field.get("unit") == "hectares" else 1.0)
                supplied["area_unit"] = "acres"
        except (TypeError, ValueError):
            pass
        try:
            if float(field.get("budget", 0) or 0) > 0:
                supplied["budget_inr"] = float(field["budget"])
        except (TypeError, ValueError):
            pass
        if field.get("weather_observation"):
            supplied["weather_summary"] = field["weather_observation"]
    supplied["language"] = supplied.get("language") or account_context.get("lang") or "en"
    return supplied


@app.post("/api/chat")
def chat(body:Chat,user=Depends(current)):
    trusted_context = merge_farmer_context(user, body.context)
    con=db()
    history = con.execute("SELECT question, answer, created_at FROM chats WHERE user_id=? ORDER BY id DESC LIMIT 6", (user["id"],)).fetchall()
    # Reverse into chronological order and bound text so the LLM sees relevant recent context only.
    trusted_context["recent_conversation"] = [{"question": r["question"][:1000], "answer": r["answer"][:1200], "created_at": r["created_at"]} for r in reversed(history)]
    result=answer(body.question, trusted_context)
    con.execute("INSERT INTO chats(user_id,question,answer,created_at) VALUES(?,?,?,?)",(user["id"],body.question,result["answer"],datetime.now(timezone.utc).isoformat()))
    con.commit()
    con.close()
    return result
@app.post("/api/retrieve")
def retrieve(body:Chat, user=Depends(current)):
    results = retrieve_evidence(body.question, body.context, top_k=5)
    return {"results": results, "query": body.question, "available": bool(results), "corpus": corpus_status()}
@app.get("/api/kg/query")
def kg_query(node: str = "", crop: str = "", pest: str = "", state: str = "", district: str = ""):
    result = query_graph(node, {"crop": crop, "pest": pest, "state": state, "district": district})
    result["path"] = result.get("relationships", [])
    return result
@app.post("/api/recommend")
def recommend(body:Chat, user=Depends(current)): return answer(body.question,body.context)
@app.put("/api/farmer/context")
def farmer_context(body:Context,user=Depends(current)):
    con=db()
    con.execute("UPDATE users SET context=? WHERE id=?",(json.dumps(body.context),user["id"]))
    con.commit()
    con.close()
    return {"context":body.context}
@app.get("/api/sources")
def sources():
    return {"corpus": corpus_status(), "source_register": json.loads((ROOT / "data/documents/sources.json").read_text(encoding="utf-8"))}
@app.get("/api/crops")
def crops(): return ["Maize","Cotton","Sorghum","Pigeon pea"]
@app.get("/api/pests")
def pests(): return ["Fall Armyworm","Aphids","Stem borer","Whitefly"]
@app.get("/api/biocontrols")
def biocontrols():
    return {"available": False, "items": [], "message": "No verified crop-specific biocontrol catalogue is configured. Recommendations require relevant source documents."}

@app.post("/api/image-analyze")
async def image_analyze(file: UploadFile = File(...), crop: str = Form(default=""), variety: str = Form(default=""), stage: str = Form(default=""), language: str = Form(default="en"), image_kind: str = Form(default="plant"), user=Depends(current)):
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Upload a JPEG, PNG, or WebP image")
    content = await file.read(10 * 1024 * 1024 + 1)
    if not content:
        raise HTTPException(400, "Image is empty")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Image must be 10 MB or smaller")
    signatures = {"image/jpeg": content.startswith(b"\xff\xd8\xff"),
                  "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
                  "image/webp": len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"}
    if not signatures.get(file.content_type, False):
        raise HTTPException(415, "The file content does not match a supported image format")
    quality = inspect_and_enhance(content)
    if not quality.get("valid"):
        raise HTTPException(415, quality.get("reason", "Invalid image"))
    quality_summary = {k: v for k, v in quality.items() if k not in {"enhanced_bytes", "valid"}}
    if quality.get("too_unclear"):
        return {"demo": False, "live": False, "filename": file.filename, "reason": "image_unclear",
                "label": "Image too unclear for reliable triage", "image_quality": quality_summary,
                "analysis": "The photo is too dark or lacks enough detail for useful visual triage. Please retake it in daylight, hold the camera steady, and show the affected area close-up."}
    # Analyze an enhanced in-memory copy only when a conservative quality adjustment was useful.
    # The original upload is not written to disk and is not modified.
    analysis_bytes = quality.get("enhanced_bytes", content)
    analysis_mime = "image/jpeg" if quality.get("enhanced") else file.content_type
    result = analyze_image(analysis_bytes, analysis_mime, {"crop": crop, "variety": variety, "stage": stage, "language": language, "image_kind": image_kind})
    if result is None:
        return {"demo": False, "live": False, "filename": file.filename,
                "label": "IMAGE ANALYSIS UNAVAILABLE", "reason": "not_configured" if model_status() != "ready" else "model_error",
                "analysis": "The cloud image model did not return an analysis. Try again or verify the crop with a local agronomist.",
                "suggested_next_step": "Use a clear, well-lit photo showing the affected plant and contact a KVK before treatment.",
                "image_quality": quality_summary}
    return {"demo": False, "live": True, "filename": file.filename, "image_kind": image_kind,
            "label": result["candidate_issue"], "analysis": result["safety_note"],
            "image_quality": quality_summary, **result}

@app.get("/api/weather/current")
async def weather_current(latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180), user=Depends(current)):
    """Fetch current weather from Open-Meteo; coordinates are not persisted."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {"latitude": latitude, "longitude": longitude,
              "current": "temperature_2m,relative_humidity_2m,precipitation,rain,showers,weather_code,wind_speed_10m",
              "daily": "precipitation_probability_max,precipitation_sum",
              "forecast_days": 1, "timezone": "auto"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        current_data = data.get("current") or {}
        daily = data.get("daily") or {}
        if not current_data:
            raise ValueError("Weather provider returned no current observation")
        return {"available": True, "provider": "Open-Meteo", "observed_at": current_data.get("time"),
                "timezone": data.get("timezone"), "temperature_c": current_data.get("temperature_2m"),
                "humidity_percent": current_data.get("relative_humidity_2m"),
                "precipitation_mm": current_data.get("precipitation"), "rain_mm": current_data.get("rain"),
                "weather_code": current_data.get("weather_code"), "wind_speed_kmh": current_data.get("wind_speed_10m"),
                "rain_probability_percent": (daily.get("precipitation_probability_max") or [None])[0],
                "daily_precipitation_mm": (daily.get("precipitation_sum") or [None])[0],
                "coordinates_saved": False}
    except Exception as exc:
        logger.warning("Weather retrieval failed: %s", exc)
        raise HTTPException(503, "Current weather is unavailable. Check connectivity or enter your district manually.")


@app.post("/api/weather-recommend")
@app.post("/api/weather")
def weather_recommend(body: WeatherRequest, user=Depends(current)):
    context = {"district": body.district, "crop": body.crop, "pest": body.pest,
               "weather_summary": {"rain_probability": body.rain_probability,
                                   "humidity": body.humidity, "temperature_c": body.temperature_c}}
    result = answer("Assess weather-related crop risk and recommend only evidence-supported next steps.", context)
    result["weather"] = {"inputs": body.model_dump(), "demo": False, "source": "farmer-provided weather values"}
    return result


@app.post("/api/budget-optimize")
@app.post("/api/budget/optimize")
def budget_optimize(body: BudgetRequest, user=Depends(current)):
    query = f"Provide an actionable, itemized biological crop protection budget plan for {body.area_acres} acres of {body.crop or 'field crop'} within budget INR {body.budget} using ICAR biopesticide benchmarks (Trichocards, pheromone traps, Shatpada / Mycoguard microbial sprays, neem extracts). Include item quantities, estimated costs, and total investment."
    result = answer(query, body.model_dump())
    result["budget_context"] = {"budget": body.budget, "area_acres": body.area_acres}
    return result


@app.post("/api/outbreak-warning")
@app.post("/api/pests/outbreak")
def outbreak_warning(body: OutbreakRequest, user=Depends(current)):
    context = {"district": body.district, "crop": body.crop, "pest": body.pest,
               "reports_last_7_days": body.reports_last_7_days}
    query = f"Assess the biological pest risk level (High, Moderate, or Low) and Economic Threshold Levels (ETL) for {body.pest or 'pest'} in {body.crop or 'crop'} under ICAR guidelines. Provide definitive ETL values, actionable field scouting steps, and immediate biological interventions."
    result = answer(query, context)
    result["risk_assessment"] = {"available": result.get("available", False), "report_count_source": "farmer-provided"}
    return result


@app.post("/api/local-suppliers")
@app.post("/api/suppliers/local")
def local_suppliers(body: SupplierRequest, user=Depends(current)):
    context = {"district": body.district, "requested_product": body.product}
    result = answer("Find verified local availability only if retrieved sources contain it. Never invent supplier names, phone numbers, addresses, stock or prices. If no live supplier data exists, direct the farmer to the official local KVK/extension service.", context)
    result["suppliers"] = []
    result["live_supplier_data"] = False
    return result


@app.post("/api/pest-planner")
@app.post("/api/planner")
def pest_planner(body: PlannerRequest, user=Depends(current)):
    context = body.model_dump()
    result = answer("Create a crop-specific scouting and follow-up plan only from retrieved evidence. Do not invent treatment intervals or dose. Use the supplied start date only as the schedule anchor.", context)
    result["plan"] = result.get("recommended_actions", [])
    return result

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
def treatment_compatibility(body: CompatibilityRequest, user=Depends(current)):
    result = answer("Assess the requested treatment combination only if authoritative retrieved evidence explicitly addresses this combination, crop and use case. Never infer compatibility from product names alone.", {"requested_treatments": body.products})
    result["compatibility_confirmed"] = False if not result.get("available") else None
    return result
