"""RAG generation adapter; generation is delegated to the configured LLM service."""
from backend.services.gemini import generate_advice


def generate(question: str, context: dict, passages: list[dict]):
    if not passages:
        return None
    return generate_advice(question, context, {"passages": passages})
