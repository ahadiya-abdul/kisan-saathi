> **Historical baseline audit (pre-Version 5).** The findings below describe the repository before the Version 5 changes. Consult `IMPLEMENTATION_REPORT.md` and `AGRICULTURAL_DATA_STATUS.md` for current status; not every item from the original proposal is complete.

# Fieldwise — Stage A Audit and Proposal (no application code edited)

Scope of this copy: the only additions are `run_updated.py`, `run_updated_flask.py`, `.vscode/`, and this `docs/` folder.
No existing file was modified, deleted, or renamed. No database was created or touched.

## 1. Entry points

| | Command | URL | Serves |
|---|---|---|---|
| Canonical (per README) | `python run.py` | :8000 | `backend/main.py` (FastAPI) → `frontend/modern-index.html` + `static/app-modern.js` |
| Preserved prototype | `python run_complete.py` / `python app.py` | :5000 | `app.py` (Flask) → `templates/index.html` (**the UI in your screenshot**) |
| This copy | `python run_updated.py` | :8010 | same FastAPI app, different port |
| This copy (prototype) | `python run_updated_flask.py` | :5010 | same Flask app, different port |

The README opens with Flask instructions and later says FastAPI is canonical. The screenshot is the Flask UI.
Both servers point at the same SQLite file name (`fieldwise.sqlite3` in the project root) but use incompatible
password-hash formats (Werkzeug vs. hand-rolled `salt:hex`), so accounts do not carry over between them.

## 2. Findings that matter before any redesign

1. **There is no RAG pipeline.** Every file in `backend/services/rag/*` and `knowledge_graph/*` is a one-line placeholder
   docstring. `data/documents/demo_dharwad_maize.txt` is not read by any code.
   - Flask "retrieval" = keyword/context scoring over 5 hard-coded records in `app.py`.
   - FastAPI "retrieval" = one hard-coded `ADVICE` dict; `/api/retrieve` returns it for every question.
2. **Knowledge graph is demo-only**: 8 edges in `app.py`, 7 edges in `backend/main.py`. Not built from data.
3. **Canonical FastAPI `/api/chat` gives maize / fall-armyworm / Trichogramma advice for every question**
   (confidence just drops to 0.72 when Dharwad+maize+armyworm are not all mentioned). A cotton or tomato question gets maize advice.
   This is a safety problem for the "never give confident advice on weak evidence" requirement.
4. **The screenshot UI's chat is not wired up in this snapshot.** `templates/index.html` has `#chatForm` / `#messageInput`,
   but no JS file in the repo references them. `static/app.js` (loaded by that template) targets the FastAPI page
   (`#authForm`, `#auth`, `#app`, `#logout`), none of which exist in the Flask template, so it throws on load. Verified by checking element IDs.
   (The Flask `/api/chat` endpoint itself works — see section 6.)
5. **Language is not implemented.** `services/translation.py` is a placeholder. Flask stores `language` in context but the
   answer is always English (tested with Hindi selected). FastAPI ignores it.
6. **Weather is fake-live.** Flask `/api/chat` always returns "Warm and partly cloudy, 68%" with no provider and no
   demo label in the UI. FastAPI `/api/weather-recommend` uses caller-supplied numbers (defaults 35% / 65% / 28 °C), labelled `demo: true`.
7. **Image analysis is crop-pest triage, not soil.** `/api/image-analyze` calls Gemini only if `GEMINI_API_KEY` is set;
   otherwise returns "IMAGE ANALYSIS UNAVAILABLE". It is unauthenticated, reads the whole upload into memory before checking size,
   trusts the declared content-type (no magic-byte check), and sends the image to Google.
8. **FastAPI auth vs. your security requirements**
   - JWT bearer stored in `localStorage` (you require no tokens in localStorage). 12-hour expiry, no revocation/logout on server.
   - Falls back to a hard-coded secret `demo-only-change-this-secret-32-bytes` if `FIELDWISE_JWT_SECRET` is unset.
   - PBKDF2-SHA256 at 180,000 iterations (below current OWASP guidance of ~600,000); hash written to both `password` and `password_hash` columns.
   - No login rate limiting; register returns 409 "Email already registered" (account enumeration); login skips hashing when the user does not exist (timing difference).
   - Min password 8 chars; no security headers; no CSRF (not needed for bearer, but needed once cookies are used).
   - Only 4 of ~21 route handlers require auth (`/me`, `/chat`, `/farmer/context`, `/farmer/dashboard`).
     Unauthenticated: image-analyze, retrieve, recommend, weather, budget, outbreak, suppliers, planner, compatibility, kg, catalogues.
