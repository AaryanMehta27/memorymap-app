# Image validation and processing utilities

# TODO: validate_image(base64_data, mime_type) -> bytes
# - Decode base64 string
# - Check file size (<4MB), return HTTP 413 if too large
# - Validate MIME type (image/jpeg, image/png, image/webp only)
# - Return raw bytes for Gemini API
