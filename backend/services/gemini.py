"""Gemini generation for evidence-grounded advisory responses."""
import json
import logging
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
logger = logging.getLogger(__name__)


def _client():
    if os.getenv("GEMINI_ENABLED", "true").lower() not in {"1", "true", "yes"}:
        return None
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def generate_advice(question: str, context: dict, evidence: dict) -> dict | None:
    """Generate a structured answer from retrieved application evidence.

    Returning None means the caller should use its explicit offline response.
    The model is instructed not to add agronomic facts that are absent from the
    supplied evidence.
    """
    try:
        client = _client()
        if client is None:
            return None

        model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        prompt = f"""
You are an agricultural advisory assistant. Be direct and concise. Use only
the evidence supplied below. Do not invent doses, prices, availability,
weather, diagnoses, or source claims. If evidence is insufficient, say so
briefly and recommend checking with a local KVK or agronomist.

Return valid JSON only with these keys:
answer (string), why_recommended (string), uncertainty (string),
confidence (number from 0 to 1).
Keep answer to at most 3 short sentences and 40 words. Start with the action
or state clearly that there is not enough evidence. Keep why_recommended and
uncertainty to one short sentence each. Do not repeat the same information.

Farmer question:
{question}

Farmer context:
{json.dumps(context, ensure_ascii=False)}

Retrieved evidence:
{json.dumps(evidence, ensure_ascii=False)}
"""
        response = client.models.generate_content(model=model, contents=prompt)
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini returned an empty response")
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].lstrip()
        generated = json.loads(text)
        if not isinstance(generated, dict):
            raise ValueError("Gemini response was not a JSON object")
        for key in ("answer", "why_recommended", "uncertainty", "confidence"):
            if key not in generated:
                raise ValueError(f"Gemini response is missing {key}")
        generated["confidence"] = max(0.0, min(1.0, float(generated["confidence"])))
        return generated
    except Exception:
        return None


def analyze_image(image_bytes: bytes, mime_type: str) -> dict | None:
    """Return cautious visual observations from a crop image."""
    try:
        client = _client()
        if client is None:
            return None
        prompt = """
Analyze this crop photo for agricultural advisory triage. Return JSON only:
candidate_issue: a possible pest, disease, nutrient issue, or "unclear"
visible_symptoms: short list of observations
confidence: number from 0 to 1
needs_human_verification: boolean
safety_note: explain that this is not a definitive diagnosis and that local
agronomist/label guidance is required before treatment.
Never invent a treatment, dose, or certainty. If the image is unclear, say so.
"""
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
            contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type), prompt],
        )
        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].lstrip()
        result = json.loads(text)
        if not isinstance(result, dict):
            raise ValueError("Gemini image response was not an object")
        required = ("candidate_issue", "visible_symptoms", "confidence",
                    "needs_human_verification", "safety_note")
        if any(key not in result for key in required):
            raise ValueError("Gemini image response is missing required fields")
        result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
        result["needs_human_verification"] = bool(result["needs_human_verification"])
        return result
    except Exception as exc:
        logger.warning("Gemini image analysis unavailable: %s", exc)
        return None
