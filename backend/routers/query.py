from fastapi import APIRouter, Depends
from services.auth import require_auth

router = APIRouter(tags=["query"])


# TODO: POST /ask — accept a natural language question + home_id,
# fetch relevant tags from Supabase, construct context window,
# send to Gemini 2.0 Flash (text-only), return grounded answer
# with source tags and photo URLs.
