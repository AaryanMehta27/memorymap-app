"""
AI client using Groq API (replaces local Ollama).
Text: llama3-8b-8192  |  Vision: meta-llama/llama-4-scout-17b-16e-instruct
"""
import os
import re
import json
import base64
import logging
import time
import asyncio
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
TEXT_MODEL    = os.getenv("GROQ_TEXT_MODEL",   "llama3-8b-8192")
VISION_MODEL  = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

_client = None


def _get_client():
    global _client
    if _client is None:
        from groq import Groq
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


VISION_PROMPT = """Analyze this photo of a room. Identify every object, furniture piece, or storage location that would help someone find their belongings.

Pay special attention to SMALL PERSONAL ITEMS:
- Items resting on flat surfaces (tables, nightstands, countertops, shelves)
- Glasses, spectacles, or eyeglass cases
- Medicine bottles, pill organizers, blister packs
- Small electronics (hearing aids, phones, remote controls)
- Keys, wallets, lanyards on any surface

For each item return:
- label: a clear short name (e.g. "reading glasses")
- position: where it is in the room (e.g. "nightstand surface")
- confidence: "high", "medium", or "low"
- notes: one sentence describing how to find it

Return ONLY valid JSON, no markdown fences:
{"tags": [...], "raw_description": "one sentence describing the room"}"""

VISION_RETRY_PROMPT = """Return ONLY a valid JSON object with this exact structure, nothing else:
{"tags": [{"label": "bedside table", "position": "right side of bed", "confidence": "high", "notes": "Small wooden table with a lamp on top."}], "raw_description": "A bedroom with a bed and bedside table."}"""


def _parse_json_response(text: str) -> dict:
    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    else:
        brace_pos = min(
            cleaned.find("{") if "{" in cleaned else len(cleaned),
            cleaned.find("[") if "[" in cleaned else len(cleaned),
        )
        if brace_pos < len(cleaned):
            cleaned = cleaned[brace_pos:]
    return json.loads(cleaned)


def _backfill_tags(result: dict) -> dict:
    for tag in result.get("tags", []):
        tag.setdefault("label", "unknown item")
        tag.setdefault("position", "unknown")
        tag.setdefault("confidence", "low")
        tag.setdefault("notes", "")
    result.setdefault("raw_description", "")
    return result


async def analyze_image(image_bytes: bytes, mime_type: str, priority_items: list[str] | None = None) -> dict:
    """Send image to Groq vision model for object detection."""
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url  = f"data:{mime_type};base64,{image_b64}"

    prompt = VISION_PROMPT
    if priority_items:
        items_list = "\n".join(f"- {item}" for item in priority_items)
        prompt = VISION_PROMPT.replace(
            "\nReturn ONLY valid JSON",
            f"\n\nPRIORITY ITEMS:\n{items_list}\n\nReturn ONLY valid JSON"
        )

    def _call_vision(p):
        return _get_client().chat.completions.create(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text",      "text": p},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }],
            max_tokens=1024,
        )

    start = time.time()
    response = await asyncio.to_thread(_call_vision, prompt)
    logger.info("groq_vision_call model=%s latency=%.2fs", VISION_MODEL, time.time() - start)

    try:
        result = _parse_json_response(response.choices[0].message.content)
        return _backfill_tags(result)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Malformed Groq JSON, retrying")

    start = time.time()
    response = await asyncio.to_thread(_call_vision, VISION_RETRY_PROMPT)
    logger.info("groq_vision_retry model=%s latency=%.2fs", VISION_MODEL, time.time() - start)
    result = _parse_json_response(response.choices[0].message.content)
    return _backfill_tags(result)


async def query_with_context(context: str, question: str) -> str:
    """Text query answered by Groq against tagged home data."""
    system = (
        "You are a helpful assistant for a person with memory difficulties. "
        "Your ONLY purpose is to help them find their belongings at home. "
        "You must ONLY answer questions about where items or belongings are located in their home.\n\n"
        "IMPORTANT: If the question is NOT about finding or locating an item in the home — "
        "for example, questions about colours, descriptions, general knowledge, or anything unrelated "
        "to where something is — respond with EXACTLY this sentence and nothing else:\n"
        "\"I'm only able to help you locate your belongings at home. "
        "Please ask me where something is, and I will do my best to assist you.\"\n\n"
        "For valid location questions:\n"
        "- Answer based only on the location data provided. Be warm, clear, and specific.\n"
        "- Never guess or fabricate locations.\n"
        "- If an item appears in MORE THAN ONE room or location, "
        "mention ALL locations clearly. For example: 'Your glasses are in two places: "
        "on the nightstand in the Bedroom, and on the kitchen table in the Kitchen.'\n\n"
        "The user may use informal or alternative words for items. "
        "Always match their intent to the closest item in the data. Examples:\n"
        "- 'specs', 'spectacles', 'eyeglasses' → glasses\n"
        "- 'meds', 'medication', 'pills', 'tablets', 'medicine cup', 'pill cup', 'medicine bottle' → medicine / pill bottle\n"
        "- 'mobile', 'cell', 'cellphone' → phone\n"
        "- 'notebook', 'notepad', 'diary' → book\n"
        "- 'telly', 'television' → TV/remote\n"
        "- 'bag', 'handbag' → purse\n"
        "- 'hearing device', 'earpiece' → hearing aid\n"
        "- 'BP machine' → blood pressure monitor\n"
        "- 'cup', 'medicine cup', 'pill cup' → medicine bottle, cup, or any container for medicine\n\n"
        "Also match items even when phrasing differs slightly — 'medicine cup' should match "
        "'medicine bottle', 'pill organizer', or any medicine-related tag.\n\n"
        "If you find the item, respond in 2-3 sentences with the room name and position. "
        "If not found, say exactly: "
        '"I don\'t have that item tagged in your home yet — ask your caregiver to add it."'
    )

    def _call_query():
        return _get_client().chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": f"Home layout data:\n{context}\n\nQuestion: {question}"},
            ],
            max_tokens=256,
            temperature=0.3,
        )

    start = time.time()
    response = await asyncio.to_thread(_call_query)
    logger.info("groq_query_call model=%s latency=%.2fs", TEXT_MODEL, time.time() - start)
    return response.choices[0].message.content


async def suggest_positions(
    tags: list[dict], room_width_px: int, room_height_px: int
) -> list[dict]:
    """Convert position descriptions to pixel coordinates."""
    system = (
        "You convert natural language position descriptions into x/y pixel "
        "coordinates on a rectangular canvas. Return ONLY valid JSON."
    )
    tag_descriptions = "\n".join(
        f'- id: "{t["id"]}", label: "{t["label"]}", position: "{t["position"]}"'
        for t in tags
    )
    prompt = (
        f"Canvas: {room_width_px}px wide x {room_height_px}px tall. Origin (0,0) = top-left.\n\n"
        f"Place these items based on their position descriptions:\n{tag_descriptions}\n\n"
        f'Return ONLY valid JSON: {{"placements": [{{"tag_id": "...", "label": "...", "x": 0, "y": 0}}]}}'
    )

    def _call_floorplan():
        return _get_client().chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=512,
            response_format={"type": "json_object"},
        )

    start = time.time()
    response = await asyncio.to_thread(_call_floorplan)
    logger.info("groq_floorplan_call model=%s latency=%.2fs", TEXT_MODEL, time.time() - start)
    result = _parse_json_response(response.choices[0].message.content)
    return result.get("placements", [])
