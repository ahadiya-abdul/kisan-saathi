# Agricultural evidence corpus (Version 5)

The canonical FastAPI advisor uses a local, source-registered RAG pipeline. It reads permitted PDF/TXT/Markdown files, extracts text, chunks it, creates a local TF-IDF lexical index, retrieves relevant passages, applies conservative crop/pest metadata filtering, and passes the actual passages to the configured Gemini model. This is retrieval augmentation, **not model fine-tuning**. The current implementation does not use a neural embedding model or an external vector database.

## Add an authorized document

1. Obtain the document from an official publisher or repository and confirm that downloading, local processing, and any intended redistribution are permitted.
2. Put the PDF, TXT, or Markdown file in this directory. Keep the filename stable.
3. Add a matching entry to `sources.json`. Example:

```json
{
  "my_crop_advisory.pdf": {
    "title": "Exact title from the publication",
    "source": "Issuing institution",
    "url": "https://official.example/advisory",
    "publication_date": "YYYY-MM-DD",
    "retrieved_date": "YYYY-MM-DD",
    "licence": "Exact licence or terms checked",
    "verified": true,
    "crop": "Tomato",
    "pest": "Whitefly",
    "state": "Karnataka",
    "district": "Example district",
    "language": "English",
    "relationships": []
  }
}
```

Only set `verified` to `true` after a person has checked the document identity, official source, relevance, and reuse rights. A source lead in this manifest is not proof that its full document is present. Documents without `verified: true`, title, source, and an HTTPS URL are excluded from retrieval.

4. Restart the app or call `python scripts/check_corpus.py`. The local index rebuilds when the file/manifest signature changes.
5. Review `/api/system/status` and `/api/sources`. Check `found_count`, `processed_count`, `indexed_chunk_count`, `rejected_count`, and `failed_count`.

## PDF page references and scanned documents

Text-based PDFs retain 1-based page numbers in retrieved passages. A scanned PDF with no extractable text is reported as failed and is not silently indexed. OCR is not bundled in this version; run an approved OCR workflow, verify its output against the original, and then add the checked text/PDF through the same manifest process.

## Curated knowledge-graph relationships

A verified manifest record may include a `relationships` array. Each relationship must contain `from`, `type`, `to`, and an `evidence_excerpt` of at least 20 characters; `page` is recommended. Add only relationships directly supported by the cited document. The graph builder ignores demo edges and unverified/missing documents. A graph edge is a traceable relationship, not sufficient evidence for a treatment by itself.

## Current corpus status

The included `demo_dharwad_maize.txt` is deliberately excluded. The source records in `sources.json` are source leads only (`verified: false`); their full documents are not included. Therefore, the repository ships with **zero verified agricultural evidence documents** and will safely return an evidence-unavailable answer until authorized, reviewed documents are supplied.

## Safety

- Do not add fabricated or AI-generated documents as if they were official publications.
- Do not add a treatment dose, local price, supplier, or availability unless a source supports it and its date/unit/scope are recorded.
- A crop photograph is preliminary visual triage. A soil photograph cannot establish pH, nutrients, salinity, or exact moisture.
- Get a local KVK/agronomist to review the corpus and localized advice before production use.
