import logging
import time
from fastapi import APIRouter, Depends, HTTPException, status
from models.schemas import (
    VisionAnalyzeRequest,
    VisionAnalyzeResponse,
    Tag,
    SweepRequest,
    SweepResponse,
)
from services.auth import require_auth
from services.gemini_client import analyze_image
from services.tag_store import save_tags
from utils.image_utils import validate_and_decode_image

logger = logging.getLogger(__name__)

router = APIRouter(tags=["vision"])


@router.post("/analyze", response_model=VisionAnalyzeResponse)
async def analyze_room_photo(
    request: VisionAnalyzeRequest,
    user: dict = Depends(require_auth),
):
    """Analyze a single room photo and extract object tags."""
    image_bytes = validate_and_decode_image(
        request.image_base64, request.image_mime_type
    )

    start = time.time()
    try:
        result = await analyze_image(image_bytes, request.image_mime_type)
    except Exception as e:
        logger.error(
            "vision_analyze_error room_id=%s error=%s",
            request.room_id, str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to analyze image with AI model",
        )
    latency = time.time() - start

    raw_tags = result.get("tags", [])
    tags = [Tag(**t) for t in raw_tags]
    raw_description = result.get("raw_description", "")

    # Save tags to Supabase (best-effort — don't fail the request if store is down)
    try:
        await save_tags(
            room_id=request.room_id,
            photo_id=request.room_id,  # Person B will provide actual photo_id
            tags=[t.model_dump() for t in tags],
        )
    except Exception as e:
        logger.error(
            "tag_save_error room_id=%s error=%s", request.room_id, str(e)
        )

    logger.info(
        "vision_analyze room_id=%s tags_count=%d latency=%.2fs model=gemini-2.0-flash",
        request.room_id, len(tags), latency,
    )

    return VisionAnalyzeResponse(
        room_id=request.room_id,
        tags=tags,
        raw_description=raw_description,
    )


@router.post("/sweep", response_model=SweepResponse)
async def sweep_room(
    request: SweepRequest,
    user: dict = Depends(require_auth),
):
    """Analyze multiple frames of the same room and return merged tags."""
    # Stretch goal — validate all frames first
    all_image_data = []
    for frame in request.frames:
        image_bytes = validate_and_decode_image(
            frame.image_base64, frame.image_mime_type
        )
        all_image_data.append((image_bytes, frame.image_mime_type))

    # Analyze each frame and merge results
    all_tags = []
    for image_bytes, mime_type in all_image_data:
        try:
            result = await analyze_image(image_bytes, mime_type)
            all_tags.extend(result.get("tags", []))
        except Exception as e:
            logger.error(
                "sweep_frame_error room_id=%s error=%s",
                request.room_id, str(e),
            )

    # Deduplicate tags by label (keep highest confidence)
    confidence_rank = {"high": 3, "medium": 2, "low": 1}
    seen: dict[str, dict] = {}
    for tag in all_tags:
        label = tag["label"].lower().strip()
        existing = seen.get(label)
        if (
            existing is None
            or confidence_rank.get(tag.get("confidence", "low"), 0)
            > confidence_rank.get(existing.get("confidence", "low"), 0)
        ):
            seen[label] = tag
    deduplicated = list(seen.values())

    tags = [Tag(**t) for t in deduplicated]
    raw_description = f"Multi-frame sweep of room with {len(tags)} unique objects detected."

    # Save deduplicated tags
    try:
        await save_tags(
            room_id=request.room_id,
            photo_id=request.room_id,
            tags=[t.model_dump() for t in tags],
        )
    except Exception as e:
        logger.error(
            "sweep_tag_save_error room_id=%s error=%s",
            request.room_id, str(e),
        )

    logger.info(
        "vision_sweep room_id=%s frames=%d tags_count=%d",
        request.room_id, len(request.frames), len(tags),
    )

    return SweepResponse(
        room_id=request.room_id,
        tags=tags,
        raw_description=raw_description,
    )
