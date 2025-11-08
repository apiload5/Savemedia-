from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_forwarded_ip 
import yt_dlp
import os

# API_KEY ab istemaal nahi hoga
# API_KEY = os.getenv("API_KEY") 

ALLOWED_DOMAIN = os.getenv("ALLOWED_DOMAIN", "savemedia.online")

app = FastAPI(
    title="SaveMedia Backend",
    version="1.3",
    description="Fast, lightweight backend using yt_dlp for SaveMedia.online",
)

limiter = Limiter(key_func=get_forwarded_ip) 
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    # FIX: Sirf ALLOWED_DOMAIN ko allow kiya gaya
    allow_origins=[f"https://{ALLOWED_DOMAIN}", f"http://{ALLOWED_DOMAIN}"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "ok", "message": "SaveMedia Zero-Load Backend running fine"}

@app.post("/api/extract")
@limiter.limit("2/minute")
async def extract_video(request: Request):
    
    # API Key check hata diya gaya hai

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
                    "format_id": f.get("format_id"), 
                })

        return {
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "formats": formats
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    print("✅ Routes loaded:", [r.path for r in app.router.routes]) 
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
