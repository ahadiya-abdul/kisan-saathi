# Known limitations — Version 5

1. **No authoritative crop documents are bundled.** The corpus has zero verified documents; the chatbot should not provide a treatment recommendation until reviewed sources are added.
2. **RAG is lexical TF-IDF.** It is a real retrieval step, but it is not neural semantic embedding, not a dedicated vector database, and may miss paraphrases or cross-language terms.
3. **Knowledge graph is an empty framework until populated.** Only curator-entered relationships attached to verified source records are loaded. The graph does not infer relationships automatically.
4. **Gemini is not live-tested in this package.** A valid API key, network access, and model access are required. API outages return an unavailable result.
5. **Image analysis requires the configured vision model.** Quality metrics are heuristics, not diagnosis. Enhancement is non-destructive and only performed in memory.
6. **Soil photos cannot provide lab measurements.** pH, nutrients, salinity, and exact moisture require suitable tests/instruments.
7. **Password recovery and phone OTP are not implemented.** No SMS/email provider is configured; the app must not claim to send verification codes.
8. **No verified biocontrol prices or supplier inventory are bundled.** Do not treat demo records or a generic biological organism as a currently available commercial formulation.
9. **Voice input/output is not implemented end-to-end in the canonical dashboard.** Use text until a supported speech service and tests are added.
10. **Translations are not professionally validated.** The six existing language catalogs are retained and auth/error text has been extended, but a native speaker should review farmer-facing agricultural content.
11. **Deployment hardening remains necessary.** Configure HTTPS, secure cookies, strong secrets, backups, central rate limiting, observability, and a production database before public launch.
12. **Preserved Flask prototype is a separate application.** It has a different startup command and auth/database assumptions; use the canonical FastAPI entry point unless intentionally testing the prototype.
