from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
import yt_dlp
import os

API_KEY = os.getenv("API_KEY")
ALLOWED_DOMAIN = os.getenv("ALLOWED_DOMAIN", "savemedia.online")

app = FastAPI(title="SaveMedia Backend", version="1.3")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# ✅ Temporarily allow all origins (for Blogger testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🏠 Root check route
@app.get("/")
def home():
    return {"status": "ok", "message": "SaveMedia Zero-Load Backend running fine"}

# 🧩 Extract endpoint
@app.post("/api/extract")
@limiter.limit("2/minute")
async def extract_video(request: Request):
    data = await request.json()
    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    print("Request received from:", request.headers.get("origin"))

    try:
        ydl_opts = {"skip_download": True, "quiet": True, "nocheckcertificate": True, "ignoreerrors": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise HTTPException(status_code=400, detail="Unable to extract info")

        if "entries" in info:
            info = info["entries"][0]

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
