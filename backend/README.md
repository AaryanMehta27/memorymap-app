# MemoryMap Backend — AI Service

FastAPI service that handles all AI/vision processing for MemoryMap.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/vision/analyze` | Analyze a single room photo, extract object tags |
| POST | `/api/vision/sweep` | Analyze multiple frames of same room (stretch goal) |
| POST | `/api/query/ask` | Conversational query — "Where are my pills?" |
| POST | `/api/floorplan/suggest-positions` | Suggest pixel coordinates for tags on floor plan |
| GET | `/health` | Health check |

## Auth

All endpoints (except `/health`) require a valid Supabase JWT in the `Authorization: Bearer <token>` header. The backend validates this token using the `SUPABASE_JWT_SECRET`.

## Privacy Disclosures for Frontend

Person B must display the following notices in the frontend UI:

1. **Before photo capture**: "Your photo will be sent to Google's Gemini AI for analysis. It will not be stored on our servers."
2. **On the Settings page**: "Photos are processed in-memory only and are never saved to MemoryMap servers. Your room data is stored in your private database and can be deleted at any time."
3. **During onboarding**: "MemoryMap uses AI to identify objects in your room photos. Photos are processed by Google Gemini API and are not retained."
4. **In the app footer or About page**: Link to PRIVACY.md content.

## Environment Variables

See `.env.example` for required configuration.

## Running Locally

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # fill in your keys
uvicorn main:app --reload
```
