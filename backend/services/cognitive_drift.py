"""
Cognitive Drift Detector for MemoryMap.

Tracks conversation sessions with dementia patients, detects repeated
questions, confusion signals, and distress. Generates gentle redirects
and triggers caregiver alerts when needed.
"""

import re
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

from services.tag_store import _get_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Simple TF-IDF-like similarity (avoids external dependencies)
# ---------------------------------------------------------------------------

_STOP_WORDS: set[str] = {
    "where", "is", "my", "the", "are", "did", "i", "put", "find", "can",
    "a", "an", "to", "do", "we", "keep", "need", "want", "some", "it",
    "in", "on", "of", "for", "up", "have", "has", "was", "be", "at",
    "this", "that", "with", "r", "u", "seen", "left", "got", "seen",
    "kitchen", "bedroom", "bathroom", "living", "room", "house",
}

# Maps any alternate word → canonical word used in tag labels
_SYNONYM_MAP: dict[str, str] = {
    "specs": "glasses",
    "spectacles": "glasses",
    "eyeglasses": "glasses",
    "eyewear": "glasses",
    "meds": "medicine",
    "medication": "medicine",
    "medications": "medicine",
    "pills": "medicine",
    "pill": "medicine",
    "tablets": "medicine",
    "tablet": "medicine",
    "prescription": "medicine",
    "mobile": "phone",
    "cell": "phone",
    "cellphone": "phone",
    "handphone": "phone",
    "smartphone": "phone",
    "telly": "remote",
    "television": "tv",
    "remote": "remote",
    "bag": "purse",
    "handbag": "purse",
    "pocketbook": "purse",
    "hearing": "hearing aid",
    "earpiece": "hearing aid",
    "bp": "blood pressure",
    "keys": "keys",
    "key": "keys",
    "wallet": "wallet",
    "charger": "charger",
    "notebook": "book",
    "notepad": "book",
    "journal": "book",
    "diary": "book",
    "cup": "bottle",
    "glass": "glasses",
}


def _normalize_synonyms(text: str) -> str:
    """Replace known synonym words with their canonical form."""
    words = text.lower().split()
    normalized = [_SYNONYM_MAP.get(w, w) for w in words]
    return " ".join(normalized)


def _tokenize(text: str) -> list[str]:
    """Normalize synonyms, then extract word tokens removing stop words."""
    normalized = _normalize_synonyms(text)
    words = re.findall(r"\w+", normalized)
    return [w for w in words if w not in _STOP_WORDS]


def _cosine_similarity(tokens_a: list[str], tokens_b: list[str]) -> float:
    """
    Compute a simple term-overlap cosine similarity between two token lists.
    This is a lightweight stand-in for full TF-IDF.
    """
    if not tokens_a or not tokens_b:
        return 0.0

    vocab = set(tokens_a) | set(tokens_b)
    freq_a = {w: tokens_a.count(w) for w in vocab}
    freq_b = {w: tokens_b.count(w) for w in vocab}

    dot = sum(freq_a.get(w, 0) * freq_b.get(w, 0) for w in vocab)
    mag_a = sum(v ** 2 for v in freq_a.values()) ** 0.5
    mag_b = sum(v ** 2 for v in freq_b.values()) ** 0.5

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# Confusion signal patterns
# ---------------------------------------------------------------------------

_CONFUSION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("confusion", re.compile(r"\bwait\s+what\b", re.IGNORECASE)),
    ("confusion", re.compile(r"\bwhat\s+was\s+i\b", re.IGNORECASE)),
    ("memory_lapse", re.compile(r"\bi\s+forgot\b", re.IGNORECASE)),
    ("abandon", re.compile(r"\bnevermind\b", re.IGNORECASE)),
    ("hesitation", re.compile(r"\b(?:um+|hmm+)\b", re.IGNORECASE)),
    ("memory_lapse", re.compile(r"\bi\s+don'?t\s+remember\b", re.IGNORECASE)),
    ("confusion", re.compile(r"\bwhat\s+did\s+i\s+say\b", re.IGNORECASE)),
    ("confusion", re.compile(r"\bwhere\s+was\s+i\b", re.IGNORECASE)),
    ("hesitation", re.compile(r"\bhold\s+on\b", re.IGNORECASE)),
    ("confusion", re.compile(r"\bi'?m\s+confused\b", re.IGNORECASE)),
]

