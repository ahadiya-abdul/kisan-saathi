"""Build a small knowledge graph only from curator-reviewed, source-backed manifest relations.

No relationships are inferred from filenames or demo edges. Each edge keeps document provenance.
"""
from __future__ import annotations
import json
from pathlib import Path
import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
DOC_DIR = ROOT / "data" / "documents"
MANIFEST = DOC_DIR / "sources.json"


def build_graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return graph
    if not isinstance(manifest, dict):
        return graph
    for filename, meta in manifest.items():
        if not isinstance(meta, dict) or meta.get("verified") is not True:
            continue
        path = (DOC_DIR / filename).resolve()
        if path.parent != DOC_DIR.resolve() and DOC_DIR.resolve() not in path.parents:
            continue
        if not path.is_file() or not str(meta.get("url") or "").startswith("https://"):
            continue
        for rel in meta.get("relationships", []):
            if not isinstance(rel, dict):
                continue
            source_node = str(rel.get("from") or "").strip()
            relation = str(rel.get("type") or "").strip()
            target_node = str(rel.get("to") or "").strip()
            evidence = str(rel.get("evidence_excerpt") or "").strip()
            if not source_node or not relation or not target_node or len(evidence) < 20:
                continue
            provenance = {"filename": filename, "title": meta.get("title"), "source": meta.get("source"),
                          "url": meta.get("url"), "page": rel.get("page"), "evidence_excerpt": evidence,
                          "crop": rel.get("crop") or meta.get("crop"), "pest": rel.get("pest") or meta.get("pest"),
                          "state": rel.get("state") or meta.get("state"), "district": rel.get("district") or meta.get("district")}
            graph.add_edge(source_node, target_node, key=f"{filename}:{rel.get('page') or 'na'}:{relation}",
                           relationship=relation, **provenance)
    return graph


def query_graph(node: str = "", context: dict | None = None, limit: int = 20) -> dict:
    graph = build_graph()
    context = context or {}
    if not graph.number_of_edges():
        return {"available": False, "node": node, "neighbors": [], "relationships": [],
                "message": "No verified source-derived relationships are configured in the knowledge graph."}
    wanted = {str(node or "").casefold(), str(context.get("crop") or "").casefold(),
              str(context.get("pest") or "").casefold()}
    wanted.discard("")
    rows = []
    for start, end, data in graph.edges(data=True):
        if wanted and not any(term in start.casefold() or term in end.casefold() for term in wanted):
            continue
        if context.get("state") and data.get("state") and str(context["state"]).casefold() != str(data["state"]).casefold():
            continue
        if context.get("district") and data.get("district") and str(context["district"]).casefold() != str(data["district"]).casefold():
            continue
        rows.append({"from": start, "relationship": data.get("relationship"), "to": end,
                     "source": data.get("source"), "title": data.get("title"), "url": data.get("url"),
                     "filename": data.get("filename"), "page": data.get("page"),
                     "evidence_excerpt": data.get("evidence_excerpt"), "crop": data.get("crop"),
                     "pest": data.get("pest"), "state": data.get("state"), "district": data.get("district")})
    rows = rows[:max(1, min(int(limit), 50))]
    neighbors = sorted({r["to"] if r["from"].casefold() in wanted else r["from"] for r in rows})
    return {"available": bool(rows), "node": node, "neighbors": neighbors, "relationships": rows,
            "message": "Relationships are curated from verified source records; they are not model-inferred." if rows else "No verified graph relationship matched this crop, pest, or location."}
