import logging
from fastapi import APIRouter, Depends, HTTPException, status
from models.schemas import QueryRequest, QueryResponse, SourceTag, ConfidenceLevel
from services.auth import require_auth
from services.gemini_client import query_with_context
from services.tag_store import get_tags_for_home

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])


@router.post("/ask", response_model=QueryResponse)
async def ask_question(
    request: QueryRequest,
    user: dict = Depends(require_auth),
):
    """Answer a natural language question about where things are in the home."""
    # Fetch all tags for the home
    try:
        tags = await get_tags_for_home(request.home_id)
    except Exception as e:
        logger.error(
            "query_fetch_error home_id=%s error=%s",
            request.home_id, str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch home data",
        )

    if not tags:
        return QueryResponse(
            answer="I don't have any rooms tagged in your home yet — ask your caregiver to add some photos.",
            source_tags=[],
            confidence=ConfidenceLevel.low,
        )

    # Build compact context from tags
    context_lines = []
    tag_lookup: dict[str, dict] = {}
    for tag in tags:
        room_name = tag.get("rooms", {}).get("name", "Unknown Room")
        photo_path = tag.get("photos", {}).get("storage_path", "")
        label = tag.get("label", "")
        position = tag.get("position", "")
        notes = tag.get("notes", "")

        context_lines.append(
            f"Room: {room_name} | Object: {label} | Position: {position} | Notes: {notes}"
        )
        tag_lookup[label.lower()] = {
            "label": label,
            "room_name": room_name,
            "position": position,
            "photo_url": photo_path,
        }

    context = "\n".join(context_lines)

    # Query Gemini
    try:
        answer = await query_with_context(context, request.question)
    except Exception as e:
        logger.error(
            "query_gemini_error home_id=%s error=%s",
            request.home_id, str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to process query",
        )

    # Identify which tags were referenced in the answer
    source_tags = []
    for label_lower, tag_info in tag_lookup.items():
        if label_lower in answer.lower():
            source_tags.append(SourceTag(**tag_info))

    # Determine confidence based on whether we found matching tags
    if source_tags:
        confidence = ConfidenceLevel.high
    elif "don't have" in answer.lower() or "not tagged" in answer.lower():
        confidence = ConfidenceLevel.low
    else:
        confidence = ConfidenceLevel.medium

    logger.info(
        "query_ask home_id=%s question_length=%d source_tags=%d",
        request.home_id, len(request.question), len(source_tags),
    )

    return QueryResponse(
        answer=answer,
        source_tags=source_tags,
        confidence=confidence,
    )
