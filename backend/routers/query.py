"""
Query router for MemoryMap.

Handles natural-language questions about where things are in the home,
with integrated tag lifecycle management, cognitive drift detection,
and caregiver alerting.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from models.schemas import QueryRequest, QueryResponse, SourceTag, ConfidenceLevel
from services.auth import require_auth
from services.gemini_client import query_with_context
from services.tag_store import get_tags_for_home
from services.tag_lifecycle import (
    detect_relocation,
    detect_removal,
    detect_contradiction,
    handle_contradiction,
    update_tag_location,
    get_effective_confidence,
    get_confidence_note,
    generate_reconfirmation_prompt,
    get_stale_tags,
)
from services.cognitive_drift import (
    get_or_create_session,
    save_session_to_db,
)
from services.caregiver_alerts import (
    create_alert,
    CaregiverAlert,
    AlertLevel,
    AlertType,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])


@router.post("/ask", response_model=QueryResponse)
async def ask_question(
    request: QueryRequest,
    user: dict = Depends(require_auth),
):
    """
    Answer a natural language question about where things are in the home.

    Processing flow:
        1. Check relocation intent -> update tag, respond, done
        2. Check removal intent -> mark tag, respond, done
        3. Check contradiction -> mark tag low confidence, ask for new location
        4. Check drift/repeat -> add redirect context
        5. Normal RAG flow with decayed confidence
        6. Log to session
        7. Check caregiver alerts
    """
    user_id = user.get("sub", "anonymous")
    question = request.question
    home_id = request.home_id

    # Get or create conversation session for drift tracking
    session = get_or_create_session(user_id)
    session.add_message("user", question)

    # ------------------------------------------------------------------
    # Fetch all tags for the home
    # ------------------------------------------------------------------
    try:
        tags = await get_tags_for_home(home_id)
    except Exception as e:
        logger.error("query_fetch_error home_id=%s error=%s", home_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch home data",
        )

    # Build a quick label -> tag lookup for matching
    tag_lookup: dict[str, dict] = {}
    for tag in tags:
        label = tag.get("label", "").lower()
        if label:
            tag_lookup[label] = tag

    # ------------------------------------------------------------------
    # 1. Check for relocation intent
    # ------------------------------------------------------------------
    relocation = detect_relocation(question)
    if relocation:
        item_key = relocation["item"].lower()
        matched_tag = tag_lookup.get(item_key)

        if matched_tag:
            update_tag_location(
                tag_id=matched_tag["id"],
                new_position=relocation["new_location"],
            )
            answer = (
                f"Got it! I've updated your {relocation['item']} location to "
                f"{relocation['new_location']}. I'll remember that for next time."
            )
        else:
            answer = (
                f"Thanks for letting me know! I don't have your {relocation['item']} "
                f"tagged yet, but I'll let your caregiver know so they can add it."
            )

        session.add_message("assistant", answer)
        await _maybe_save_session(session)

        return QueryResponse(
            answer=answer,
            source_tags=[],
            confidence=ConfidenceLevel.high,
        )

    # ------------------------------------------------------------------
    # 2. Check for removal intent
    # ------------------------------------------------------------------
    removed_item = detect_removal(question)
    if removed_item:
        item_key = removed_item.lower()
        matched_tag = tag_lookup.get(item_key)

        if matched_tag:
            # Mark as stale/low confidence rather than deleting
            handle_contradiction(matched_tag["id"], matched_tag.get("room_id", ""))
            answer = (
                f"Noted! I've marked your {removed_item} as no longer there. "
                f"If you get a replacement, just let me know where you put it."
            )
        else:
            answer = f"Okay, noted about the {removed_item}."

        session.add_message("assistant", answer)
        await _maybe_save_session(session)

        return QueryResponse(
            answer=answer,
            source_tags=[],
            confidence=ConfidenceLevel.high,
        )

    # ------------------------------------------------------------------
    # 3. Check for contradiction
    # ------------------------------------------------------------------
    redirect_message = None
    is_repeat = False
    drift_detected = False

    if detect_contradiction(question):
        # Find the most recently referenced tag to mark as low confidence
        for label_lower, tag in tag_lookup.items():
            if label_lower in question.lower():
                result = handle_contradiction(tag["id"], tag.get("room_id", ""))
                answer = result["message"]
                session.add_message("assistant", answer)
                await _maybe_save_session(session)

                # Fire a caregiver alert for contradictions
                await _fire_alert(
                    patient_id=user_id,
                    home_id=home_id,
                    alert_type=AlertType.CONTRADICTION,
                    level=AlertLevel.INFO,
                    message=f"Patient reported '{label_lower}' is not in its tagged location.",
                )

                return QueryResponse(
                    answer=answer,
                    source_tags=[],
                    confidence=ConfidenceLevel.low,
                )

        # Generic contradiction (no specific tag matched)
        answer = (
            "I'm sorry that wasn't right! Can you tell me which item "
            "you're looking for? I'll update the location."
        )
        session.add_message("assistant", answer)
        return QueryResponse(
            answer=answer,
            source_tags=[],
            confidence=ConfidenceLevel.low,
        )

    # ------------------------------------------------------------------
    # 4. Check for cognitive drift (repeats, confusion)
    # ------------------------------------------------------------------
    repeat_event = session.detect_repeat(question)
    if repeat_event:
        is_repeat = True
        drift_detected = True
        redirect_message = session.generate_redirect({
            "type": "repeat",
            "detail": repeat_event,
        })

    confusion_type = session.detect_confusion(question)
    if confusion_type and not drift_detected:
        drift_detected = True
        redirect_message = session.generate_redirect({
            "type": confusion_type,
            "detail": {"message": question},
        })

    # ------------------------------------------------------------------
    # 5. Normal RAG flow with decayed confidence
    # ------------------------------------------------------------------
    if not tags:
        answer = (
            "I don't have any rooms tagged in your home yet "
            "-- ask your caregiver to add some photos."
        )
        session.add_message("assistant", answer)
        return QueryResponse(
            answer=answer,
            source_tags=[],
            confidence=ConfidenceLevel.low,
            redirect_message=redirect_message,
            is_repeat=is_repeat,
            drift_detected=drift_detected,
        )

    # Build context with confidence decay annotations
    context_lines: list[str] = []
    for tag in tags:
        room_name = tag.get("rooms", {}).get("name", "Unknown Room")
        label = tag.get("label", "")
        position = tag.get("position", "")
        notes = tag.get("notes", "")
        effective_conf = get_effective_confidence(tag)
        conf_note = get_confidence_note(tag)

        context_lines.append(
            f"Room: {room_name} | Object: {label} | Position: {position} "
            f"| Notes: {notes} | Confidence: {effective_conf} {conf_note}"
        )

    context = "\n".join(context_lines)

    # Query Gemini
    try:
        answer = await query_with_context(context, question)
    except Exception as e:
        logger.error("query_gemini_error home_id=%s error=%s", home_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to process query",
        )

    # Prepend redirect message if drift was detected
    if redirect_message:
        answer = f"{redirect_message}\n\n{answer}"

    # Identify which tags were referenced in the answer
    source_tags: list[SourceTag] = []
    for label_lower, tag in tag_lookup.items():
        if label_lower in answer.lower():
            room_name = tag.get("rooms", {}).get("name", "Unknown Room")
            photo_path = tag.get("photos", {}).get("storage_path", "")
            source_tags.append(SourceTag(
                label=tag.get("label", ""),
                room_name=room_name,
                position=tag.get("position", ""),
                photo_url=photo_path,
            ))

    # Determine confidence based on effective (decayed) confidence
    if source_tags:
        # Use the best effective confidence among matched tags
        conf_levels = [get_effective_confidence(tag_lookup.get(st.label.lower(), {}))
                       for st in source_tags]
        if "high" in conf_levels:
            confidence = ConfidenceLevel.high
        elif "medium" in conf_levels:
            confidence = ConfidenceLevel.medium
        else:
            confidence = ConfidenceLevel.low
    elif "don't have" in answer.lower() or "not tagged" in answer.lower():
        confidence = ConfidenceLevel.low
    else:
        confidence = ConfidenceLevel.medium

    # ------------------------------------------------------------------
    # 6. Log interaction to session
    # ------------------------------------------------------------------
    session.add_message("assistant", answer)

    # Record which items were asked about (for repeat detection)
    for st in source_tags:
        session.record_asked_item(st.label, answer)

    await _maybe_save_session(session)

    # ------------------------------------------------------------------
    # 7. Check if caregiver should be alerted
    # ------------------------------------------------------------------
    alert_info = session.should_alert_caregiver()
    if alert_info:
        alert_type_str = alert_info.get("alert_type", "confusion")
        try:
            alert_type = AlertType(alert_type_str)
        except ValueError:
            alert_type = AlertType.CONFUSION

        level = AlertLevel.URGENT if alert_type == AlertType.DISTRESS else AlertLevel.WARNING
        await _fire_alert(
            patient_id=user_id,
            home_id=home_id,
            alert_type=alert_type,
            level=level,
            message=alert_info.get("message", ""),
        )

    logger.info(
        "query_ask home_id=%s question_length=%d source_tags=%d drift=%s",
        home_id, len(question), len(source_tags), drift_detected,
    )

    return QueryResponse(
        answer=answer,
        source_tags=source_tags,
        confidence=confidence,
        redirect_message=redirect_message,
        is_repeat=is_repeat,
        drift_detected=drift_detected,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _maybe_save_session(session) -> None:
    """Best-effort session persistence -- never fails the request."""
    try:
        await save_session_to_db(session)
    except Exception as exc:
        logger.warning("session_save_skipped error=%s", exc)


async def _fire_alert(
    patient_id: str,
    home_id: str,
    alert_type: AlertType,
    level: AlertLevel,
    message: str,
) -> None:
    """Best-effort alert creation -- never fails the request."""
    try:
        alert = CaregiverAlert(
            level=level,
            patient_id=patient_id,
            home_id=home_id,
            message=message,
            alert_type=alert_type,
        )
        await create_alert(alert)
    except Exception as exc:
        logger.warning("alert_fire_failed error=%s", exc)
