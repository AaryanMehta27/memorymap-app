from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
import uuid


class ConfidenceLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


# --- Vision Analyze ---

class VisionAnalyzeRequest(BaseModel):
    room_id: str
    image_base64: str
    image_mime_type: str = Field(
        ..., pattern=r"^image/(jpeg|png|webp)$"
    )


class Tag(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str
    position: str
    confidence: ConfidenceLevel
    notes: str


class VisionAnalyzeResponse(BaseModel):
    room_id: str
    tags: list[Tag]
    raw_description: str


# --- Query ---

class QueryRequest(BaseModel):
    home_id: str
    question: str


class SourceTag(BaseModel):
    label: str
    room_name: str
    position: str
    photo_url: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    source_tags: list[SourceTag]
    confidence: ConfidenceLevel
    redirect_message: Optional[str] = None
    is_repeat: bool = False
    drift_detected: bool = False


# --- Floorplan ---

class FloorplanTagInput(BaseModel):
    id: str
    label: str
    position: str


class FloorplanRequest(BaseModel):
    room_id: str
    room_shape: str = "rectangle"
    room_width_px: int
    room_height_px: int
    tags: list[FloorplanTagInput]


class TagPlacement(BaseModel):
    tag_id: str
    label: str
    x: float
    y: float


class FloorplanResponse(BaseModel):
    placements: list[TagPlacement]


# --- Sweep (Stretch) ---

class SweepFrame(BaseModel):
    image_base64: str
    image_mime_type: str = Field(
        ..., pattern=r"^image/(jpeg|png|webp)$"
    )


class SweepRequest(BaseModel):
    room_id: str
    frames: list[SweepFrame] = Field(..., min_length=3, max_length=5)


class SweepResponse(BaseModel):
    room_id: str
    tags: list[Tag]
    raw_description: str


# --- Alerts ---

class AlertResponse(BaseModel):
    id: str
    level: str
    message: str
    alert_type: str
    timestamp: str
    acknowledged: bool = False


class AlertListResponse(BaseModel):
    alerts: list[AlertResponse]
