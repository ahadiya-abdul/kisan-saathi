# Setup and run — Version 5

## Requirements

- Python 3.11+ recommended.
- Internet access only for installing dependencies, Gemini requests, and the existing Open-Meteo weather adapter.
- A Gemini API key is optional for startup but required for live LLM and image analysis.

## Windows PowerShell

From the extracted `kisan-saathi-version-5` project directory:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set `GEMINI_API_KEY` if you have one. Keep secrets out of source control. `GEMINI_ENABLED=true` enables the configured integration; without a key, the app should report model unavailability rather than invent an answer.

Run the canonical FastAPI application:

```powershell
python run.py
```

Open `http://127.0.0.1:8000/`.

## macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python run.py
```

## Verify

- Health: `http://127.0.0.1:8000/health`
- System/model/corpus status: `http://127.0.0.1:8000/api/system/status`
- Source register and corpus status: `http://127.0.0.1:8000/api/sources`
- Run tests: `python -m pytest -q`
- Check corpus: `python scripts/check_corpus.py`

## Production security notes

- Set `FIELDWISE_JWT_SECRET` to a unique random value of at least 32 bytes for legacy bearer-token compatibility.
- Set `FIELDWISE_SECRET_KEY` separately for the preserved Flask prototype.
- Set `FIELDWISE_COOKIE_SECURE=1` only when the FastAPI app is served over HTTPS.
- Use HTTPS, backups, a managed database, centralized rate limiting, monitoring, and a reviewed CSRF/deployment configuration before public deployment.
- Cookie sessions expire after 30 days and logout revokes the current server-side session.
- Password recovery and phone OTP are not available until a real provider and verification flow are configured.

## Alternative entry points

- `python run_updated.py` is a preserved alternate FastAPI port (`8010`), not required for normal use.
- `python run_complete.py` or `python app.py` starts the preserved Flask prototype (`5000`). Its routes and authentication implementation are separate from the canonical FastAPI app. Do not confuse the two when reporting bugs.
- `/classic` serves the previous FastAPI dashboard.
