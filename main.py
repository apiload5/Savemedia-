from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from fpdf import FPDF
from PIL import Image
import fitz  # PyMuPDF
import io, os, tempfile
from PyPDF2 import PdfReader, PdfWriter

# -------------------------------
# ✅ Config
# -------------------------------
ALLOWED_ORIGINS = [
    "https://pdf.savemedia.online",
    "https://www.pdf.savemedia.online",
    "http://localhost:3000",
]

app = FastAPI(
    title="SaveMedia PDF API (Lite)",
    version="2.1",
    description="🚀 Railway-ready Lite API for SaveMedia PDF Converter"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# ✅ Helper Functions
# -------------------------------
def image_to_pdf(img_bytes: bytes) -> io.BytesIO:
    """Convert image (bytes) to PDF (BytesIO)"""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = img.size
    pdf = FPDF(unit="pt", format=(w, h))
    pdf.add_page()

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img.save(tmp, "JPEG")
        tmp_path = tmp.name

    pdf.image(tmp_path, 0, 0, w, h)
    os.remove(tmp_path)

    # ✅ Fixed output (no rfind error)
    pdf_data = pdf.output(dest="S").encode("latin1")
    return io.BytesIO(pdf_data)


def text_to_pdf(text: str) -> io.BytesIO:
    """Convert plain text to PDF"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in text.splitlines():
        pdf.multi_cell(0, 10, line)

    # ✅ Fixed output
    pdf_data = pdf.output(dest="S").encode("latin1")
    return io.BytesIO(pdf_data)


def merge_pdfs(pdfs: List[io.BytesIO]) -> io.BytesIO:
    """Merge multiple PDFs into one"""
    writer = PdfWriter()
    for p in pdfs:
        p.seek(0)
        reader = PdfReader(p)
        for page in reader.pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out


def pdf_to_image(pdf_bytes: bytes) -> io.BytesIO:
    """Convert first page of PDF to PNG"""
    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    if len(pdf) == 0:
        raise HTTPException(status_code=400, detail="Empty PDF")
    pix = pdf[0].get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")
    return io.BytesIO(img_bytes)


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF"""
    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    return "\n".join(page.get_text() for page in pdf)


# -------------------------------
# ✅ Routes
# -------------------------------
@app.get("/")
def home():
    return {
        "message": "🚀 SaveMedia PDF Lite API running successfully!",
        "frontend": "https://pdf.savemedia.online",
        "docs": "/docs"
    }


@app.post("/convert/to-pdf")
async def convert_to_pdf(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    pdf_parts = []
    for f in files:
        content = await f.read()
        ext = f.filename.lower().split(".")[-1]
        if ext in ["png", "jpg", "jpeg", "bmp", "webp", "tiff"]:
            pdf_parts.append(image_to_pdf(content))
        elif ext == "txt":
            pdf_parts.append(text_to_pdf(content.decode(errors="ignore")))
        elif ext == "pdf":
            pdf_parts.append(io.BytesIO(content))
        else:
            raise HTTPException(status_code=415, detail=f"Unsupported file: {f.filename}")

    merged = merge_pdfs(pdf_parts)
    headers = {"Content-Disposition": 'attachment; filename="converted.pdf"'}
    return StreamingResponse(merged, media_type="application/pdf", headers=headers)


@app.post("/convert/from-pdf")
async def convert_from_pdf(file: UploadFile = File(...), format_type: str = Form("text")):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Upload must be a PDF file")

    pdf_data = await file.read()

    if format_type == "image":
        img = pdf_to_image(pdf_data)
        headers = {"Content-Disposition": 'attachment; filename="page_1.png"'}
        return StreamingResponse(img, media_type="image/png", headers=headers)

    elif format_type == "text":
        extracted_text = extract_text_from_pdf(pdf_data)
        out = io.BytesIO(extracted_text.encode("utf-8"))
        headers = {"Content-Disposition": 'attachment; filename="extracted.txt"'}
        return StreamingResponse(out, media_type="text/plain", headers=headers)

    else:  # Return original PDF
        headers = {"Content-Disposition": f'attachment; filename="{file.filename}"'}
        return StreamingResponse(io.BytesIO(pdf_data), media_type="application/pdf", headers=headers)


# -------------------------------
# ✅ Run (for local testing)
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Running SaveMedia PDF API on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
