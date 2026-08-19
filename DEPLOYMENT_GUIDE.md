# ─────────────────────────────────────────────────────────────────────────────
# Polymath.ai — Full Deployment Guide
# Frontend → Vercel | Backend → Railway
# ─────────────────────────────────────────────────────────────────────────────

## Why This Setup?

| Component | Platform | URL | Why |
|---|---|---|---|
| React UI | **Vercel** | `polymath-ai.vercel.app` | Free, instant CDN, automatic HTTPS |
| FastAPI Backend | **Railway** | `polymath-ai.up.railway.app` | Persistent disk (ChromaDB), no timeout limits, free tier |

---

## STEP 1 — Deploy the Backend to Railway

### 1A. Create a GitHub repository

Push your **entire** `polymath-ai/` project to GitHub:

```bash
cd C:\Users\A-Prasad\.gemini\antigravity\scratch\polymath-ai

git init
git add .
git commit -m "Initial Polymath.ai deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/polymath-ai-backend.git
git push -u origin main
```

### 1B. Create a Railway project

1. Go to [railway.app](https://railway.app) → **"Start a New Project"**
2. Click **"Deploy from GitHub repo"**
3. Select your `polymath-ai-backend` repo
4. Railway will detect the `Dockerfile` and start building automatically

### 1C. Set Environment Variables on Railway

In your Railway project dashboard → **Variables** tab, add:

| Variable | Value |
|---|---|
| `GOOGLE_API_KEY` | Your Google Gemini API key |
| `POLYMATH_API_KEY` | *(Optional)* Any secret key you want |

### 1D. Get your Railway backend URL

After deployment, Railway gives you a URL like:
```
https://polymath-ai-backend-production.up.railway.app
```

**Copy this URL — you need it in Step 2!**

---

## STEP 2 — Deploy the Frontend to Vercel

### 2A. Create a separate GitHub repo for the frontend

```bash
cd C:\Users\A-Prasad\.gemini\antigravity\scratch\polymath-ai\frontend

git init
git add .
git commit -m "Polymath.ai frontend"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/polymath-ai-frontend.git
git push -u origin main
```

### 2B. Deploy on Vercel

1. Go to [vercel.com](https://vercel.com) → **"Add New Project"**
2. Import your `polymath-ai-frontend` repo
3. Vercel auto-detects Vite — click **Deploy**

### 2C. Set the Backend URL Environment Variable

In your Vercel project → **Settings → Environment Variables**, add:

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://polymath-ai-backend-production.up.railway.app` |

> **Important:** After adding this variable, go to **Deployments → Redeploy** so Vite bakes the URL into the build.

---

## STEP 3 — Enable CORS on the Backend for Vercel Domain

Update `api/server.py` to allow requests from your Vercel domain. The code already allows all origins (`*`) so this should work immediately!

---

## STEP 4 — Test the Live Deployment

Once both are live, open your Vercel URL (e.g. `https://polymath-ai.vercel.app`) and test:

- ✅ Ask a CS question
- ✅ Upload a PDF
- ✅ Generate a Practice Quiz
- ✅ Generate Flashcards

---

## Alternatives if Railway has issues

| Platform | Notes |
|---|---|
| **Render.com** | Very similar to Railway, free tier, `render.yaml` supported |
| **Fly.io** | More control, Docker-native, persistent volumes for ChromaDB |
| **Google Cloud Run** | Scales to zero, pay-per-use, best for production |

---

## Current Local Development

Both servers still work locally without any changes:

```bash
# Backend
cd polymath-ai
.venv\Scripts\python.exe -m uvicorn api.server:app --port 8000

# Frontend
cd polymath-ai/frontend
npm run dev
# → http://localhost:5173
```

The `VITE_API_URL` environment variable is not set locally so it defaults to the relative path `""` which hits `localhost:5173` Vite proxy — exactly as before!
