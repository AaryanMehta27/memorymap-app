"""
Tag Lifecycle Service for MemoryMap.

Handles confidence decay over time, contradiction detection when patients
report incorrect locations, relocation intent parsing, item removal detection,
and stale-tag reconfirmation prompts.
"""

import re
import logging
from datetime import datetime, timezone
from typing import Optional

from services.tag_store import _get_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Confidence Decay
# ---------------------------------------------------------------------------

def _days_since_update(tag: dict) -> float:
    """Return the number of days since the tag was last updated (or created)."""
    timestamp_str = tag.get("updated_at") or tag.get("created_at")
    if not timestamp_str:
        return 0.0

    # Supabase timestamps are ISO-8601 (may or may not include tz)
    try:
        updated = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return 0.0

    now = datetime.now(timezone.utc)
    return (now - updated).total_seconds() / 86400


def get_effective_confidence(tag: dict) -> str:
    """
    Compute the effective confidence of a tag based on its age.

    Decay schedule:
        Day 0-7   : original confidence
        Day 7-14  : drops one level (high -> medium, medium -> low)
        Day 14-30 : drops to low
        Day 30+   : marked as "stale"
    """
    days = _days_since_update(tag)
    original = tag.get("confidence", "medium")

    if days <= 7:
        return original

    if days <= 14:
        # Drop one level
        if original == "high":
            return "medium"
        return "low"

    if days <= 30:
        return "low"

    return "stale"


def get_confidence_note(tag: dict) -> str:
    """
    Return a human-readable qualifier about tag freshness.

    Examples:
        "(tagged 2 months ago -- may have moved)"
        "(tagged yesterday)"
    """
    days = _days_since_update(tag)

    if days < 1:
        return "(tagged today)"
    if days < 2:
        return "(tagged yesterday)"
    if days <= 7:
        return f"(tagged {int(days)} days ago)"
    if days <= 30:
        return f"(tagged {int(days)} days ago -- may have moved)"
    if days <= 60:
        return f"(tagged about {int(days // 30)} month ago -- may have moved)"
    months = int(days // 30)
    return f"(tagged {months} months ago -- may have moved)"


# ---------------------------------------------------------------------------
# Contradiction Detection
# ---------------------------------------------------------------------------

# Patterns that indicate the patient disagrees with a location
_CONTRADICTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bnot there\b",
        r"\bcan'?t find it\b",
        r"\bit'?s not in\b",
        r"\balready checked\b",
        r"\bthat'?s wrong\b",
        r"\bno it isn'?t\b",
        r"\bi looked there\b",
        r"\bit'?s empty\b",
        r"\bnothing there\b",
    ]
]


def detect_contradiction(user_message: str) -> bool:
    """Return True if the message indicates the user disagrees with a location."""
    for pattern in _CONTRADICTION_PATTERNS:
        if pattern.search(user_message):
            return True
    return False


