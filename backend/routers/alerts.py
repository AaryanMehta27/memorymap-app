"""
Alerts router for MemoryMap.

Provides endpoints for caregivers to view and acknowledge alerts.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from models.schemas import AlertListResponse, AlertResponse
from services.auth import require_auth
from services.caregiver_alerts import get_recent_alerts, acknowledge_alert

logger = logging.getLogger(__name__)

router = APIRouter(tags=["alerts"])


@router.get("/{home_id}", response_model=AlertListResponse)
async def list_alerts(
    home_id: str,
    hours: int = 24,
    user: dict = Depends(require_auth),
):
    """Get recent caregiver alerts for a home."""
    alerts_data = await get_recent_alerts(home_id, hours=hours)

    alerts = []
    for a in alerts_data:
        alerts.append(AlertResponse(
            id=a.get("id", ""),
            level=a.get("level", "info"),
            message=a.get("message", ""),
            alert_type=a.get("alert_type", ""),
            timestamp=a.get("timestamp", ""),
            acknowledged=a.get("acknowledged", False),
        ))

    logger.info("alerts_listed home_id=%s count=%d", home_id, len(alerts))
    return AlertListResponse(alerts=alerts)


@router.post("/{alert_id}/acknowledge")
async def ack_alert(
    alert_id: str,
    user: dict = Depends(require_auth),
):
    """Mark an alert as acknowledged."""
    result = await acknowledge_alert(alert_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    logger.info("alert_acked id=%s", alert_id)
    return {"acknowledged": True, "alert_id": alert_id}
