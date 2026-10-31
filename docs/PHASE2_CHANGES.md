# Phase 2 – what changed, what was tested, what is still open

## Root causes found
1. **No language selector:** the FastAPI dashboard (`frontend/modern-index.html`) never had one. Not a CSS/route bug.
2. **"IMAGE ANALYSIS UNAVAILABLE" + 0%:** the backend returns HTTP 200 with `live:false` whenever Gemini gives no result
   (no `GEMINI_API_KEY`, `GEMINI_ENABLED=false`, bad model id, network/quota error, or non-JSON reply). The old page drew that as
   a success panel and showed `confidence || 0` (a frontend default, not a model output).
   **Which of those causes applies on your machine is not yet known:** run the app, click Analyze, and read the terminal line
   `Gemini image analysis not attempted: ...` (new) or `Gemini image analysis unavailable: ...` (existing).
3. **Cards were independent demos:** nothing was saved, values were hard-coded (Maize / Fall Armyworm / Dharwad).

## Files
New: `frontend/dashboard-v2.html`, `static/app-v2.js`, `static/v2.css`, `static/i18n/{en,hi,kn,ta,te,ml,languages}.json`,
`tests/test_i18n_catalogs.py`, `tests/test_dashboard_v2.py`, `run_updated.py`, `run_updated_flask.py`, `.vscode/*`, `docs/*`.
Edited (originals in `backup_before_phase2/`): `backend/main.py` (serve new page at `/`, old page kept at `/classic`, `reason` field added to the
image-failure response), `backend/services/gemini.py` (`model_status()` + one log line; generation behavior unchanged).
Not touched: Flask app, auth, database schema, RAG/KG placeholders, all existing endpoints and response shapes.

## How the flow works now
Language screen (first visit) -> sign in / create account -> **Section A** (3 cards: Crop and soil, Farm size and budget, Your location; each with its own
Save, status text and validation) -> "Save field information and view recommendations" -> **Section B** (Ask Fieldwise, Photo diagnosis, Budget plan,
Pest risk check, Field plan, Treatment compatibility, Local suppliers, Field notes).
Section A is saved in the existing `users.context` JSON column via the existing `PUT /api/farmer/context` (no schema change). Section B reads it;
each card lists what it still needs and stays disabled until it has it. Changing crop/pest/district/area/budget marks earlier results "Outdated".

## Honest limitations (still true)
- Budget, risk, planner, compatibility and supplier logic are **sample rules in the backend**; the UI labels them "Sample rules – not real data".
  Suppliers always returns one "(sample)" entry. Risk uses a count the farmer types, and says it is not an official alert.
- The backend's chat gives **maize** advice for any question. The new page hides that answer when the saved crop/pest differ and shows a warning instead.
  Fixing it properly needs a real evidence base (needs your approval).
- **Advice text is English** (no translation service exists). Non-English UI shows a notice saying so. Photo-diagnosis details are English too.
- UI strings for hi/kn/ta/te/ml are **my drafts and must be reviewed by native speakers**, especially crop/stage/soil words. Pest names are deliberately left
  in English until verified local names are available.
- No automatic weather (no provider approved) and no GPS use; location is typed.
- Login token is still in `localStorage` (unchanged, needs approval to change). Unsaved form drafts are kept in `sessionStorage` and cleared on save/sign-out.
- Photo diagnosis does not send crop context to the model (endpoint takes only the file).
- Indic fonts: no remote fonts are loaded; the page relies on device fonts (Nirmala UI on Windows, Noto on Android). Not verified on real phones.

## Tests actually run
- 70 browser checks (Playwright/Chromium, 360x740 phone viewport) against a **stand-in server that mimics the API shapes**, using the real HTML/JS/CSS/catalogs: 70/70 passed.
  Covered: language-first flow and persistence, all six languages with no horizontal scroll, validation, draft survives refresh, save -> Section B data flow,
  stale-result invalidation, photo (non-image, shrink to 1600px, not-configured, model error, HTTP 500, success), crop-mismatch guard, sign-out, route guard, offline banner.
- `tests/test_i18n_catalogs.py`: 4/4 passed (run without pytest).
- **Not run:** the real FastAPI server and `tests/test_dashboard_v2.py` / existing tests (FastAPI cannot be installed in my sandbox), real Gemini calls,
  real phones/cameras, slow-network throttling, Indic font rendering.

## Run
```powershell
.venv\Scripts\python.exe run_updated.py      # http://127.0.0.1:8010   (old dashboard: /classic)
.venv\Scripts\python.exe -m pytest tests -v
```
Press Ctrl+F5 in the browser after restarting so the new JS/CSS load.
