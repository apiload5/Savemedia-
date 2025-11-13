import os
import io
import uuid
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

# -----------------
# 1. Configuration
# -----------------

# Frontend Domain jise allow karna hai
ALLOWED_ORIGIN = "https://pdf.savemedia.online"

# Temporary files store karne ke liye directory
# Railway par volume storage ya S3 use karna best hai, lekin kam cost ke liye 
# aur chote projects ke liye hum /tmp directory use kar sakte hain.
# Railway /tmp directory mein likhne ki ijazat deta hai.
TEMP_DIR = "/tmp/converted" # Linux/Railway standard temporary directory
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
# Yeh aapke frontend domain ko is backend se baat karne ki ijazat deta hai.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],  # Sirf yeh domain allowed hai
    allow_credentials=True,
    allow_methods=["*"],             # Sabhi methods (POST, GET, etc.) allowed
    allow_headers=["*"],             # Sabhi headers allowed
)

# -----------------
# 3. Health Check
# -----------------

@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"status": "ok", "message": "PDF Converter Service is running"}

# -----------------
# 4. Conversion Endpoint
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
        
        # 3. Conversion Logic
        if image.mode in ('RGBA', 'P'): # Transparency/Palette modes ko RGB mein convert karein
            image = image.convert('RGB')
            
        # Image ko PDF format mein save karein
        image.save(temp_file_path, "PDF", resolution=100.0)

        # 4. File ko FileResponse ke through bhej dein
        # file.filename se extension hatakar .pdf add karein
        output_filename = os.path.splitext(file.filename)[0] + ".pdf"
        
        return FileResponse(
            path=temp_file_path,
            filename=output_filename,
            media_type="application/pdf"
        )
        
    except Exception as e:
        print(f"Conversion Error: {e}")
        # Zyada tar server errors ke liye 500 return karein
        raise HTTPException(status_code=500, detail="Conversion failed due to a server error.")
        
    finally:
        # File transfer hone ke baad temporary file ko delete karne ki koshish karein
        # Railway ke /tmp directory ka size limited hota hai, isliye cleanup zaroori hai.
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as cleanup_e:
                print(f"Error cleaning up file {temp_file_path}: {cleanup_e}")

# Note: Railway par deployment ke baad, aapko logs monitor karne chahiye 
# yeh confirm karne ke liye ki cleanup theek se ho raha hai.