9. **Flask auth is closer to your requirements** (server session, HttpOnly + SameSite cookie, CSRF, per-IP throttle, 12-char minimum,
   security headers) but: random `SECRET_KEY` per process if env var unset (sessions die on restart), per-IP-only throttle,
   and the `conversations` table has **no user_id** (questions are logged anonymously and cannot be tied to a farmer).
10. **Config drift.** `.env.example` lists `SECRET_KEY, JWT_SECRET_KEY, DATABASE_PATH, LLM_PROVIDER, LLM_API_KEY, ALLOWED_ORIGINS`;
    none are read. Code actually reads `FIELDWISE_JWT_SECRET, FIELDWISE_SECRET_KEY, FIELDWISE_COOKIE_SECURE, GEMINI_API_KEY, GEMINI_ENABLED, GEMINI_MODEL`.
    Default model id `gemini-3.6-flash` — I cannot verify that this id exists; please confirm it against your Google AI console.
11. `pandas`, `numpy`, `scikit-learn`, `httpx`, `pydantic-settings` are in `requirements.txt` but never imported by app code.
12. Silent failure: `generate_advice` swallows all exceptions and returns `None`, so a Gemini outage or bad key looks identical to "offline mode" without any log line.

## 3. Feature inventory (what actually works)

| Feature | Where | Status |
|---|---|---|
| Register / login / me | `backend/main.py`; `app.py` | Functional; weaker than required (see 8, 9) |
| Chat advisory | `backend/main.py:answer`; `app.py:build_answer` | Hard-coded demo logic; Gemini wording layer optional, untested by me |
| RAG (ingest, embed, retrieve, rank, filter) | `backend/services/rag/*` | **Not implemented** (placeholders) |
| Knowledge graph | `knowledge_graph/*`; inline edges | **Demo only** |
| LLM (Gemini) | `backend/services/gemini.py` | Real integration, needs key; not tested here |
| Translation / voice | `services/translation.py`, `voice.py` | **Not implemented** |
| Weather | `/api/weather*`; Flask chat | **Mock / caller-supplied inputs** |
| Budget, outbreak, suppliers, planner, compatibility | `backend/main.py` | Demo-flagged hard-coded rules |
| Image analysis | `/api/image-analyze` | Real Gemini call if key set; crop triage only |
| Farmer records | `users.context` (JSON blob), `chats` (question, answer) | Minimal; no farm/crop/plot model, no language/source stored |
| Tests | `tests/` (6 FastAPI tests) | None for Flask |

## 4. Proposed structure (pending your approval)

Build on the canonical FastAPI app. Keep Flask untouched. Add routes in the currently empty `backend/api.py`, included from `main.py` with a 2-line change.

Pages: `/language` → `/auth` (sign in / register tabs as two routes) → `/setup/farm` → `/setup/crop` → `/setup/weather` → `/setup/soil` → `/setup/summary` → `/ask` → `/answer/{id}` → `/home` (+ `/settings`).
Progress is saved server-side per step (additive tables: `farms`, `crops`, `weather_obs`, `soil_assessments`, `user_prefs`; created with `CREATE TABLE IF NOT EXISTS`, no migration of existing tables). Language is kept in a first-party cookie (no personal data) and copied to the account after sign-in.
New API (additive): `/api/profile`, `/api/farms`, `/api/crops/mine`, `/api/weather/current`, `/api/soil/analyze`, `/api/i18n/{lang}`, `/api/account` (export/delete).
Existing endpoints and response shapes stay as they are.

Files that would change: `backend/main.py` (include routers; safety gate if approved), `backend/api.py`, `backend/auth.py`, `backend/database.py`, `backend/config.py`, `backend/schemas.py`, `backend/services/translation.py`, `static/*` (new small CSS/JS, no framework), new `frontend/pages/*` and `locales/*.json`, `tests/*`.

## 5. Decisions that need your approval

