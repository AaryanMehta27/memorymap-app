# MemoryMap

An AI-powered home layout app that helps patients with memory loss locate their belongings. Caregivers photograph and tag rooms; patients query the map conversationally.

## Team
- Person A: AI pipeline (FastAPI + Gemini) — `/backend`
- Person B: Product layer (Next.js + Supabase) — `/frontend`

## Tech Stack
- Frontend: Next.js 14, Tailwind CSS, shadcn/ui, Konva.js
- Backend: Python 3.11, FastAPI, Google Gemini 2.0 Flash
- Database + Auth + Storage: Supabase
- Deployment: Vercel (frontend), Render (backend)

## Getting Started

### Backend (Person A)
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # fill in your keys
uvicorn main:app --reload
```

### Frontend (Person B)
```bash
cd frontend
npm install
cp .env.local.example .env.local  # fill in your keys
npm run dev
```

## Branch Strategy
- `main` — stable, deployable code only
- `feature/ai-pipeline` — Person A's work
- `feature/product-layer` — Person B's work
- Merge to main via pull request after testing

## Environment Variables
See `backend/.env.example` and `frontend/.env.local.example`. Never commit `.env` or `.env.local` files.

## Privacy
Photos are processed by Google Gemini API and are never stored on MemoryMap servers. See PRIVACY.md for full disclosure.
