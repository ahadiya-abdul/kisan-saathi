# Agricultural evidence source register

Use these official/reputed sources to obtain crop-specific documents. The application only uses local files that you add to `data/documents/`; these links alone are not treated as retrieved evidence.

1. **ICAR — Handbook of Integrated Pest Management**
   https://www.icar.org.in/en/product/18
2. **ICAR Indian Farming — Farmer-centric ICT-based approach for integrated pest management in India**
   https://epubs.icar.org.in/index.php/IndFarm/article/view/172442
3. **FAO — Guidance on integrated pest management for the world's major crop pests and diseases**
   https://openknowledge.fao.org/items/7a20fe82-13ce-462c-8476-8267e8a5b71b
4. **FAO — Integrated Pest Management overview**
   https://www.fao.org/pest-and-pesticide-management/ipm/integrated-pest-management/en/
5. **ICAR publications catalogue**
   https://icar.org.in/en/all-publications

Prioritize current, crop-specific, region-specific packages of practices from ICAR institutes and the relevant Krishi Vigyan Kendra (KVK), especially for Karnataka and the farmer's district. Confirm document date, crop/variety coverage, geography, licensing and intended use before ingesting it.

Do not ingest search result snippets or unverified internet text as if it were a complete paper. Record title, issuing institution, date/version and source URL in `data/documents/sources.json`. Where advice differs across regions or years, keep both sources and require the model to explain the difference instead of silently selecting one.
