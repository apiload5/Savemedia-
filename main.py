from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from fpdf import FPDF
from PIL import Image
import fitz  # PyMuPDF (for PDF to image)
import io, os, tempfile

# -------------------------------
# ✅ Config
# -------------------------------
ALLOWED_ORIGINS = [
    "https://pdf.savemedia.online",
    "https://www.pdf.savemedia.online",
    "http://localhost:3000"
]

app = FastAPI(
    title="SaveMedia PDF API (Lite)",
    version="2.0",
    description="🚀 Railway-ready Lite API for SaveMedia PDF Converter"
)

# ✅ CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Helper Functions
# -------------------------------
def image_to_pdf(img_bytes: bytes) -> io.BytesIO:
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = img.size
    pdf = FPDF(unit="pt", format=(w, h))
    pdf.add_page()
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img.save(tmp, "JPEG")
        tmp_path = tmp.name
    pdf.image(tmp_path, 0, 0, w, h)
    os.remove(tmp_path)

    out = io.BytesIO()
    pdf_bytes = pdf.output(dest="S").encode("latin1")
    out.write(pdf_bytes)
    out.seek(0)
    return out


def text_to_pdf(text: str) -> io.BytesIO:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in text.splitlines():
        pdf.multi_cell(0, 10, line)
    out = io.BytesIO()
    pdf_bytes = pdf.output(dest="S").encode("latin1")
    out.write(pdf_bytes)
    out.seek(0)
    return out


def pdf_to_image(pdf_data: bytes) -> io.BytesIO:
    """Convert first PDF page to PNG image"""
    pdf = fitz.open(stream=pdf_data, filetype="pdf")
    if len(pdf) == 0:
        raise HTTPException(status_code=400, detail="Empty PDF")
    pix = pdf[0].get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")
    out = io.BytesIO(img_bytes)
    out.seek(0)
    return out

# -------------------------------
# Routes
# -------------------------------
@app.get("/")
def home():
    return {"message": "🚀 SaveMedia PDF Lite API Running", "frontend": "https://pdf.savemedia.online"}

@app.post("/convert/to-pdf")
async def convert_to_pdf(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No file uploaded")

    merged_pdfs = []
    for f in files:
        data = await f.read()
        ext = f.filename.lower().split(".")[-1]

        if ext in ["png", "jpg", "jpeg", "bmp", "webp"]:
            merged_pdfs.append(image_to_pdf(data))
        elif ext == "txt":
            merged_pdfs.append(text_to_pdf(data.decode(errors="ignore")))
        elif ext == "pdf":
            merged_pdfs.append(io.BytesIO(data))
        else:
            raise HTTPException(status_code=415, detail=f"Unsupported file type: {f.filename}")

    # Combine PDFs (if multiple)
    if len(merged_pdfs) == 1:
        final_pdf = merged_pdfs[0]
    else:
        import PyPDF2
        writer = PyPDF2.PdfWriter()
        for p in merged_pdfs:
            p.seek(0)
            reader = PyPDF2.PdfReader(p)
            for page in reader.pages:
                writer.add_page(page)
        final_pdf = io.BytesIO()
        writer.write(final_pdf)
        final_pdf.seek(0)

    headers = {"Content-Disposition": 'attachment; filename="converted.pdf"'}
    return StreamingResponse(final_pdf, media_type="application/pdf", headers=headers)


@app.post("/convert/from-pdf")
async def convert_from_pdf(file: UploadFile = File(...), format_type: str = Form("text")):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Upload must be a PDF file")

    data = await file.read()

    if format_type == "image":
        image_bytes = pdf_to_image(data)
        headers = {"Content-Disposition": 'attachment; filename="page_1.png"'}
        return StreamingResponse(image_bytes, media_type="image/png", headers=headers)
    elif format_type == "text":
        pdf = fitz.open(stream=data, filetype="pdf")
        text = "\n".join(page.get_text() for page in pdf)
        out = io.BytesIO(text.encode("utf-8"))
        headers = {"Content-Disposition": 'attachment; filename="extracted.txt"'}
        return StreamingResponse(out, media_type="text/plain", headers=headers)
    else:
        headers = {"Content-Disposition": f'attachment; filename="{file.filename}"'}
        return StreamingResponse(io.BytesIO(data), media_type="application/pdf", headers=headers)

# -------------------------------
# Run
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
