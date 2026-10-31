# Version 5 decision log

Dates use the project build date, 2026-10-30.

## D-001 — Keep FastAPI as canonical
- **Requirement:** preserve architecture and existing working functionality.
- **Evidence:** `README.md`, `run.py`, and `backend/main.py` identify the FastAPI app as canonical; Flask remains a separate prototype.
- **Decision:** modify the canonical FastAPI path and keep the classic page/prototype available.
- **Alternatives:** consolidate Flask and FastAPI; rejected because it would be a risky architecture replacement.
- **Files:** `backend/main.py`, `static/app-v2.js`, `static/app-modern.js`, `frontend/dashboard-v2.html`, `frontend/modern-index.html`.
- **Test:** application route tests and JS syntax checks.
- **Limitations:** the separate Flask prototype is preserved and has its own auth/session implementation.

## D-002 — Use revocable HttpOnly cookie sessions
- **Requirement:** persistent login without storing passwords/tokens in browser localStorage.
- **Evidence:** old canonical frontend stored a bearer JWT in localStorage; old token had no server-side revocation.
- **Decision:** create opaque random session tokens, store only SHA-256 token digests in SQLite, set an HttpOnly SameSite=Lax cookie, expire after 30 days, and delete the session on logout. Keep bearer auth compatibility for existing clients.
- **Alternatives:** keep localStorage JWT; rejected due exposure to script injection and no revocation. Replace JWT for all clients immediately; rejected to preserve compatibility.
- **Files:** `backend/main.py`, `static/app-v2.js`, `static/app-modern.js`.
- **Security:** configure `FIELDWISE_COOKIE_SECURE=1` only behind HTTPS. SameSite=Lax and Origin checks provide baseline CSRF mitigation; production review is still required.
- **Test:** phone session create, restore, login, logout, and expired/unauthenticated behavior.
- **Limitations:** password reset and OTP are not implemented without a verified email/SMS provider.

## D-003 — Raise password hashing cost and support phone identifiers
- **Requirement:** email or phone plus password.
- **Evidence:** canonical schema/login supported email only; existing hashes used a lower iteration count.
- **Decision:** support either email or phone; use PBKDF2-HMAC-SHA256 with 600,000 iterations for new passwords; upgrade recognized legacy hashes after successful login; add phone column and a guarded migration for old NOT NULL email schemas.
- **Alternatives:** replace database/auth library; rejected as unnecessarily disruptive.
- **Files:** `backend/main.py`, auth fields in `frontend/dashboard-v2.html` and `frontend/modern-index.html`, translation catalogs.
- **Test:** existing email tests and new phone account tests.
- **Limitations:** phone ownership is not verified; do not treat a phone number as verified identity until an OTP provider is configured.

## D-004 — Only verified source-manifest documents may support advice
- **Requirement:** evidence-grounded RAG and no fabricated agricultural facts.
- **Evidence:** repository had source leads but no bundled authoritative documents; the previous local corpus accepted any non-demo document.
- **Decision:** require a manifest record with `verified: true`, title, source, and HTTPS URL; retain source/page metadata; report rejected/failed documents; keep demo documents excluded.
- **Alternatives:** auto-trust all PDFs or download source leads automatically; rejected due licensing and provenance risk.
- **Files:** `backend/services/rag/*`, `data/documents/README.md`, `data/documents/sources.json`, `scripts/check_corpus.py`.
- **Test:** manifest gating test and existing empty-corpus tests.
- **Limitations:** no verified source PDFs are included, so the app correctly does not produce agronomic recommendations yet.

## D-005 — Implement lexical RAG rather than claim neural embeddings
- **Requirement:** actual retrieval and evidence passed to the LLM.
- **Evidence:** no configured embedding model/vector database was present; scikit-learn was already a dependency.
- **Decision:** use TF-IDF lexical vectorization with cosine similarity, bounded word chunks, context metadata filtering, and transparent relevance scores. Pass retrieved text and curated KG facts to Gemini.
- **Alternatives:** add a new embedding provider/vector database; deferred pending approval, credentials, and evaluation.
- **Files:** `backend/services/rag/*`, `backend/services/gemini.py`, `backend/main.py`.
- **Test:** source-gated retrieval and no-corpus safety tests.
- **Limitations:** lexical retrieval may miss paraphrases and multilingual queries; neural embeddings/reranking remain future work.

## D-006 — Build KG only from curated relationships
- **Requirement:** use KG relationships with provenance.
- **Evidence:** prior graph edges were hard-coded demo edges and not appropriate as agronomic evidence.
- **Decision:** ignore demo edges for advice; load only relationships in verified source records with a source excerpt and document provenance.
- **Files:** `knowledge_graph/evidence_graph.py`, `backend/main.py`, `backend/services/gemini.py`, corpus docs.
- **Test:** import/syntax checks and empty graph behavior.
- **Limitations:** no verified relationship data is bundled, so KG remains empty until a curator adds supported relations.

## D-007 — Preserve original images and use cautious enhancement
- **Requirement:** image quality check and image analysis.
- **Evidence:** previous endpoint validated declared type/signature/size but did not check complete image decoding or quality.
- **Decision:** use Pillow to decode and estimate brightness, contrast, and edge detail; reject invalid/oversized images; modestly enhance an in-memory copy when helpful; ask for a retake for severely unclear images; never write the upload to disk.
- **Files:** `backend/services/image_quality.py`, `backend/main.py`, `static/app-v2.js`, translations, tests, requirements.
- **Test:** real image fixtures and invalid-image rejection.
- **Limitations:** image quality heuristics are approximate; visual triage still needs a configured vision-capable model and human review.

## D-008 — Include bounded recent conversation context
- **Requirement:** continuity across sessions.
- **Evidence:** chat records were persisted per user, but previous turns were not supplied to the generation context.
- **Decision:** include up to six recent question/answer pairs, bounded in length, for the same authenticated user.
- **Files:** `backend/main.py`.
- **Test:** existing per-user context isolation tests.
- **Limitations:** context is recent history, not a validated long-term agronomic memory; farmers must update crop/field details when they change.
