from pydantic import BaseModel

# TODO: Define all Pydantic request/response models:
# - VisionAnalyzeRequest (room_id, image_base64, image_mime_type)
# - Tag (id, label, position, confidence, notes)
# - VisionAnalyzeResponse (room_id, tags, raw_description)
# - QueryRequest (home_id, question)
# - SourceTag (label, room_name, position, photo_url)
# - QueryResponse (answer, source_tags, confidence)
# - FloorplanRequest (room_id, room_shape, room_width_px, room_height_px, tags)
# - TagPlacement (tag_id, label, x, y)
# - FloorplanResponse (placements)
# - SweepRequest (room_id, frames: list of image data)
