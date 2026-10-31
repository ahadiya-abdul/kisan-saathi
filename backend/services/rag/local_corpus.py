"""Source-registered local agricultural corpus with provenance-aware TF-IDF retrieval.

This is a real lexical RAG baseline, not a neural embedding/vector database and not model fine-tuning.
Only documents with an explicit verified=true manifest record are eligible for recommendations.
"""
from __future__ import annotations
import json, math, re
from pathlib import Path
from collections import Counter
from .chunker import chunk_text
from .cleaner import clean_text
from .context_filter import compatible
from .embedder import make_vectorizer
from .loader import read_document, SUPPORTED
from .ranker import rerank
try:
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:
    cosine_similarity = None

_CACHE_SIGNATURE = None
_CACHE_DOCS = []
_CACHE_VECTORIZER = None
_CACHE_MATRIX = None
ROOT = Path(__file__).resolve().parents[3]
DOC_DIR = ROOT / "data" / "documents"
MANIFEST = DOC_DIR / "sources.json"
WORD_RE = re.compile(r"[\w-]+", re.UNICODE)


def _manifest():
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _load_corpus():
    global _CACHE_SIGNATURE, _CACHE_DOCS, _CACHE_VECTORIZER, _CACHE_MATRIX
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    paths = [p for p in sorted(DOC_DIR.rglob("*")) if p.is_file() and p.suffix.lower() in SUPPORTED
             and p.name.lower() != "readme.md" and not p.name.lower().startswith("demo_")]
    signature = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths) + ((str(MANIFEST), MANIFEST.stat().st_mtime_ns, MANIFEST.stat().st_size),) if MANIFEST.exists() else tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths)
    if signature == _CACHE_SIGNATURE:
        return _CACHE_DOCS, _CACHE_VECTORIZER, _CACHE_MATRIX
    manifest = _manifest(); docs = []
    for path in paths:
        meta = manifest.get(path.name, {})
        # An official-looking filename is not provenance. Require an explicit reviewed manifest record.
        if not isinstance(meta, dict) or meta.get("verified") is not True:
            continue
        source_url = str(meta.get("url") or "")
        if not source_url.startswith("https://") or not meta.get("source") or not meta.get("title"):
            continue
        pages, error = read_document(path)
        if error:
            continue
        for page in pages:
            text = page["text"]
            if not text or "DEMO DOCUMENT" in text[:500].upper():
                continue
            for index, chunk in enumerate(chunk_text(text)):
                docs.append({"id": f"{path.name}#p{page['page'] or 'na'}-c{index+1}",
                    "title": meta["title"], "source": meta["source"], "url": source_url,
                    "text": chunk, "filename": path.name, "page": page["page"],
                    "metadata": {k: meta.get(k) for k in ("crop", "pest", "state", "district", "stage", "language") if meta.get(k)},
                    "publication_date": meta.get("publication_date"), "retrieved_date": meta.get("retrieved_date"),
                    "licence": meta.get("licence"), "verified": True})
    vectorizer = matrix = None
    if docs:
        vectorizer = make_vectorizer()
        if vectorizer is not None:
            try:
                matrix = vectorizer.fit_transform([d["text"] for d in docs])
            except ValueError:
                vectorizer = matrix = None
    _CACHE_SIGNATURE, _CACHE_DOCS, _CACHE_VECTORIZER, _CACHE_MATRIX = signature, docs, vectorizer, matrix
    return docs, vectorizer, matrix


def retrieve(query: str, context: dict | None = None, top_k: int = 5) -> list[dict]:
    """Retrieve source-verified passages; scores indicate text relevance only."""
    context = context or {}
    docs, vectorizer, matrix = _load_corpus()
    if not docs:
        return []
    query_parts = [query or ""]
    for key in ("crop", "variety", "pest", "stage", "soil", "district", "state", "weather_summary", "image_analysis"):
        value = context.get(key)
        if value:
            query_parts.append(str(value))
    query_text = " ".join(query_parts)
    candidates = []
    if vectorizer is not None and matrix is not None and cosine_similarity is not None:
        try:
            scores = cosine_similarity(vectorizer.transform([query_text]), matrix).ravel()
            for index, score in sorted(enumerate(scores), key=lambda pair: pair[1], reverse=True):
                if score < 0.025: break
                item = dict(docs[index]); item["score"] = float(score); candidates.append(item)
        except Exception:
            candidates = []
    if not candidates:
        qtokens = {w.lower() for w in WORD_RE.findall(query_text) if len(w) > 2}
        if not qtokens: return []
        tokenized = [{w.lower() for w in WORD_RE.findall(d["text"])} for d in docs]
        df = Counter(t for toks in tokenized for t in (qtokens & toks))
        for d, toks in zip(docs, tokenized):
            overlap = qtokens & toks
            if overlap:
                score = sum(math.log(1 + len(docs) / (1 + df[t])) for t in overlap) / math.sqrt(max(1, len(toks)))
                if score >= 0.015:
                    item = dict(d); item["score"] = score; candidates.append(item)
    candidates = [x for x in candidates if compatible(x, context)]
    ranked = rerank(candidates, context)
    # Keep text sent to the model bounded and avoid passing internal full-document content.
    return [{**item, "score": round(float(item["score"]), 4)} for item in ranked[:max(1, min(int(top_k), 10))]]


def corpus_status() -> dict:
    manifest = _manifest(); found = []; processed = []; rejected = []; failed = []
    for p in sorted(DOC_DIR.rglob("*")) if DOC_DIR.exists() else []:
        if not p.is_file() or p.suffix.lower() not in SUPPORTED or p.name.lower() == "readme.md" or p.name.lower().startswith("demo_"):
            continue
        found.append(p.name); meta = manifest.get(p.name, {})
        if not isinstance(meta, dict) or meta.get("verified") is not True:
            rejected.append({"filename": p.name, "reason": "missing manifest entry with verified=true"}); continue
        if not str(meta.get("url") or "").startswith("https://") or not meta.get("source") or not meta.get("title"):
            rejected.append({"filename": p.name, "reason": "incomplete source provenance"}); continue
        pages, error = read_document(p)
        if error:
            failed.append({"filename": p.name, "reason": error}); continue
        processed.append(p.name)
    docs, _, _ = _load_corpus()
    return {"found_count": len(found), "processed_count": len(processed), "indexed_chunk_count": len(docs),
            "rejected_count": len(rejected), "failed_count": len(failed), "document_count": len(processed),
            "documents": processed, "rejected": rejected, "failed": failed, "ready": bool(docs),
            "mode": "source-registered TF-IDF retrieval; no neural embeddings or model fine-tuning"}
