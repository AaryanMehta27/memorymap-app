import base64
from fastapi import HTTPException, status

MAX_IMAGE_SIZE = 4 * 1024 * 1024  # 4MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


def validate_and_decode_image(image_base64: str, mime_type: str) -> bytes:
    """Validate image size and MIME type, return decoded bytes."""
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type: {mime_type}. Allowed: jpeg, png, webp",
        )

    try:
        image_bytes = base64.b64decode(image_base64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 image data",
        )

    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds {MAX_IMAGE_SIZE // (1024*1024)}MB limit",
        )

    return image_bytes
