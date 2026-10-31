# Phase 3 — evidence-first farmer decisions

## Implemented in this folder

- Removed the hard-coded maize / fall-armyworm advisory from the FastAPI advisor path.
- Added local document retrieval over legally obtained PDF, TXT and Markdown sources. `demo_*` documents and `data/documents/README.md` are excluded.
- Added a source manifest and official source leads for ICAR and FAO. These are links only; the actual publications are not bundled or claimed to be ingested.
- Updated the Gemini prompt to use retrieved passages, return native-script advice, cite only retrieved source IDs, avoid unsupported doses/prices/suppliers, and disclose uncertainty.
- If there is no relevant corpus evidence or the LLM does not return a validated response, the API returns a localized evidence-unavailable message instead of a sample answer.
- Moved photo collection/analysis into Section A so the first three cards collect crop/photo evidence, budget/field size, and location/weather. Section B contains decision-making actions. Removed the manual pest/control selection from the form; farmers can optionally describe symptoms in their own question.
- The dashboard's main advice and decision cards send the farmer's saved crop, stage, soil observation, field area, budget, location, weather snapshot, selected language and current-session image findings to the advisor. Farmers no longer have to choose a control method in the compatibility card.
- Replaced sample budget/risk/planner/compatibility logic with evidence-grounded advisor requests. Local supplier search does not invent a supplier list.
- Added an authenticated Open-Meteo weather endpoint. Browser GPS coordinates are used for the request only and are not persisted; the returned weather snapshot can be saved to the farmer's field context.
- Image analysis now requires authentication, passes crop/stage/language context to Gemini, checks the image signature and size, and does not fabricate a confidence score on failure. Farmers can choose plant-photo triage or soil-surface observation; soil photos are explicitly not treated as lab tests.
- Added `/api/system/status` and `scripts/check_corpus.py` for diagnosing model/corpus readiness.
- Updated language catalogs and script-specific system font stacks for Hindi, Kannada, Tamil, Telugu and Malayalam.

## Important limitations (do not misrepresent these)

1. This implementation uses RAG, not fine-tuning. It does not train a new model. Training/fine-tuning would require a separate approved dataset, rights review, training infrastructure, evaluation sets and deployment process.
2. The folder does not include full ICAR/FAO papers. The source list contains official links only. Add legally obtained crop-specific PDFs/TXT/MD files to `data/documents/` and list their metadata in `sources.json` before expecting evidence-grounded recommendations.
3. The demo note `demo_dharwad_maize.txt` is intentionally excluded and cannot be used to produce advice.
4. Until real crop-specific documents are added, the advisor correctly refuses to provide a treatment recommendation. This is intentional and satisfies the no-sample-answer requirement.
5. A general multimodal LLM is not a validated crop-disease classifier. Image output is preliminary triage, not a definitive diagnosis. Do not infer soil pH/nutrients/salinity from an image.
6. Open-Meteo requires internet access and location permission. GPS may fail or be denied. The code does not claim that weather retrieval works offline.
7. The knowledge graph in the original repository is demo-only. Demo edges are no longer used as evidence for decisions; a validated graph built from source-derived facts remains future work.
8. Supplier availability, real-time market prices, and official local outbreak surveillance are not integrated. The app must not fabricate them.
9. The six language catalogs are UI drafts and need native-speaker review for agricultural terminology before production deployment.
10. The browser still uses the existing bearer token storage mechanism. A stronger HttpOnly-cookie migration remains a separate security change and should be completed before public production deployment.

## Run

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt --timeout 180 --retries 10
.venv\Scripts\python.exe run_updated.py
```

Open `http://127.0.0.1:8010` and use Ctrl+F5 after restarting. Check `http://127.0.0.1:8010/api/system/status` to see whether the LLM is configured and whether usable documents have been loaded. Run `python scripts/check_corpus.py` to inspect the local corpus.

## Test status

Syntax and static checks were run while preparing this package. Automated tests run in this build: `python -m pytest tests -q` → 15 passed. Language catalog tests: 4 passed. Python compilation and JavaScript syntax checks passed. Real Gemini/Open-Meteo requests, native-speaker translation review, and model accuracy were not tested. No 10x speed or accuracy improvement is claimed.
