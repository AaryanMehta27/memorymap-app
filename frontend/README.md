# MemoryMap Frontend

Next.js 14 app with Supabase auth, room/photo CRUD, and conversational query UI.

## Person B's Scope
- Auth system (login, register, OTP verification)
- Dashboard with room overview
- Room CRUD with photo capture/upload
- Floor plan canvas (Konva.js) with draggable tags
- Query interface for patients
- Settings page with account management

## Getting Started
```bash
npm install
cp .env.local.example .env.local  # fill in your keys
npm run dev
```

## AI Integration
The frontend calls the backend AI service at `NEXT_PUBLIC_AI_API_URL`.
See `backend/README.md` for endpoint documentation.
