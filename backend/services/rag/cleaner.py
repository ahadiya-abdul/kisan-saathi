"""Text cleaning for retrieved agricultural documents; does not add facts."""
from __future__ import annotations
import re


def clean_text(text: str) -> str:
    text = (text or "").replace("\x00", " ").replace("\ufeff", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
