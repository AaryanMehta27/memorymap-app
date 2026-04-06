"""
Caregiver Alert System for MemoryMap.

Provides a simple alerting mechanism that stores alerts to Supabase
(best-effort) with an in-memory queue as fallback.
"""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

from services.tag_store import _get_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Alert types and models
# ---------------------------------------------------------------------------

class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    URGENT = "urgent"


class AlertType(str, Enum):
    REPEAT_QUERY = "repeat_query"
    CONFUSION = "confusion"
    CONTRADICTION = "contradiction"
    STALE_TAG = "stale_tag"
    DISTRESS = "distress"


@dataclass
class CaregiverAlert:
    """A single caregiver alert."""

    level: AlertLevel
    patient_id: str
    home_id: str
    message: str
    alert_type: AlertType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    acknowledged: bool = False


# ---------------------------------------------------------------------------
# In-memory fallback queue (used when Supabase table doesn't exist)
# ---------------------------------------------------------------------------

_alert_queue: list[CaregiverAlert] = []


# ---------------------------------------------------------------------------
# Alert operations
# ---------------------------------------------------------------------------

def _alert_to_dict(alert: CaregiverAlert) -> dict:
    """Convert an alert to a serializable dict."""
    return {
        "id": alert.id,
        "level": alert.level.value,
        "patient_id": alert.patient_id,
        "home_id": alert.home_id,
        "message": alert.message,
        "alert_type": alert.alert_type.value,
        "timestamp": alert.timestamp.isoformat(),
        "acknowledged": alert.acknowledged,
    }


async def create_alert(alert: CaregiverAlert) -> dict:
    """
    Store a caregiver alert to Supabase. Falls back to in-memory queue
    if the table doesn't exist yet.

    Returns the alert as a dict.
    """
    alert_dict = _alert_to_dict(alert)

    try:
        client = _get_client()
        client.table("caregiver_alerts").insert(alert_dict).execute()
        logger.info(
            "alert_created id=%s type=%s level=%s home_id=%s",
            alert.id, alert.alert_type.value, alert.level.value, alert.home_id,
        )
    except Exception as exc:
        # Table may not exist yet -- store in memory
        logger.warning("alert_db_failed id=%s error=%s (using in-memory queue)", alert.id, exc)
        _alert_queue.append(alert)

    return alert_dict


async def get_recent_alerts(home_id: str, hours: int = 24) -> list[dict]:
    """
    Fetch recent caregiver alerts for a home.

    Tries Supabase first, falls back to in-memory queue.
    """
    try:
        client = _get_client()
        # Calculate cutoff timestamp
        cutoff = datetime.now(timezone.utc)
        from datetime import timedelta
        cutoff = (cutoff - timedelta(hours=hours)).isoformat()

        result = (
            client.table("caregiver_alerts")
            .select("*")
            .eq("home_id", home_id)
            .gte("timestamp", cutoff)
            .order("timestamp", desc=True)
            .execute()
        )
        logger.info(
            "alerts_fetched home_id=%s count=%d",
            home_id, len(result.data),
        )
        return result.data
    except Exception as exc:
        logger.warning("alerts_fetch_failed home_id=%s error=%s (using in-memory)", home_id, exc)

    # Fallback: return from in-memory queue
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return [
        _alert_to_dict(a)
        for a in _alert_queue
        if a.home_id == home_id and a.timestamp >= cutoff
    ]


async def acknowledge_alert(alert_id: str) -> Optional[dict]:
    """
    Mark an alert as acknowledged.

    Returns the updated alert dict, or None if not found.
    """
    try:
        client = _get_client()
        result = (
            client.table("caregiver_alerts")
            .update({"acknowledged": True})
            .eq("id", alert_id)
            .execute()
        )
        if result.data:
            logger.info("alert_acknowledged id=%s", alert_id)
            return result.data[0]
    except Exception as exc:
        logger.warning("alert_ack_failed id=%s error=%s", alert_id, exc)

    # Fallback: check in-memory queue
    for alert in _alert_queue:
        if alert.id == alert_id:
            alert.acknowledged = True
            logger.info("alert_acknowledged_memory id=%s", alert_id)
            return _alert_to_dict(alert)

    return None
