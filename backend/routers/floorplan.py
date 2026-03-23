from fastapi import APIRouter, Depends
from services.auth import require_auth

router = APIRouter(tags=["floorplan"])


# TODO: POST /suggest-positions — accept tag list with position descriptions
# and room canvas dimensions, use Gemini to interpret position descriptions
# as fractions of canvas dimensions, return x/y pixel coordinates for Konva.js.
