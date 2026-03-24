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
        r"(?:my\s+|the\s+)?(?P<item>.+?)\s+(?:is|are)\s+on\s+(?:the\s+)?(?P<location>.+?)\s+now",
        re.IGNORECASE,
    ),
    # "My X are/is on/in the Y" (without trailing "now")
    re.compile(
        r"(?:my\s+|the\s+)(?P<item>.+?)\s+(?:is|are)\s+(?:in|on)\s+(?:the\s+)?(?P<location>.+)",
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


def find_tag_by_item(item: str, home_id: str) -> Optional[dict]:
    """
    Search existing tags for one matching the given item name.

    Uses a case-insensitive substring match on the tag label. For example,
    if the patient says "I put the milk on the counter", we search for
    any tag whose label contains "milk".

    Args:
        item: the item name extracted from the patient's message
        home_id: the patient's home ID

    Returns:
        The matching tag dict, or None if no match found.
    """
    try:
        client = _get_client()
        result = (
            client.table("tags")
            .select("*, rooms!inner(name, home_id)")
            .eq("rooms.home_id", home_id)
            .ilike("label", f"%{item}%")
            .execute()
        )
        if result.data:
            logger.info("find_tag_by_item found=%s for item=%s", result.data[0]["id"], item)
            return result.data[0]
    except Exception as exc:
        logger.warning("find_tag_by_item_failed item=%s error=%s", item, exc)
    return None


def create_conversational_tag(
    item: str,
    location: str,
    home_id: str,
    room_id: Optional[str] = None,
) -> dict:
    """
    Create a NEW tag from conversational input.

    When a patient says "I put the milk on the kitchen counter" and there's
    no existing "milk" tag, we create one. This way, next time they ask
    "where is my milk?", the retriever finds it via direct keyword match.

    These conversational tags have source="conversation" to distinguish them
    from vision-pipeline tags (source="vision"). Confidence starts at "high"
    because the patient just told us where it is.

    Args:
        item: the item name (e.g., "milk", "reading glasses")
        location: where they said it is (e.g., "kitchen counter")
        home_id: the patient's home ID
        room_id: optional room ID (if we can determine which room)

    Returns:
        Dict with created tag info, or error details.
    """
    import uuid

    tag_data = {
        "id": str(uuid.uuid4()),
        "label": item,
        "position": location,
        "confidence": "high",
        "notes": f"Reported by patient via conversation: '{item}' is at '{location}'",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # If we have a room_id, use it. Otherwise try to find a matching room.
    if room_id:
        tag_data["room_id"] = room_id
    else:
        # Try to infer room from the location description
        inferred_room = _infer_room_from_location(location, home_id)
        if inferred_room:
            tag_data["room_id"] = inferred_room["id"]

    # We need a photo_id for the foreign key, but conversational tags
    # have no photo. Use a null/placeholder approach — Person B may need
    # to make photo_id nullable, or we skip the insert if it's required.
    try:
        client = _get_client()
        result = client.table("tags").insert(tag_data).execute()
        logger.info(
            "conversational_tag_created item=%s location=%s id=%s",
            item, location, tag_data["id"],
        )
        return {
            "created": True,
            "tag": result.data[0] if result.data else tag_data,
            "message": f"Got it! I'll remember that your {item} is on the {location}.",
        }
    except Exception as exc:
        # If insert fails (e.g., photo_id required), store in-memory as fallback
        logger.warning(
            "conversational_tag_insert_failed item=%s error=%s — storing in memory",
            item, exc,
        )
        _in_memory_tags.append(tag_data)
        return {
            "created": True,
            "stored_in_memory": True,
            "tag": tag_data,
            "message": f"Got it! I'll remember that your {item} is on the {location}.",
        }


# In-memory fallback for conversational tags when Supabase insert fails
# (e.g., if photo_id is a required foreign key)
_in_memory_tags: list[dict] = []


def get_in_memory_tags() -> list[dict]:
    """Return all tags stored in memory (conversational tags that couldn't
    be persisted to Supabase)."""
    return list(_in_memory_tags)


def _infer_room_from_location(location: str, home_id: str) -> Optional[dict]:
    """
    Try to figure out which room the location belongs to by matching
    room names against the location description.

    E.g., "kitchen counter" contains "kitchen" → match the Kitchen room.
    """
    try:
        client = _get_client()
        result = (
            client.table("rooms")
            .select("id, name")
            .eq("home_id", home_id)
            .execute()
        )
        location_lower = location.lower()
        for room in result.data:
            if room["name"].lower() in location_lower:
                logger.info(
                    "inferred_room name=%s from location=%s",
                    room["name"], location,
                )
                return room
    except Exception as exc:
        logger.warning("room_inference_failed location=%s error=%s", location, exc)
    return None


async def handle_relocation(
    user_message: str,
    home_id: str,
) -> Optional[dict]:
    """
    Full relocation handler: detect intent, find or create the tag, update it.

    This is the main entry point called from the query router when a patient
    says something like "I put the milk on the kitchen counter".

    Flow:
        1. Detect relocation intent ("I put X at/on/in Y")
        2. Search for existing tag matching item X
        3. If found → update the tag's position to Y
        4. If NOT found → create a new conversational tag for X at Y
        5. Return confirmation message

    Args:
        user_message: the raw patient message
        home_id: the patient's home ID

    Returns:
        Response dict with confirmation, or None if no relocation detected.
    """
    relocation = detect_relocation(user_message)
    if relocation is None:
        return None

    item = relocation["item"]
    new_location = relocation["new_location"]

    # Try to find an existing tag for this item
    existing_tag = find_tag_by_item(item, home_id)

    if existing_tag:
        # Update the existing tag's position
        result = update_tag_location(existing_tag["id"], new_location)
        return {
            "action": "updated",
            "item": item,
            "old_location": existing_tag.get("position", "unknown"),
            "new_location": new_location,
            "message": (
                f"Updated! I've moved your {item} from "
                f"'{existing_tag.get('position', 'its old location')}' to "
                f"'{new_location}'. I'll remember that for next time."
            ),
        }
    else:
        # No existing tag — create a new one from conversation
        result = create_conversational_tag(item, new_location, home_id)
        return {
            "action": "created",
            "item": item,
            "new_location": new_location,
            "message": result["message"],
        }


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
