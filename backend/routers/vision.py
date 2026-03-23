from fastapi import APIRouter, Depends
from services.auth import require_auth

router = APIRouter(tags=["vision"])


# TODO: POST /analyze — accept a single room photo (base64), send to Gemini 2.0 Flash,
# return extracted object tags with positions. Save tags to Supabase via tag_store.
# - Validate image size (<4MB) and MIME type (jpeg, png, webp)
# - Retry once on malformed Gemini JSON response
# - Never log base64 image data


# TODO: POST /sweep — accept 3-5 frames of the same room, send all to Gemini in one call,
# return merged deduplicated tags. (Stretch goal — build after Features 1-3)
