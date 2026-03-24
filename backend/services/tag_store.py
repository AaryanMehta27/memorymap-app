import os
import uuid
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


async def save_tags(room_id: str, photo_id: str, tags: list[dict]) -> list[dict]:
    """Insert tags into Supabase tags table. Returns the inserted rows."""
    client = _get_client()
    rows = []
    for tag in tags:
        # Ensure confidence is a plain string matching CHECK constraint
        conf = tag["confidence"]
        if hasattr(conf, "value"):
            conf = conf.value  # handle enum objects
        if conf not in ("high", "medium", "low"):
            conf = "medium"

        row = {
            "id": tag.get("id", str(uuid.uuid4())),
            "photo_id": photo_id,
            "room_id": room_id,
            "label": tag["label"],
            "position": tag["position"],
            "confidence": conf,
            "notes": tag.get("notes", ""),
        }
        rows.append(row)

    if rows:
        result = client.table("tags").insert(rows).execute()
        logger.info(
            "saved_tags room_id=%s count=%d", room_id, len(result.data)
        )
        return result.data

    return []


async def get_tags_for_home(home_id: str) -> list[dict]:
    """Fetch all tags for a home, joined with room name and photo storage path."""
    client = _get_client()
    result = (
        client.table("tags")
        .select("*, rooms!inner(name, home_id), photos!inner(storage_path)")
        .eq("rooms.home_id", home_id)
        .execute()
    )
    return result.data


async def get_tags_for_room(room_id: str) -> list[dict]:
    """Fetch all tags for a specific room."""
    client = _get_client()
    result = (
        client.table("tags")
        .select("*, rooms!inner(name), photos!inner(storage_path)")
        .eq("room_id", room_id)
        .execute()
    )
    return result.data


async def update_tag_positions(
    tag_updates: list[dict],
) -> list[dict]:
    """Update canvas_x and canvas_y for tags."""
    client = _get_client()
    updated = []
    for update in tag_updates:
        result = (
            client.table("tags")
            .update({"canvas_x": update["x"], "canvas_y": update["y"]})
            .eq("id", update["tag_id"])
            .execute()
        )
        updated.extend(result.data)
    return updated
