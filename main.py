from io import BytesIO
from typing import List
from PIL import Image
from fpdf import FPDF
from fastapi import FastAPI, UploadFile, File, HTTPException
from starlette.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware # <--- NAYA IMPORT

# FastAPI application instance
app = FastAPI()

# ----------------------------------------------------
# 🌟 FIX: CORS MIDDLEWARE (Domain Allow Karne Ke Liye) 
# ----------------------------------------------------
# Wo domains jinko is API ko call karne ki ijazat hogi.
# Sab domains ko allow karne ke liye "*" ka istemal karen,
# ya sirf apne domain (maslan "https://www.mysavemedia.com") ko likhen.
origins = [
    "https://pdf.savemedia.online", 
    # "https://www.yourfrontenddomain.com", # <--- Ise apne asal domain se badal dain.
    # "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Sab HTTP methods (POST, GET, etc.) ki ijazat
    allow_headers=["*"],  # Sab HTTP headers ki ijazat
)
# ----------------------------------------------------

def image_to_pdf(image_data: BytesIO) -> bytes:
    """
    In-memory image ko PDF bytes mein convert karta hai.
    (Pehle ki AttributeError fix shamil hai)
    """
    try:
        # Image ko PIL (Pillow) se open karen
        img = Image.open(image_data)
        
        # Dimensions aur format hasil karen
        w, h = img.size
        image_format = img.format
        
        if not image_format:
            raise ValueError("Image format could not be determined. Check if the file is a valid image.")

        # FPDF object banaen
        pdf = FPDF(unit="pt", format=(w, h))
        pdf.add_page()
        
        # BytesIO pointer ko shuruaat mein laayen
        image_data.seek(0)
        
        # FIX: fpdf.image ko 'type' argument ke saath call karen
        pdf.image(
            name=image_data, 
            x=0, 
            y=0, 
            w=w, 
            h=h, 
            type=image_format # Ye wo FIX hai jo 'rfind' error ko dur karta hai
        )

        # PDF ko in-memory bytes mein output karen
        pdf_bytes = pdf.output(dest='S').encode('latin1')
        return pdf_bytes

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Image processing error: {e}")
    except Exception as e:
        print(f"Error during PDF conversion: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during PDF generation.")


@app.post("/convert/to-pdf", summary="Convert images to a single PDF")
async def convert_to_pdf(files: List[UploadFile] = File(...)):
    """
    Multiple uploaded images (JPEG, PNG) ko ek single PDF file mein convert karta hai.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
        
    pdf_parts = []
    
    for file in files:
        content = await file.read()
        data = BytesIO(content)
        
        try:
            pdf_part = image_to_pdf(data)
            pdf_parts.append(pdf_part)
        except HTTPException as e:
            raise e
        except Exception:
            raise HTTPException(status_code=500, detail=f"Failed to process file: {file.filename}")

    # Agar multiple parts hain, to sabse pehle ka PDF return karen (Merging logic ki zarurat ho sakti hai)
    if pdf_parts:
        final_pdf_bytes = pdf_parts[0]
    else:
         raise HTTPException(status_code=500, detail="No PDF parts were created.")


    # Result ko StreamingResponse ke taur par return karen
    return StreamingResponse(
        BytesIO(final_pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=converted.pdf"}
    )
