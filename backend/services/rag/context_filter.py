"""Conservative context compatibility checks for retrieved passages."""
from __future__ import annotations


def compatible(passsage: dict, context: dict) -> bool:
    """Filter only when a document explicitly declares a conflicting crop/pest scope."""
    meta = passsage.get("metadata") or {}
    for key in ("crop", "pest"):
        expected = str(context.get(key) or "").strip().casefold()
        declared = meta.get(key)
        if expected and declared and str(declared).strip().casefold() not in {expected, "all", "multiple", "general"}:
            return False
    return True
