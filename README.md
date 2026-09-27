# Fieldwise - Localized Biocontrol Advisory

A standalone Flask MVP aligned to the Phase 2 presentation: a context-aware RAG + KG assistant for localized, affordable biocontrol advice for Indian smallholders.

## Run locally

From the project directory:

```powershell
cd "C:\Users\Asus\OneDrive\Desktop\biocontrolchatbot"
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Open <http://127.0.0.1:5000>.

## Which server should I run?

FastAPI is the canonical app and the preserved Flask prototype remains available separately:

- **Canonical FastAPI app:** `python run.py` → `http://127.0.0.1:8000/`
- **Preserved Flask prototype:** `python run_complete.py` → `http://127.0.0.1:5000/login`

Run the canonical app with:

```powershell
cd "C:\Users\Asus\OneDrive\Desktop\biocontrolchatbot"
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

Then open <http://127.0.0.1:8000/>.

## Secure authentication

- Visit `/login` and create an account with a password of at least 12 characters.
- Passwords are stored as Werkzeug PBKDF2 password hashes, never plaintext.
- Login, registration, logout, and chat requests use CSRF tokens.
- Sessions use HTTP-only, SameSite cookies and expire after 30 minutes.
- Failed logins are throttled per client IP.
- Protected pages and APIs require an authenticated session.
- Security response headers are added by the application.

For production, set a strong secret and serve the app behind HTTPS:

```powershell
$env:FIELDWISE_SECRET_KEY = "generate-a-long-random-secret-outside-the-repository"
$env:FIELDWISE_COOKIE_SECURE = "1"
python app.py
```

`FIELDWISE_COOKIE_SECURE=1` must only be used when the site is actually served over HTTPS. A production deployment should also put the app behind a reverse proxy with TLS, use a managed database and backups, and add centralized rate limiting/WAF controls for multiple server instances.

## What is included

- Responsive farmer-facing chat page with district, crop, pest, soil, crop-stage, budget, and language context.
- Context-weighted retrieval over seeded ICAR/KVK-style advisory records.
- Biocontrol-first scoring using cost and local availability/distance.
- SQLite persistence for farmer questions and context.
- Crop-pest-biocontrol graph paths shown beside each answer.
- Evidence cards with source, confidence, cost, and distance metadata.
- Weather and local-market signal panels ready for live API adapters.
- Multilingual and multimodal/voice integration seams in the UI and API contract.

The current demo uses deterministic retrieval and seeded records so it runs without API keys. The `retrieve`, `graph_for`, and `build_answer` functions in `app.py` are the seams for connecting ICAR/KVK document embeddings, NetworkX, an LLM, IMD weather, AGMARKNET prices, image diagnosis, and WhatsApp/SMS/voice delivery in the next iteration.