1. **Base app:** confirm FastAPI (`run.py`) is what you actually use, since your screenshot is the Flask UI.
2. **Auth change:** add HttpOnly SameSite cookie sessions + CSRF to FastAPI, keeping bearer JWT working for tests/API clients; remove localStorage use in new pages. Add login throttling, generic error messages, secret-from-env (fail to start in production without one). Password hashing: `hashlib.scrypt` (no new dependency) with versioned hashes and re-hash on next login, or `argon2-cffi` (new dependency).
3. **Sign-in identifier:** today it is email only. Phone login needs an SMS/OTP provider (cost, DLT registration in India). Recommendation: email now.
4. **Password reset:** needs an email provider (SMTP or API). I will not build a fake reset. Provide provider + credentials, or defer.
5. **Weather provider:** none exists. Candidates: Open-Meteo (no key; I would verify its terms and limits before you choose), OpenWeatherMap (key, free tier), IMD (needs separate access). Existing weather endpoint stays; new `/api/weather/current` feeds it.
6. **Multilingual answers:** no translation service exists. Options: (a) Gemini responds in the selected language from the same evidence (no new vendor; quality on agricultural terms unverified), (b) Bhashini / Google Cloud Translation (registration or billing). UI strings: I can draft catalogues for the six languages but they must be reviewed by native speakers; I will not call them verified.
7. **Soil photo:** the current endpoint is not a soil model. Options: (a) add a separate soil prompt to the existing Gemini integration + client-side quality checks (blur, brightness, size), results labelled as visual observation only, never driving fertilizer or biocontrol advice; (b) trained soil classifier (needs dataset, training, hosting); (c) no ML, photo kept as a record plus farmer-chosen soil type and a pointer to a Soil Health Card test via KVK. Recommendation: (a) with strict wording, or (c) if you want zero accuracy risk. pH, nutrients, salinity, organic carbon, and exact moisture cannot come from a photo.
8. **RAG / knowledge graph:** your brief says to preserve them, but they do not exist beyond placeholders. Building them is a new core feature: loader → chunker → retriever (TF-IDF with scikit-learn, already in requirements, no cost or key; or embeddings API) and a graph built from data. Needs a real, licensed ICAR/KVK corpus; today there is one 248-byte demo note.
9. **Safety gate on advice:** change `/api/chat` so that when the crop/pest/district is not covered by evidence it says "not enough verified evidence, consult KVK" instead of returning maize advice. Changes current behavior (and one existing test's assumptions).
10. **New dependencies (only if approved):** `jinja2` (server-rendered pages) or none (static pages + small vanilla JS); `Pillow` (server-side image validation); `argon2-cffi` (optional).
11. **PWA / offline:** minimal service worker caching static assets only, `no-store` on all API/personal responses. Defer unless you want it.

## 6. Baseline test results

- `pytest` **could not be run** in my environment: no network, so `fastapi`, `uvicorn`, `httpx`, `pytest`, `google-genai` could not be installed. The 6 existing tests are FastAPI-only. Please run `pytest tests -v` locally and send me the output; I am recording it as "unknown" until then.
- What I did run: Flask smoke test in a throwaway copy — `/login` 200, register 302, `/` 200 after register, `/api/chat` 200 with 3 sources and 3 graph edges; with language = Hindi the answer contained no Devanagari text.
- Not run: FastAPI server, Gemini (no key/network), any browser rendering.

## 7. Testing plan (Stage C)

Auth (register/login/logout/throttle/session expiry/cross-account access), language persistence, onboarding resume after refresh, crop add/edit without overwrite, geolocation denied/timeout/provider down (provider mocked), image validation (type, size, magic bytes, corrupt file), uncertain-result handling, advice gate, source attribution, plus manual checks on a real low-end Android phone and throttled network. Translation quality, camera behavior, weather accuracy, and model accuracy will be reported as untested unless done.

## 8. Run in Visual Studio / VS Code

```powershell
cd bio-py-repo-updated
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run_updated.py        # http://127.0.0.1:8010
.venv\Scripts\python.exe run_updated_flask.py  # http://127.0.0.1:5010 (prototype)
```
Change the port with `$env:FIELDWISE_PORT = "8020"`. In VS Code, use Run and Debug → "Fieldwise (updated) - FastAPI :8010".
Optional Gemini: create `.env` with `GEMINI_API_KEY=...` (never commit it).
