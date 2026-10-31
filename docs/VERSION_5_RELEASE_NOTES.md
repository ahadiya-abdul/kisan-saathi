# Version 5 release notes

## Added
- Revocable, persistent HttpOnly cookie sessions for the canonical FastAPI UI.
- Email-or-phone identifier for registration/login and stronger password hashing.
- Per-IP login throttling and baseline security headers.
- Source-manifest-gated TF-IDF RAG with text cleaning, chunking, page provenance, contextual filtering/reranking, and corpus status counts.
- Curated knowledge-graph relationship loader with source provenance.
- Image decoding/quality checks, non-destructive in-memory enhancement, and retake guidance for severely unclear images.
- Bounded recent chat context for multi-turn continuity.
- Implementation plan, decision log, setup guide, data status, report, and known limitations.

## Preserved
- Existing language-first selector and six language choices.
- Existing dashboard design and FastAPI canonical entry point.
- Existing Flask prototype, classic dashboard route, weather adapter, and existing route contracts where possible.

## Important limitations
- No verified agricultural source documents are bundled.
- Gemini, voice services, password recovery, phone OTP, and live supplier pricing are not verified/configured end-to-end.
- TF-IDF retrieval is lexical, not neural semantic embedding.
- No live agronomic recommendation should be relied on until the corpus and localized outputs are reviewed by agricultural experts.
