import logging
from fastapi import APIRouter, Depends, HTTPException, status
from models.schemas import (
    FloorplanRequest,
    FloorplanResponse,
    TagPlacement,
)
from services.auth import require_auth
from services.gemini_client import suggest_positions
from services.tag_store import update_tag_positions

logger = logging.getLogger(__name__)

router = APIRouter(tags=["floorplan"])


@router.post("/suggest-positions", response_model=FloorplanResponse)
async def suggest_tag_positions(
    request: FloorplanRequest,
    user: dict = Depends(require_auth),
):
    """Suggest pixel coordinates for tags on a floor plan canvas."""
    tags_input = [
        {"id": t.id, "label": t.label, "position": t.position}
        for t in request.tags
    ]

    try:
        placements_raw = await suggest_positions(
            tags_input, request.room_width_px, request.room_height_px
        )
    except Exception as e:
        logger.error(
            "floorplan_error room_id=%s error=%s",
            request.room_id, str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate tag positions",
        )

    # Clamp coordinates to canvas bounds
    placements = []
    for p in placements_raw:
        placements.append(
            TagPlacement(
                tag_id=p["tag_id"],
                label=p["label"],
                x=max(0.0, min(float(p["x"]), float(request.room_width_px))),
                y=max(0.0, min(float(p["y"]), float(request.room_height_px))),
            )
        )

    # Save positions to Supabase (best-effort)
    try:
        await update_tag_positions(
            [{"tag_id": p.tag_id, "x": p.x, "y": p.y} for p in placements]
        )
    except Exception as e:
        logger.error(
            "floorplan_save_error room_id=%s error=%s",
            request.room_id, str(e),
        )

    logger.info(
        "floorplan_suggest room_id=%s placements=%d",
        request.room_id, len(placements),
    )

    return FloorplanResponse(placements=placements)
