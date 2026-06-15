# Medallion Staging API — Deployment Guide

## Files in this project

```
staging-api/
├── main.py           ← FastAPI app (the staging API)
├── generator.py      ← Python data generator script
├── requirements.txt  ← Python dependencies
├── render.yaml       ← Render deployment config
└── README.md         ← This file
```

---

## Step-by-Step: Deploy to Render (Free)

### Step 1 — Push code to GitHub
1. Create a new GitHub repo (e.g. `medallion-staging-api`)
2. Push these files to it:
   ```bash
   git init
   git add .
   git commit -m "initial staging api"
   git remote add origin https://github.com/YOUR_USERNAME/medallion-staging-api.git
   git push -u origin main
   ```

### Step 2 — Create a Render account
- Go to https://render.com and sign up (free, no credit card needed)
- Connect your GitHub account when prompted

### Step 3 — Create a new Web Service on Render
1. Click **"New"** → **"Web Service"**
2. Select your GitHub repo (`medallion-staging-api`)
3. Fill in the settings:
   - **Name:** `medallion-staging-api`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** `Free`

### Step 4 — Set the API Key environment variable
1. In Render dashboard → your service → **"Environment"**
2. Add a new variable:
   - **Key:** `API_KEY`
   - **Value:** `your-strong-secret-key-here` (pick anything, remember it)
3. Click **Save Changes** — Render will redeploy automatically

### Step 5 — Get your public URL
- After deploy, Render gives you a URL like:
  `https://medallion-staging-api.onrender.com`
- Test it: open `https://medallion-staging-api.onrender.com/health` in your browser
- You should see: `{"status":"ok", ...}`

### Step 6 — Update generator.py
Open `generator.py` and replace these two lines:
```python
STAGING_API_URL = "https://YOUR-APP-NAME.onrender.com"   # ← paste your Render URL
API_KEY         = "change-me-in-render-env"               # ← paste your API key
```

### Step 7 — Run the generator
```bash
pip install requests
python generator.py
```
You'll see output like:
```
[Generator] Starting — pushing 100 records every 50 minutes
[2024-01-15T10:00:00] Generating batch...
[Generator] Pushing 100 records to staging API...
[Generator] ✅ Success — batch_id: abc-123 | records: 100 | status: staged
```

---

## API Endpoints

| Method | Endpoint | Who calls it | Description |
|--------|----------|--------------|-------------|
| `POST` | `/batches` | Python generator | Push a new batch every 50 min |
| `GET`  | `/batches` | FDF Web Activity | Pull all un-pulled batches |
| `GET`  | `/batches/{id}` | Debug | Inspect a specific batch |
| `GET`  | `/health` | Render + FDF | Health check |
| `DELETE` | `/batches` | Optional | Clear pulled batches |

All endpoints except `/health` require the header: `x-api-key: YOUR_KEY`

---

## FDF Web Activity Configuration

In Fabric Data Factory, add a **Web Activity** with:
- **URL:** `https://medallion-staging-api.onrender.com/batches`
- **Method:** `GET`
- **Headers:**
  - `x-api-key` → your API key
- The response JSON feeds directly into your Copy Activity to write to OneLake Bronze

---

## Important: Free Tier Spin-Down

Render's free tier spins down after 15 minutes of inactivity.
- Your generator runs every 50 min → the service may be asleep when it calls
- First call after sleep takes ~30 seconds to wake up
- The generator has a 30-second timeout which handles this gracefully
- FDF pipeline runs every 1 hour → same applies, first call may be slow

**To avoid this:** Keep the free tier and just accept the cold start delay — 
it won't cause data loss, just a slightly slower first response.
