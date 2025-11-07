# main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
import yt_dlp
import os

# -----------------------
# Configuration
# -----------------------
API_KEY = os.getenv("API_KEY")
ALLOWED_DOMAIN = os.getenv("ALLOWED_DOMAIN", "savemedia.online")

# -----------------------
# FastAPI setup
# -----------------------
app = FastAPI(
    title="SaveMedia Backend",
    version="1.2",
    description="Secure and ultra-lightweight FastAPI backend for savemedia.online — powered by yt_dlp."
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"https://{ALLOWED_DOMAIN}", f"http://{ALLOWED_DOMAIN}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------
# API Endpoint
# -----------------------
@app.post("/api/extract")
@limiter.limit("2/minute")  # ⏳ Limit per IP: 2 requests per minute
async def extract_video(request: Request):
    data = await request.json()
    url = data.get("url")

    # 🧩 1. URL validation
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    # 🔐 2. Origin protection
    origin = request.headers.get("origin")
    if origin not in [f"https://{ALLOWED_DOMAIN}", f"http://{ALLOWED_DOMAIN}"]:
        raise HTTPException(status_code=403, detail="Unauthorized origin")

    # 🔑 3. Optional API key check
    key = request.headers.get("x-api-key")
    if key and key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # ⚙️ 4. Extract video info using yt_dlp (without downloading)
    try:
        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "nocheckcertificate": True,
            "ignoreerrors": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise HTTPException(status_code=400, detail="Unable to extract info")

        # 🧠 If playlist, get first entry
        if "entries" in info:
            info = info["entries"][0]

        # 🎬 Build response
        formats = []
        for f in info.get("formats", []):
            if f.get("url") and f.get("ext"):
                formats.append({
                    "ext": f.get("ext"),
                    "quality": f.get("format_note"),
                    "filesize": f.get("filesize"),
                    "url": f.get("url"),
                })

        return {
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "formats": formats
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
