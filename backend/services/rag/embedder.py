"""Local TF-IDF vectorizer factory. This is lexical vectorization, not a neural embedding model."""
from __future__ import annotations


def make_vectorizer():
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        return TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, max_features=150000,
                               token_pattern=r"(?u)\b\w[\w-]+\b")
    except Exception:
        return None
