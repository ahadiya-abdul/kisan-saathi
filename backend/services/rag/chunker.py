"""Deterministic word-window chunker that retains page/source metadata."""
from __future__ import annotations


def chunk_text(text: str, size: int = 180, overlap: int = 35):
    words = (text or "").split()
    if not words:
        return
    size = max(40, int(size)); overlap = max(0, min(int(overlap), size - 1))
    step = size - overlap
    for start in range(0, len(words), step):
        chunk = " ".join(words[start:start + size]).strip()
        if len(chunk) >= 80:
            yield chunk
