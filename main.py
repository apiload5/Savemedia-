from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from fpdf import FPDF
from pypdf import PdfReader, PdfWriter
from PIL import Image
import io, os

# -----------------------------------
# CONFIGURATION
# -----------------------------------
ALLOWED_ORIGINS = ["https://pdf.savemedia.online"]  # ✅ Your domain
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

app = FastAPI(
    title="SaveMedia PDF Lite API",
    version="1.0",
    description="Lightweight FastAPI PDF converter for SaveMedia.online"
)

# ✅ Enable CORS for your domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------
# HELPER FUNCTIONS
# -----------------------------------
def read_file(upload: UploadFile) -> io.BytesIO:
    """Read uploaded file safely into memory with size limit."""
    data = io.BytesIO()
    total = 0
    while True:
        chunk = upload.file.read(8192)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large (max 25MB)")
        data.write(chunk)
    data.seek(0)
    return data


def image_to_pdf(img_bytes: io.BytesIO) -> io.BytesIO:
    """Convert an image to a single-page PDF."""
    img = Image.open(img_bytes).convert("RGB")
    w, h = img.size
    pdf = FPDF(unit="pt", format=(w, h))
    pdf.add_page()
    temp = io.BytesIO()
    img.save(temp, format="JPEG")
    temp.seek(0)
    pdf.image(temp, 0, 0, w, h)

    out = io.BytesIO()
    out.write(pdf.output(dest="S").encode("latin1"))  # ✅ FIXED
    out.seek(0)
    return out


def text_to_pdf(text: str) -> io.BytesIO:
    """Convert plain text to PDF."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in text.splitlines():
        pdf.multi_cell(0, 10, line)

    out = io.BytesIO()
    out.write(pdf.output(dest="S").encode("latin1"))  # ✅ FIXED
    out.seek(0)
    return out


def merge_pdfs(pdfs: List[io.BytesIO]) -> io.BytesIO:
    """Merge multiple PDF files into one."""
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


def extract_text(pdf_io: io.BytesIO) -> str:
    """Extract text from a PDF file."""
    pdf_io.seek(0)
    reader = PdfReader(pdf_io)
    text = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text.append(page_text)
    return "\n".join(text)


# -----------------------------------
# ROUTES
# -----------------------------------
@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/convert/to-pdf")
async def convert_to_pdf(files: List[UploadFile] = File(...)):
    """Convert uploaded files (image/text/pdf) into a single merged PDF."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    pdf_parts = []
    for file in files:
        name = file.filename.lower()
        ext = name.split(".")[-1]
        data = read_file(file)

        if ext in ["png", "jpg", "jpeg", "bmp", "webp"]:
            pdf_parts.append(image_to_pdf(data))
        elif ext == "txt":
            text = data.read().decode(errors="ignore")
            pdf_parts.append(text_to_pdf(text))
        elif ext == "pdf":
            pdf_parts.append(data)
        else:
            raise HTTPException(status_code=415, detail=f"Unsupported file type: {ext}")

    merged = merge_pdfs(pdf_parts)
    headers = {"Content-Disposition": 'attachment; filename="converted.pdf"'}
    return StreamingResponse(merged, media_type="application/pdf", headers=headers)


@app.post("/convert/from-pdf")
async def convert_from_pdf(file: UploadFile = File(...), format_type: str = Form("text")):
    """Extract text or return the same PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="File must be a PDF")

    data = read_file(file)
    if format_type == "pdf":
        headers = {"Content-Disposition": f'attachment; filename="{file.filename}"'}
        return StreamingResponse(data, media_type="application/pdf", headers=headers)

    text = extract_text(data)
    out = io.BytesIO(text.encode("utf-8"))
    headers = {"Content-Disposition": 'attachment; filename="extracted.txt"'}
    return StreamingResponse(out, media_type="text/plain", headers=headers)


# -----------------------------------
# RUN SERVER
# -----------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Running SaveMedia Lite API on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
