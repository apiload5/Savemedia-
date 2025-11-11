from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from fpdf import FPDF
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import io

# -----------------------------------
# Configuration
# -----------------------------------
ALLOWED_ORIGINS = ["https://pdf.savemedia.online"]
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB limit per file

# -----------------------------------
# App Setup
# -----------------------------------
app = FastAPI(
    title="SaveMedia PDF Microservice",
    version="1.0",
    description="Lightweight, cache-free PDF conversion API for SaveMedia.online"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------
# Helper Functions
# -----------------------------------

def read_upload_file(upload: UploadFile) -> io.BytesIO:
    """Safely read uploaded file into memory (with size limit)."""
    data = io.BytesIO()
    total = 0
    for chunk in upload.file:
        total += len(chunk)
        if total > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large (max 25 MB)")
        data.write(chunk)
    data.seek(0)
    return data


def image_to_pdf_bytes(img_bytes: io.BytesIO) -> io.BytesIO:
    """Convert image bytes to single-page PDF (in memory)."""
    img_bytes.seek(0)
    img = Image.open(img_bytes).convert("RGB")
    w, h = img.size
    pdf = FPDF(unit="pt", format=(w, h))
    pdf.add_page()
    temp = io.BytesIO()
    img.save(temp, format="JPEG")
    temp.seek(0)
    pdf.image(temp, x=0, y=0, w=w, h=h)
    out = io.BytesIO()
    pdf.output(out)
    out.seek(0)
    return out


def text_to_pdf_bytes(text: str) -> io.BytesIO:
    """Convert text string to a simple PDF."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in text.splitlines():
        pdf.multi_cell(0, 10, line)
    out = io.BytesIO()
    pdf.output(out)
    out.seek(0)
    return out


def merge_pdfs(list_of_pdfs: List[io.BytesIO]) -> io.BytesIO:
    """Merge multiple PDF byte streams into one PDF."""
    writer = PdfWriter()
    for pdf_io in list_of_pdfs:
        pdf_io.seek(0)
        reader = PdfReader(pdf_io)
        for page in reader.pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out


def extract_text_from_pdf(pdf_io: io.BytesIO) -> str:
    """Extract readable text from PDF."""
    pdf_io.seek(0)
    reader = PdfReader(pdf_io)
    text = []
    for page in reader.pages:
        try:
            text.append(page.extract_text() or "")
        except Exception:
            text.append("")
    return "\n\n".join(text)

# -----------------------------------
# Routes
# -----------------------------------

@app.get("/health")
async def health():
    """Simple health check endpoint."""
    return JSONResponse({"status": "ok"})


@app.post("/convert/to-pdf")
async def convert_to_pdf(files: List[UploadFile] = File(...)):
    """
    Convert uploaded files to a single merged PDF.
    Supports: Images (.png, .jpg, .jpeg, .webp, .bmp, .tiff),
              Text (.txt),
              Existing PDF (merged directly)
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    pdf_parts = []

    for file in files:
        filename = file.filename or "file"
        ext = filename.lower().split(".")[-1]
        data_io = read_upload_file(file)

        if ext in ["png", "jpg", "jpeg", "webp", "bmp", "tiff"]:
            pdf_parts.append(image_to_pdf_bytes(data_io))
        elif ext == "txt":
            text = data_io.read().decode(errors="ignore")
            pdf_parts.append(text_to_pdf_bytes(text))
        elif ext == "pdf":
            pdf_parts.append(data_io)
        else:
            raise HTTPException(status_code=415, detail=f"Unsupported file type: {filename}")

    merged_pdf = merge_pdfs(pdf_parts)
    headers = {"Content-Disposition": 'attachment; filename="converted.pdf"'}
    return StreamingResponse(merged_pdf, media_type="application/pdf", headers=headers)


@app.post("/convert/from-pdf")
async def convert_from_pdf(file: UploadFile = File(...), format_type: str = Form("text")):
    """
    Extract text from PDF or return same file.
    - format_type=text → returns .txt
    - format_type=pdf → returns same PDF file
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF files allowed")

    data_io = read_upload_file(file)

    if format_type == "pdf":
        headers = {"Content-Disposition": f'attachment; filename="{file.filename}"'}
        data_io.seek(0)
        return StreamingResponse(data_io, media_type="application/pdf", headers=headers)

    elif format_type == "text":
        text = extract_text_from_pdf(data_io)
        output = io.BytesIO(text.encode("utf-8"))
        headers = {"Content-Disposition": 'attachment; filename="extracted.txt"'}
        return StreamingResponse(output, media_type="text/plain", headers=headers)

    else:
        raise HTTPException(status_code=400, detail="Invalid format_type")
