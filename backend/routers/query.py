"""
Query router for MemoryMap.

Handles natural-language questions about where things are in the home,
with integrated tag lifecycle management, cognitive drift detection,
and caregiver alerting.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from rapidfuzz import fuzz
from services.cognitive_drift import _normalize_synonyms

from models.schemas import QueryRequest, QueryResponse, SourceTag, ConfidenceLevel
from services.auth import require_auth
from services.gemini_client import query_with_context
from services.tag_store import get_tags_for_home
from services.tag_lifecycle import (
    detect_relocation,
    detect_removal,
    detect_contradiction,
    handle_contradiction,
    handle_relocation,
    update_tag_location,
    get_effective_confidence,
    get_confidence_note,
    get_in_memory_tags,
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
    question = _normalize_synonyms(request.question)
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
        logger.warning("query_fetch_error home_id=%s error=%s — continuing with empty tags", home_id, str(e))
        tags = []

    # Build a quick label -> [tags] lookup for matching (same item may be in multiple rooms)
    tag_lookup: dict[str, list[dict]] = {}
    for tag in tags:
        label = tag.get("label", "").lower()
        if label:
            tag_lookup.setdefault(label, []).append(tag)

    # ------------------------------------------------------------------
    # 1. Check for relocation intent
    # ------------------------------------------------------------------
    relocation_result = await handle_relocation(question, home_id)
    if relocation_result:
        answer = relocation_result["message"]
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
        matched_tag_list = tag_lookup.get(item_key, [])
        matched_tag = matched_tag_list[0] if matched_tag_list else None

        if matched_tag:
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
        for label_lower, tag_list in tag_lookup.items():
            if label_lower in question.lower():
                tag = tag_list[0]
                result = handle_contradiction(tag["id"], tag.get("room_id", ""))
                answer = result["message"]
                session.add_message("assistant", answer)
                await _maybe_save_session(session)

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
    # Only run repeat detection on genuine location questions so that
    # off-topic questions (e.g. "what colour is my phone?") don't
    # mistakenly match a prior location query for the same item.
    # ------------------------------------------------------------------
    _LOCATION_WORDS = {
        "where", "find", "locate", "which room", "looking for",
        "can't find", "cannot find", "have you seen", "seen my",
        "remind me", "forgot", "forget", "lost my", "put my",
        "help me find", "remember where", "left my",
    }
    _is_location_q = any(w in question.lower() for w in _LOCATION_WORDS)

    repeat_event = session.detect_repeat(question) if _is_location_q else None
    if repeat_event:
        is_repeat = True
        drift_detected = True
        redirect_message = session.generate_redirect({
            "type": "repeat",
            "detail": repeat_event,
        })
        session.add_message("assistant", redirect_message)

        original_item = repeat_event.get("original_query", "")
        original_answer = repeat_event.get("original_answer", "")
        if original_item:
            session.record_asked_item(original_item, original_answer)

        await _maybe_save_session(session)

        alert_info = session.should_alert_caregiver()
        if alert_info:
            alert_type_str = alert_info.get("alert_type", "repeat_query")
            try:
                alert_type = AlertType(alert_type_str)
            except ValueError:
                alert_type = AlertType.CONFUSION
            await _fire_alert(
                patient_id=user_id,
                home_id=home_id,
                alert_type=alert_type,
                level=AlertLevel.WARNING,
                message=alert_info.get("message", ""),
            )
            logger.info("alert_fired user_id=%s home_id=%s type=%s", user_id, home_id, alert_type_str)

        return QueryResponse(
            answer=redirect_message,
            source_tags=[],
            confidence=ConfidenceLevel.medium,
            redirect_message=redirect_message,
            is_repeat=True,
            drift_detected=True,
        )

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
        session.record_asked_item(question, answer)
        await _maybe_save_session(session)

        alert_info = session.should_alert_caregiver()
        if alert_info:
            alert_type_str = alert_info.get("alert_type", "repeat_query")
            try:
                alert_type = AlertType(alert_type_str)
            except ValueError:
                alert_type = AlertType.CONFUSION
            await _fire_alert(
                patient_id=user_id,
                home_id=home_id,
                alert_type=alert_type,
                level=AlertLevel.WARNING,
                message=alert_info.get("message", ""),
            )

        return QueryResponse(
            answer=answer,
            source_tags=[],
            confidence=ConfidenceLevel.low,
            redirect_message=redirect_message,
            is_repeat=is_repeat,
            drift_detected=drift_detected,
        )

    memory_tags = get_in_memory_tags()
    for mt in memory_tags:
        label = mt.get("label", "").lower()
        if label and label not in tag_lookup:
            tags.append(mt)
            tag_lookup[label] = [mt]

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

    try:
        answer = await query_with_context(context, question)
    except Exception as e:
        logger.error("query_gemini_error home_id=%s error=%s", home_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to process query",
        )

    if redirect_message:
        answer = f"{redirect_message}\n\n{answer}"

    # If the AI refused the question as off-topic, skip source tag matching
    _off_topic = "i'm only able to help you locate your belongings" in answer.lower()

    answer_lower = answer.lower()
    source_tags: list[SourceTag] = []
    for label_lower, tag_list in tag_lookup.items():
        if not _off_topic and (label_lower in answer_lower or fuzz.partial_ratio(label_lower, answer_lower) >= 80):
            for tag in tag_list:
                room_name = tag.get("rooms", {}).get("name", "Unknown Room")
                photo_path = tag.get("photos", {}).get("storage_path", "")
                source_tags.append(SourceTag(
                    label=tag.get("label", ""),
                    room_name=room_name,
                    position=tag.get("position", ""),
                    photo_url=photo_path,
                ))

    if source_tags:
        conf_levels = [
            get_effective_confidence(tag)
            for st in source_tags
            for tag in tag_lookup.get(st.label.lower(), [{}])
        ]
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

    # Record asked items — always record so repeat counter works even without matched tags
    if source_tags:
        for st in source_tags:
            session.record_asked_item(st.label, answer)
    else:
        session.record_asked_item(question, answer)

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
        logger.info("alert_fired user_id=%s home_id=%s type=%s", user_id, home_id, alert_type_str)

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
