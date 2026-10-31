# Version 5 implementation plan

## Baseline and canonical path

- Canonical app: FastAPI in `backend/main.py`, started by `python run.py`, served at `http://127.0.0.1:8000/`.
- Canonical dashboard: `frontend/dashboard-v2.html` plus `static/app-v2.js` and `static/v2.css`.
- Preserved classic dashboard: `/classic`, served by `frontend/modern-index.html` and `static/app-modern.js`.
- Preserved Flask prototype: `python run_complete.py` or `python app.py`; it is not the canonical FastAPI app.
- Existing language-first screen and its six language options are preserved.
- Existing baseline tests passed before edits: 15 tests. See the report for the post-change result.

## Confirmed issues addressed

1. FastAPI authentication used a JWT in browser `localStorage`; sessions could not be revoked server-side.
2. Registration accepted email only and passwords had an 8-character minimum.
3. The RAG modules were placeholders; the local corpus implementation was the only actual retrieval logic and did not require an explicitly verified source-manifest record.
4. PDF page provenance and ingestion/rejection counts were not reported.
5. Image uploads checked file signatures and size, but not whether the file decoded into a complete image or whether it was extremely dark/unclear.
6. Chat did not pass recent saved question/answer history into the generation context.
7. The KG route deliberately returned unavailable and demo edges were not safe evidence.
8. Setup and evidence-corpus instructions were contradictory across the README and audit.

## Planned implementation

- Add persistent server-side opaque sessions in an HttpOnly cookie while keeping bearer-token support for existing clients/tests.
- Support email or phone identifiers; hash passwords with PBKDF2-HMAC-SHA256 at 600,000 iterations and upgrade supported legacy hashes on successful login.
- Add login throttling, logout revocation, basic security headers, and migration-safe schema updates.
- Implement reusable RAG loader, cleaner, chunker, TF-IDF vectorizer, metadata filter, reranker, and source-gated local retrieval.
- Require an explicit `verified: true` source manifest record before a document can enter the recommendation corpus.
- Preserve PDF page numbers, report found/processed/indexed/rejected/failed counts, and keep the demo document excluded.
- Build knowledge-graph edges only from curator-entered relationships in verified source records; never use the old demo edges for advice.
- Perform non-destructive image validation/quality assessment and modest in-memory brightness/contrast enhancement; request a retake when an image is too unclear.
- Include recent farmer conversation turns in bounded chat context.
- Document all remaining blockers rather than fabricating external data or service results.

## Explicit non-goals / approval gates

- No model fine-tuning, new paid service, external SMS/email provider, or replacement database.
- No download or redistribution of agricultural publications without checking permission.
- No generated prices, supplier stock, weather, treatment dosage, or disease confidence scores.
- No redesign of the language-selection screen.

## Acceptance checks

- `python -m pytest -q`
- `python -m py_compile backend/main.py backend/services/rag/*.py backend/services/image_quality.py knowledge_graph/evidence_graph.py`
- `node --check static/app-v2.js`
- `node --check static/app-modern.js`
- Check `/health`, `/api/system/status`, registration/login/logout, phone/email identifiers, empty corpus behavior, image rejection/triage, and source-manifest filtering.

## Decisions requiring external input

- Authorized ICAR/KVK/State Agricultural University documents and reuse rights.
- Gemini API key and confirmation of vision/model access.
- Email or SMS provider if password reset or phone OTP is required.
- Human review of crop-specific claims, graph relationships, and translations.
