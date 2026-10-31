# Agricultural data status — Version 5

## Current repository inventory

- Full verified ICAR/KVK/state agricultural university/FAO documents bundled: **0**.
- `data/documents/demo_dharwad_maize.txt`: present as a demo file but deliberately excluded from retrieval.
- `data/documents/sources.json`: contains three source leads, not local document copies; each is marked `verified: false` and its reuse terms need review.
- Current retrieval method: local TF-IDF lexical retrieval over verified manifest documents.
- Current neural embedding model / external vector database: none configured.
- Current source-derived knowledge graph relationships: none bundled; demo edges are not used for recommendations.

## Source leads already recorded

1. ICAR, *Handbook of Integrated Pest Management* — `https://www.icar.org.in/en/product/18`
2. ICAR Indian Farming, *Farmer-centric ICT-based approach for integrated pest management in India* — `https://epubs.icar.org.in/index.php/IndFarm/article/view/172442`
3. FAO, *Guidance on integrated pest management for the world's major crop pests and diseases* — `https://openknowledge.fao.org/items/7a20fe82-13ce-462c-8476-8267e8a5b71b`

These are leads only. The code does not claim that the files were downloaded, parsed, indexed, or checked for licensing.

## Current safety consequence

Until at least one relevant document is placed in `data/documents/`, given a complete source-manifest entry with `verified: true`, and successfully processed, the chatbot returns an evidence-unavailable response instead of treatment advice. This is intentional.

## Counts

Run `python scripts/check_corpus.py` or inspect `/api/system/status` and `/api/sources` after the server starts. The corpus status includes:

- `found_count`: supported files found on disk (excluding README/demo files)
- `processed_count`: files passing source verification and text extraction
- `indexed_chunk_count`: chunks currently indexed
- `rejected_count`: files excluded for missing/unverified/incomplete provenance
- `failed_count`: files with extraction errors, including scanned PDFs without OCR text

A file count is not a claim that the agricultural advice has been validated. Expert review and local-language review are still required.
