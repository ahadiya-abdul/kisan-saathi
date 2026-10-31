# Kisan Saathi / Fieldwise — Version 5

An existing farmer-facing advisory application with a FastAPI dashboard, multilingual UI, persistent farmer profiles, evidence-first RAG, and a source-provenance-aware knowledge-graph interface. The original UI branding is preserved.

## Run the canonical app

Python 3.11+ is recommended. From the extracted project folder:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

Open `http://127.0.0.1:8000/`.

For macOS/Linux, use `python3 -m venv .venv`, `source .venv/bin/activate`, `cp .env.example .env`, and then the same pip/run commands.

## Authentication

- Register or sign in using either an email address or a phone number.
- New passwords must be at least 12 characters.
- Passwords are stored as PBKDF2-HMAC-SHA256 hashes (600,000 iterations).
- The canonical dashboard uses an opaque, revocable, server-side session token in an HttpOnly SameSite=Lax cookie; it does not store the session credential in browser localStorage.
- Sessions expire after 30 days; logout revokes the current session.
- Legacy bearer authentication is still supported for compatibility with existing clients.
- Configure HTTPS and `FIELDWISE_COOKIE_SECURE=1` in production. Do not use a predictable secret.
- Phone ownership verification and password recovery are not implemented until a real SMS/email provider is configured.

## Agricultural evidence and RAG

The local retrieval pipeline reads authorized PDF/TXT/Markdown documents, extracts and chunks text, preserves PDF page numbers, builds a TF-IDF lexical index, filters/reranks results using farmer context, and passes the actual retrieved passages to Gemini when configured. This is RAG, not fine-tuning. It is **not** a neural embedding model or external vector database.

Only documents with a matching `data/documents/sources.json` entry containing `verified: true`, title, source, and HTTPS URL are eligible. Demo files and unverified source leads are excluded. This ZIP includes **zero verified full agricultural documents**, so the chatbot intentionally declines to recommend a treatment until authorized documents are added and reviewed. See:

- `data/documents/README.md`
- `docs/AGRICULTURAL_DATA_STATUS.md`
- `docs/DECISION_LOG.md`
- `docs/KNOWN_LIMITATIONS.md`

## Configure Gemini (optional)

Edit `.env` and set `GEMINI_API_KEY`. The default model setting is `gemini-2.5-flash`; confirm model access in your Google AI account. Without credentials or if the service fails, the app should report unavailability rather than fabricate advice.

## Verify the project

```powershell
python -m pytest -q
python scripts/check_corpus.py
```

- Health: `http://127.0.0.1:8000/health`
- Runtime status: `http://127.0.0.1:8000/api/system/status`
- Source register: `http://127.0.0.1:8000/api/sources`

## Other preserved entry points

- `python run_updated.py`: alternate FastAPI port 8010.
- `python run_complete.py` or `python app.py`: preserved Flask prototype on port 5000.
- `/classic`: previous FastAPI dashboard.

Use `python run.py` for normal development. The Flask prototype is a separate application; do not confuse its routes or database/auth behavior with the canonical app.

## Version 5 documents

- `docs/IMPLEMENTATION_PLAN.md` — audit and planned scope
- `docs/DECISION_LOG.md` — why key decisions were made
- `docs/IMPLEMENTATION_REPORT.md` — implementation status and verification
- `docs/SETUP_AND_RUN.md` — detailed setup commands
- `docs/AGRICULTURAL_DATA_STATUS.md` — what agricultural data is and is not included
- `docs/KNOWN_LIMITATIONS.md` — incomplete items and deployment risks