def handle_contradiction(tag_id: str, room_id: str) -> dict:
    """
    Mark a tag's confidence as 'low' in Supabase because the patient
    reported the item isn't where the system said.

    Returns a response dict with a helpful message.
    """
    try:
        client = _get_client()
        client.table("tags").update({
            "confidence": "low",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", tag_id).execute()
        logger.info("contradiction_handled tag_id=%s marked low", tag_id)
    except Exception as exc:
        logger.warning("contradiction_update_failed tag_id=%s error=%s", tag_id, exc)

    return {
        "handled": True,
        "message": (
            "I'm sorry about that! I've noted that the previous location "
            "might be wrong. Do you remember where you moved it? "
            "I can update the location for you."
        ),
    }


# ---------------------------------------------------------------------------
# Relocation Intent Detection
# ---------------------------------------------------------------------------

# Patterns: "I moved X to Y", "I put X in/on Y", "X is now in Y", etc.
_RELOCATION_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"i\s+moved\s+(?:my\s+|the\s+)?(?P<item>.+?)\s+to\s+(?:the\s+)?(?P<location>.+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"i\s+put\s+(?:my\s+|the\s+)?(?P<item>.+?)\s+(?:in|on)\s+(?:the\s+)?(?P<location>.+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:my\s+|the\s+)?(?P<item>.+?)\s+is\s+now\s+(?:in|on)\s+(?:the\s+)?(?P<location>.+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"i\s+left\s+(?:my\s+|the\s+)?(?P<item>.+?)\s+(?:in|on)\s+(?:the\s+)?(?P<location>.+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:my\s+|the\s+)?(?P<item>.+?)\s+is\s+on\s+(?:the\s+)?(?P<location>.+?)\s+now",
        re.IGNORECASE,
    ),
]


def detect_relocation(user_message: str) -> Optional[dict]:
    """
    Detect if the user is saying they moved an item to a new location.

    Returns:
        {"item": "pills", "new_location": "bedroom nightstand"} or None
    """
    for pattern in _RELOCATION_PATTERNS:
        match = pattern.search(user_message)
        if match:
            item = match.group("item").strip().rstrip(".,!?")
            location = match.group("location").strip().rstrip(".,!?")
            if item and location:
                logger.info("relocation_detected item=%s location=%s", item, location)
                return {"item": item, "new_location": location}
    return None


def update_tag_location(
    tag_id: str,
    new_position: str,
    room_id: Optional[str] = None,
) -> dict:
    """
    Update a tag in Supabase with a new position, reset confidence to 'high',
    and refresh the updated_at timestamp.
    """
    update_data: dict = {
        "position": new_position,
        "confidence": "high",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if room_id is not None:
        update_data["room_id"] = room_id

    try:
        client = _get_client()
        result = (
            client.table("tags")
            .update(update_data)
            .eq("id", tag_id)
            .execute()
        )
        logger.info("tag_location_updated tag_id=%s new_position=%s", tag_id, new_position)
        return {"updated": True, "tag": result.data[0] if result.data else {}}
    except Exception as exc:
        logger.warning("tag_location_update_failed tag_id=%s error=%s", tag_id, exc)
        return {"updated": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Item Removal Detection
# ---------------------------------------------------------------------------

_REMOVAL_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"i\s+finished\s+(?:my\s+|the\s+)?(?P<item>.+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:threw|throw)\s+away\s+(?:my\s+|the\s+)?(?P<item>.+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:my\s+|the\s+)?(?P<item>.+?)\s+is\s+gone",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:got rid of|used up|ran out of)\s+(?:my\s+|the\s+)?(?P<item>.+)",
        re.IGNORECASE,
    ),
]


def detect_removal(user_message: str) -> Optional[str]:
    """
    Detect if the user is saying an item is gone / used up / thrown away.

    Returns the item name or None.
    """
    for pattern in _REMOVAL_PATTERNS:
        match = pattern.search(user_message)
        if match:
            item = match.group("item").strip().rstrip(".,!?")
            if item:
                logger.info("removal_detected item=%s", item)
                return item
    return None


# ---------------------------------------------------------------------------
# Re-confirmation (Stale Tags)
# ---------------------------------------------------------------------------

async def get_stale_tags(home_id: str, days_threshold: int = 14) -> list[dict]:
    """
    Fetch tags for a home that haven't been updated in more than
    `days_threshold` days.
    """
    try:
        client = _get_client()
        # Calculate the cutoff timestamp
        cutoff = datetime.now(timezone.utc)
        cutoff_iso = cutoff.isoformat()

        # Fetch all tags for the home then filter by age client-side,
        # because Supabase date arithmetic in PostgREST is limited.
        result = (
            client.table("tags")
            .select("*, rooms!inner(name, home_id)")
            .eq("rooms.home_id", home_id)
            .execute()
        )

        stale: list[dict] = []
        for tag in result.data:
            if _days_since_update(tag) >= days_threshold:
                stale.append(tag)

        logger.info(
            "stale_tags_fetched home_id=%s threshold=%d count=%d",
            home_id, days_threshold, len(stale),
        )
        return stale
    except Exception as exc:
        logger.warning("stale_tags_fetch_failed home_id=%s error=%s", home_id, exc)
        return []


def generate_reconfirmation_prompt(tag: dict) -> str:
    """
    Generate a gentle reconfirmation question for a stale tag.

    Example: "By the way, are your pills still in the kitchen cabinet?"
    """
    label = tag.get("label", "item")
    position = tag.get("position", "its usual place")
    room_name = tag.get("rooms", {}).get("name", "")

    location = position
    if room_name:
        location = f"the {room_name} {position}"

    return f"By the way, is your {label} still in {location}?"