# Distress keywords for caregiver alerting
_DISTRESS_KEYWORDS: list[re.Pattern] = [
    re.compile(r"\bhelp\b", re.IGNORECASE),
    re.compile(r"\bscared\b", re.IGNORECASE),
    re.compile(r"\bdon'?t\s+know\b", re.IGNORECASE),
    re.compile(r"\bi(?:'?m)?\s+lost\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Conversation Session
# ---------------------------------------------------------------------------

@dataclass
class ConversationSession:
    """Tracks a single conversation session with a patient."""

    session_id: str
    user_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    messages: list[dict] = field(default_factory=list)
    asked_items: list[dict] = field(default_factory=list)
    drift_events: list[dict] = field(default_factory=list)
    alerted_counts: dict = field(default_factory=dict)  # item → last count we alerted at

    # ------------------------------------------------------------------
    # Message tracking
    # ------------------------------------------------------------------

    def add_message(self, role: str, content: str) -> None:
        """Record a message in the session history."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def record_asked_item(self, item: str, answer: str) -> None:
        """Record that the patient asked about an item and what answer was given."""
        self.asked_items.append({
            "item": item,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "answer_given": answer,
        })

    # ------------------------------------------------------------------
    # Repeat detection
    # ------------------------------------------------------------------

    def detect_repeat(self, current_query: str) -> Optional[dict]:
        """
        Compare the current query against previously asked items using
        token-overlap cosine similarity.

        Returns a repeat-event dict if similarity > 0.5 and within 30 min,
        or None.
        """
        now = datetime.now(timezone.utc)
        current_tokens = _tokenize(current_query)

        for asked in reversed(self.asked_items):
            asked_time = datetime.fromisoformat(asked["timestamp"])
            minutes_ago = (now - asked_time).total_seconds() / 60

            if minutes_ago > 30:
                # Older than 30 minutes -- stop checking
                break

            asked_tokens = _tokenize(asked["item"])
            similarity = _cosine_similarity(current_tokens, asked_tokens)

            if similarity > 0.5:
                event = {
                    "is_repeat": True,
                    "original_query": asked["item"],
                    "original_answer": asked["answer_given"],
                    "minutes_ago": round(minutes_ago, 1),
                }
                self.drift_events.append({
                    "type": "repeat",
                    "timestamp": now.isoformat(),
                    "detail": event,
                })
                logger.info(
                    "repeat_detected user_id=%s item=%s minutes_ago=%.1f",
                    self.user_id, asked["item"], minutes_ago,
                )
                return event

        return None

    # ------------------------------------------------------------------
    # Confusion signal detection
    # ------------------------------------------------------------------

    def detect_confusion(self, message: str) -> Optional[str]:
        """
        Detect confusion signals in the patient's message.

        Also detects "trailing off" -- very short messages (< 4 words)
        following a longer message (> 8 words).

        Returns the confusion type string or None.
        """
        # Check explicit patterns
        for signal_type, pattern in _CONFUSION_PATTERNS:
            if pattern.search(message):
                self.drift_events.append({
                    "type": signal_type,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "detail": {"message": message},
                })
                logger.info(
                    "confusion_detected user_id=%s type=%s",
                    self.user_id, signal_type,
                )
                return signal_type

        # Check for trailing off (short message after a longer one)
        user_messages = [m for m in self.messages if m["role"] == "user"]
        if user_messages:
            current_word_count = len(message.split())
            prev_word_count = len(user_messages[-1]["content"].split())
            if current_word_count < 4 and prev_word_count > 8:
                self.drift_events.append({
                    "type": "trailing_off",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "detail": {"message": message},
                })
                logger.info(
                    "trailing_off_detected user_id=%s",
                    self.user_id,
                )
                return "trailing_off"

        return None

    # ------------------------------------------------------------------
    # Gentle redirect generation
    # ------------------------------------------------------------------

    def generate_redirect(self, drift_event: dict) -> str:
        """
        Generate a kind, non-patronizing redirect based on the drift event.
        """
        event_type = drift_event.get("type", "")
        detail = drift_event.get("detail", {})

        # Find the most recently asked item for context
        last_item = None
        last_location = None
        if self.asked_items:
            last = self.asked_items[-1]
            last_item = last.get("item")
            last_location = last.get("answer_given", "")

        if event_type == "repeat":
            item = detail.get("original_query", last_item or "that item")
            answer = detail.get("original_answer", last_location or "")
            minutes = detail.get("minutes_ago", "a few")
            return (
                f"You asked about your {item} {minutes} minutes ago. "
                f"{answer} Would you still like help with that?"
            )

        if event_type in ("confusion", "memory_lapse", "hesitation", "abandon"):
            if last_item and last_location:
                return (
                    f"It sounds like you might be trying to find something. "
                    f"Your most recently asked item was {last_item}. "
                    f"{last_location} Can I help with that?"
                )
            return (
                "No worries at all! Is there something I can help you find?"
            )

        if event_type == "trailing_off":
            if last_item and last_location:
                return (
                    f"No worries! You were looking for your {last_item}. "
                    f"{last_location}"
                )
            return "No worries! Let me know if there's something you need."

        return "I'm here to help. What are you looking for?"

    # ------------------------------------------------------------------
    # Caregiver alert triggers
    # ------------------------------------------------------------------

    def should_alert_caregiver(self) -> Optional[dict]:
        """
        Determine whether the caregiver should be alerted.

        Triggers:
            - Same item asked 4+ times in 1 hour
            - 3+ confusion signals in 30 minutes
            - Distress keywords detected
        """
        now = datetime.now(timezone.utc)

        # --- Check repeated item queries (4+ in 1 hour) ---
        one_hour_items: dict[str, int] = {}
        for asked in self.asked_items:
            asked_time = datetime.fromisoformat(asked["timestamp"])
            if (now - asked_time).total_seconds() <= 3600:
                item = asked["item"].lower()
                one_hour_items[item] = one_hour_items.get(item, 0) + 1

        for item, count in one_hour_items.items():
            if count >= 3:
                last_alerted = self.alerted_counts.get(item, 0)
                if count == last_alerted:
                    continue  # already fired alert at this count, skip
                self.alerted_counts[item] = count
                logger.warning(
                    "caregiver_alert_repeat user_id=%s item=%s count=%d",
                    self.user_id, item, count,
                )
                return {
                    "alert_type": "repeat_query",
                    "message": (
                        f"Patient has asked about '{item}' {count} times "
                        f"in the last hour."
                    ),
                }

        # --- Check confusion signals (3+ in 30 minutes) ---
        recent_confusion = [
            e for e in self.drift_events
            if e["type"] in ("confusion", "memory_lapse", "hesitation",
                             "abandon", "trailing_off")
            and (now - datetime.fromisoformat(e["timestamp"])).total_seconds() <= 1800
        ]
        if len(recent_confusion) >= 3:
            logger.warning(
                "caregiver_alert_confusion user_id=%s count=%d",
                self.user_id, len(recent_confusion),
            )
            return {
                "alert_type": "confusion",
                "message": (
                    f"Patient has shown {len(recent_confusion)} confusion "
                    f"signals in the last 30 minutes."
                ),
            }

        # --- Check distress keywords in recent messages ---
        recent_messages = [
            m for m in self.messages
            if m["role"] == "user"
            and (now - datetime.fromisoformat(m["timestamp"])).total_seconds() <= 600
        ]
        for msg in recent_messages:
            for pattern in _DISTRESS_KEYWORDS:
                if pattern.search(msg["content"]):
                    logger.warning(
                        "caregiver_alert_distress user_id=%s keyword=%s",
                        self.user_id, pattern.pattern,
                    )
                    return {
                        "alert_type": "distress",
                        "message": (
                            "Patient may be in distress. Recent message: "
                            f"'{msg['content'][:100]}'"
                        ),
                    }

        return None


# ---------------------------------------------------------------------------
# Session Store (in-memory with best-effort Supabase persistence)
# ---------------------------------------------------------------------------

_sessions: dict[str, ConversationSession] = {}


def get_or_create_session(user_id: str) -> ConversationSession:
    """
    Get the active session for a user, or create a new one.

    Sessions are stored in-memory for fast access.
    """
    if user_id in _sessions:
        return _sessions[user_id]

    import uuid
    session = ConversationSession(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
    )
    _sessions[user_id] = session
    logger.info("session_created user_id=%s session_id=%s", user_id, session.session_id)
    return session


async def save_session_to_db(session: ConversationSession) -> None:
    """
    Persist session data to Supabase `conversation_logs` table.

    Best-effort: silently logs warnings if the table doesn't exist yet.
    """
    try:
        client = _get_client()
        client.table("conversation_logs").upsert({
            "session_id": session.session_id,
            "user_id": session.user_id,
            "started_at": session.started_at.isoformat(),
            "message_count": len(session.messages),
            "drift_event_count": len(session.drift_events),
            "asked_items_count": len(session.asked_items),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        logger.info(
            "session_saved session_id=%s messages=%d",
            session.session_id, len(session.messages),
        )
    except Exception as exc:
        # Table may not exist yet -- that's fine
        logger.warning(
            "session_save_failed session_id=%s error=%s",
            session.session_id, exc,
        )
