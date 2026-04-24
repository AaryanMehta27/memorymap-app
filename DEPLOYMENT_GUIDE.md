# MemoryMap Deployment Guide
Frontend → Vercel | Backend → Railway | AI → Groq (free)

---

## Step 1 — Get a free Groq API key (2 min)

1. Go to https://console.groq.com and sign up (free)
2. Click **API Keys** → **Create API Key**
3. Copy the key (starts with `gsk_...`)

---

## Step 2 — Deploy the Backend to Railway (10 min)

1. Go to https://railway.app and sign in with GitHub
2. Click **New Project** → **Deploy from GitHub repo**
3. Select this repo (or upload the `backend/` folder)
4. Railway will auto-detect Python and use the `Procfile`
5. Go to **Variables** tab and add these environment variables:

```
GROQ_API_KEY          = gsk_your_groq_key_here
GROQ_TEXT_MODEL       = llama-3.1-8b-instant
GROQ_VISION_MODEL     = meta-llama/llama-4-scout-17b-16e-instruct
SUPABASE_URL          = https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY  = your_supabase_service_key
SUPABASE_JWT_SECRET   = your_supabase_jwt_secret
ALLOWED_ORIGINS       = https://your-app.vercel.app,http://localhost:3000
```

6. Under **Settings** → **Networking** → click **Generate Domain**
7. Copy your Railway URL — looks like: `https://memorymap-backend-xxxx.railway.app`
8. Test it: visit `https://your-railway-url.railway.app/health` — should return `{"status":"ok"}`

---

## Step 3 — Deploy the Frontend to Vercel (5 min)

1. Go to https://vercel.com and sign in with GitHub
2. Click **Add New** → **Project** → import this repo
3. Set **Root Directory** to `frontend`
4. Go to **Environment Variables** and add:

```
NEXT_PUBLIC_SUPABASE_URL       = https://your-project-id.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY  = your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY      = your_supabase_service_key
NEXT_PUBLIC_AI_API_URL         = https://your-railway-url.railway.app
```

5. Click **Deploy**
6. Your app URL will be: `https://your-project-name.vercel.app`

---

## Step 4 — Update CORS on Railway (1 min)

Go back to Railway → Variables → update `ALLOWED_ORIGINS`:
```
ALLOWED_ORIGINS = https://your-project-name.vercel.app,http://localhost:3000
```

Redeploy the backend (Railway does this automatically when you save variables).

---

## Done!

Your live URLs:
- **Frontend**: `https://your-project-name.vercel.app`
- **Backend**:  `https://your-backend-xxxx.railway.app`

Both are permanent, free, and work 24/7.
