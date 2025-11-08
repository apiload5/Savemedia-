from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
import yt_dlp
import os

# -----------------------
# Config
# -----------------------
API_KEY = os.getenv("API_KEY", "2580421-amir-karachi")
ALLOWED_DOMAIN = os.getenv("ALLOWED_DOMAIN", "savemedia.online")

# -----------------------
# App setup
# -----------------------
app = FastAPI(
    title="SaveMedia Backend",
    version="1.3",
    description="Fast, lightweight backend using yt_dlp for SaveMedia.online",
)

# Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# ✅ Allow CORS for all during testing (Blogger compatible)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later restrict to ["https://savemedia.online"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------
# Root check route
# -----------------------
@app.get("/")
def home():
    return {"status": "ok", "message": "SaveMedia Zero-Load Backend running fine"}

# -----------------------
# Extract route
# -----------------------
@app.post("/api/extract")
@limiter.limit("2/minute")  # ⏳ limit: 2 requests per minute per IP
async def extract_video(request: Request):
    data = await request.json()
    url = data.get("url")

    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    print("Request received from:", request.headers.get("origin"))

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


# ✅ Make sure this is NOT indented — must be at the very left
if __name__ == "__main__":
    import uvicorn
    print("✅ Routes loaded:", [r.path for r in app.router.routes])
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
