import os
import json
import logging
import time
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is not set")
        _client = genai.Client(api_key=api_key)
    return _client


VISION_MODEL = "gemini-2.5-flash"
TEXT_MODEL = "gemini-2.5-flash"

PRIVACY_SYSTEM_INSTRUCTION = (
    "You are processing private home photos for an accessibility application "
    "that helps memory-impaired patients locate their belongings. "
    "Treat all content as sensitive and private."
)

VISION_PROMPT = """Analyze this photo of a room. Identify every object, furniture piece, or storage location that would help someone find their belongings.

For each item return:
- label: a clear short name (e.g. "medicine cabinet", "bedside drawer")
- position: where it is in the room (e.g. "left wall near window", "top shelf above desk")
- confidence: "high", "medium", or "low"
- notes: one sentence describing what makes it recognizable or how to locate it

Focus on: medication, food storage, personal items, appliances, drawers, cabinets, shelves.
Ignore: bare walls, floors, ceilings unless they have a notable storage feature.

Return ONLY valid JSON, no markdown fences, no explanation:
{"tags": [...], "raw_description": "one sentence describing the room"}"""

VISION_RETRY_PROMPT = """Your previous response was not valid JSON. Try again.

Analyze this photo of a room. Return ONLY a valid JSON object with this exact structure, nothing else:
{"tags": [{"label": "string", "position": "string", "confidence": "high|medium|low", "notes": "string"}], "raw_description": "string"}"""


async def analyze_image(image_bytes: bytes, mime_type: str) -> dict:
    """Send image to Gemini for object detection. Returns parsed dict."""
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    def _call_vision(prompt, part):
        return _get_client().models.generate_content(
            model=VISION_MODEL,
            contents=[prompt, part],
            config=types.GenerateContentConfig(
                system_instruction=PRIVACY_SYSTEM_INSTRUCTION,
            ),
        )

    start = time.time()
    response = await asyncio.to_thread(_call_vision, VISION_PROMPT, image_part)
    latency = time.time() - start

    logger.info(
        "gemini_vision_call model=%s latency=%.2fs",
        VISION_MODEL, latency,
    )

    try:
        result = _parse_json_response(response.text)
        return result
    except (json.JSONDecodeError, ValueError):
        logger.warning("Malformed Gemini JSON, retrying with stricter prompt")

    # Retry once with stricter prompt
    start = time.time()
    response = await asyncio.to_thread(_call_vision, VISION_RETRY_PROMPT, image_part)
    latency = time.time() - start
    logger.info(
        "gemini_vision_retry model=%s latency=%.2fs",
        VISION_MODEL, latency,
    )

    result = _parse_json_response(response.text)
    return result


async def query_with_context(context: str, question: str) -> str:
    """Text-only query for conversational interface."""
    system = (
        "You are a helpful assistant for a person with memory difficulties. "
        "Answer questions about where things are in their home based only on "
        "the location data provided. Be warm, clear, and specific. "
        "Never guess or fabricate locations.\n\n"
        "If you find the item, respond in 2-3 sentences including the room name "
        "and position. If you do not find it, say exactly: "
        '"I don\'t have that item tagged in your home yet — ask your caregiver to add it."'
    )

    prompt = f"Home layout data:\n{context}\n\nQuestion: {question}"

    def _call_query():
        return _get_client().models.generate_content(
            model=TEXT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
            ),
        )

    start = time.time()
    response = await asyncio.to_thread(_call_query)
    latency = time.time() - start

    logger.info(
        "gemini_query_call model=%s latency=%.2fs",
        TEXT_MODEL, latency,
    )

    return response.text


async def suggest_positions(
    tags: list[dict], room_width_px: int, room_height_px: int
) -> list[dict]:
    """Use Gemini to interpret position descriptions as pixel coordinates."""
    system = (
        "You convert natural language position descriptions into x/y pixel "
        "coordinates on a rectangular canvas. Return ONLY valid JSON."
    )

    tag_descriptions = "\n".join(
        f'- id: "{t["id"]}", label: "{t["label"]}", position: "{t["position"]}"'
        for t in tags
    )

    prompt = (
        f"Canvas dimensions: {room_width_px}px wide x {room_height_px}px tall.\n"
        f"The origin (0,0) is the top-left corner.\n\n"
        f"Place these items on the canvas based on their position descriptions:\n"
        f"{tag_descriptions}\n\n"
        f'Return ONLY valid JSON: {{"placements": [{{"tag_id": "...", "label": "...", "x": 0, "y": 0}}]}}'
    )

    def _call_floorplan():
        return _get_client().models.generate_content(
            model=TEXT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
            ),
        )

    start = time.time()
    response = await asyncio.to_thread(_call_floorplan)
    latency = time.time() - start

    logger.info(
        "gemini_floorplan_call model=%s latency=%.2fs",
        TEXT_MODEL, latency,
    )

    result = _parse_json_response(response.text)
    return result.get("placements", [])


def _parse_json_response(text: str) -> dict:
    """Parse JSON from Gemini response, stripping markdown fences if present."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)
