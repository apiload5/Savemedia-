import os
import io
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask # Cleanup ke liye zaruri
from PIL import Image

# -----------------
# 1. Configuration
# -----------------
ALLOWED_ORIGIN = "https://pdf.savemedia.online"
# Railway par /tmp directory mein likhne ki ijazat hoti hai.
TEMP_DIR = "/tmp/converted" 
os.makedirs(TEMP_DIR, exist_ok=True)

# -----------------
# 2. FastAPI Setup
# -----------------
app = FastAPI(
    title="SaveMedia PDF Converter API",
    description="Lightweight and low-cost image-to-PDF conversion service.",
    version="1.0.0"
)

# CORS Middleware Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------
# 3. Conversion Endpoint
# -----------------

@app.post("/convert/to-pdf", response_class=FileResponse)
async def convert_image_to_pdf(file: UploadFile = File(...)):
    """
    JPG/PNG images ko PDF mein convert karta hai.
    """
    allowed_types = ["image/jpeg", "image/png"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type: {file.content_type}. Only {', '.join(t.split('/')[1] for t in allowed_types)} allowed."
        )

    temp_file_path = None
    try:
        # 1. Image Data ko Memory mein read karein
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        
        # 2. Output PDF file ka path define karein
        unique_id = uuid.uuid4().hex
        temp_file_path = os.path.join(TEMP_DIR, f"{unique_id}.pdf")
        
        # 3. Conversion Logic (using PIL/Pillow)
        if image.mode in ('RGBA', 'P'): 
            image = image.convert('RGB')
            
        image.save(temp_file_path, "PDF", resolution=100.0)

        # 4. FileResponse ke through bhej dein aur background mein delete karein
        output_filename = os.path.splitext(file.filename)[0] + ".pdf"
        
        return FileResponse(
            path=temp_file_path,
            filename=output_filename,
            media_type="application/pdf",
            # File transfer hone ke baad hi file ko delete karne ke liye BackgroundTask use karein
            background=BackgroundTask(os.remove, temp_file_path)
        )
        
    except Exception as e:
        print(f"Conversion Error: {e}")
        # Agar error aaye toh file ko delete karne ki koshish karein
        if temp_file_path and os.path.exists(temp_file_path):
             try: os.remove(temp_file_path)
             except: pass
        raise HTTPException(status_code=500, detail="Conversion failed due to a server error.")
        
# Health Check
@app.get("/")
def read_root():
    return {"status": "ok", "message": "PDF Converter Service is running"}
