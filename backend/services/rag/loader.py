"""Document loading with page-level provenance and explicit rejection reasons."""
from __future__ import annotations
from pathlib import Path
from .cleaner import clean_text

SUPPORTED = {".txt", ".md", ".pdf"}


def read_document(path: Path) -> tuple[list[dict], str | None]:
    """Return page-like records; PDF pages retain 1-based page numbers."""
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            pages = [{"page": i + 1, "text": clean_text(page.extract_text() or "")}
                     for i, page in enumerate(reader.pages)]
            if not any(p["text"] for p in pages):
                return [], "no extractable text (scanned PDF may require OCR)"
            return pages, None
        except ImportError:
            return [], "pypdf dependency is not installed"
        except Exception as exc:
            return [], f"PDF read failed: {type(exc).__name__}"
    try:
        text = clean_text(path.read_text(encoding="utf-8", errors="ignore"))
        return ([{"page": None, "text": text}] if text else []), (None if text else "empty text")
    except OSError as exc:
        return [], f"read failed: {type(exc).__name__}"
