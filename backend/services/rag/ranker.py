"""Small, transparent ranking helpers; scores are relevance, not diagnostic confidence."""
from __future__ import annotations


def context_bonus(item: dict, context: dict) -> float:
    meta = item.get("metadata") or {}
    bonus = 0.0
    for key in ("crop", "pest", "district", "state", "stage"):
        expected = str(context.get(key) or "").strip().casefold()
        actual = str(meta.get(key) or "").strip().casefold()
        if expected and actual and expected == actual:
            bonus += 0.04
    return bonus


def rerank(items: list[dict], context: dict) -> list[dict]:
    ranked = []
    for original in items:
        item = dict(original)
        item["score"] = round(float(item.get("score", 0)) + context_bonus(item, context), 4)
        ranked.append(item)
    return sorted(ranked, key=lambda x: x.get("score", 0), reverse=True)
