from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
import shutil, tempfile, io, subprocess, zipfile
from pathlib import Path
from PIL import Image
import fitz  # PyMuPDF
from PyPDF2 import PdfMerger

# --------------------
# Configuration
# --------------------
ALLOWED_ORIGINS = [
    "https://pdf-savemedia.blogspot.com",
    "https://savemedia-pdf.blogspot.com",
    "https://pdf.savemedia.online",
    "https://www.pdf.savemedia.online",
]

# --------------------
# FastAPI app
# --------------------
app = FastAPI(title="SaveMedia PDF Tools", version="1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------
# Helpers
# --------------------
def save_upload_tmp(upload: UploadFile) -> Path:
    suffix = Path(upload.filename).suffix or ""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        with tmp as f:
            shutil.copyfileobj(upload.file, f)
        return Path(tmp.name)
    finally:
        upload.file.close()

def cleanup_path(p: Path):
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass

# --------------------
# Convert to PDF (multi-file supported)
# --------------------
@app.post("/convert/to-pdf")
async def convert_to_pdf(
    files: List[UploadFile] = File(...),
    as_single_pdf: Optional[bool] = Form(True)
):
    if not files:
        raise HTTPException(status_code=400, detail="No file uploaded")

    pdf_buffers = []

    for upload in files:
        tmp_in = save_upload_tmp(upload)
        ext = tmp_in.suffix.lower()
        buf = io.BytesIO()

        try:
            # Image → PDF
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp"]:
                img = Image.open(tmp_in).convert("RGB")
                img.save(buf, format="PDF")

            # Text → PDF
            elif ext == ".txt":
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import A4
                c = canvas.Canvas(buf, pagesize=A4)
                y = 820
                text = tmp_in.read_text(encoding="utf-8", errors="ignore")
                for line in text.splitlines():
                    c.drawString(40, y, line[:1000])
                    y -= 12
                    if y < 40:
                        c.showPage()
                        y = 820
                c.save()

            # Office → PDF (LibreOffice)
            elif ext in [".doc", ".docx", ".odt", ".ppt", ".pptx", ".xls", ".xlsx"]:
                soffice = shutil.which("soffice") or shutil.which("libreoffice")
                if not soffice:
                    raise HTTPException(status_code=500, detail="LibreOffice not found on server")
                cmd = [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(tmp_in.parent), str(tmp_in)]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
                converted = tmp_in.with_suffix('.pdf')
                if not converted.exists():
                    raise HTTPException(status_code=500, detail="Conversion failed")
                with converted.open("rb") as f:
                    buf.write(f.read())

            # Already PDF → Keep
            elif ext == ".pdf":
                with tmp_in.open("rb") as f:
                    buf.write(f.read())

            else:
                raise HTTPException(status_code=400, detail=f"Unsupported format: {ext}")

            buf.seek(0)
            pdf_buffers.append(buf)

        finally:
            cleanup_path(tmp_in)
            cleanup_path(tmp_in.with_suffix('.pdf'))

    # Combine all PDFs (if requested)
    if as_single_pdf and len(pdf_buffers) > 1:
        merger = PdfMerger()
        for pdf in pdf_buffers:
            merger.append(io.BytesIO(pdf.getvalue()))
        combined = io.BytesIO()
        merger.write(combined)
        merger.close()
        combined.seek(0)
        return StreamingResponse(
            combined,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=merged.pdf"}
        )
    else:
        pdf = pdf_buffers[0]
        return StreamingResponse(
            pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=converted.pdf"}
        )

# --------------------
# Convert from PDF
# --------------------
@app.post("/convert/from-pdf")
async def convert_from_pdf(
    file: UploadFile = File(...),
    format: str = Form("image")  # 'image' | 'docx' | 'text'
):
    tmp_in = save_upload_tmp(file)
    try:
        if tmp_in.suffix.lower() != ".pdf":
            raise HTTPException(status_code=400, detail="Uploaded file is not a PDF")

        if format == "text":
            doc = fitz.open(str(tmp_in))
            text = "\n\n----- PAGE BREAK -----\n\n".join([p.get_text() for p in doc])
            doc.close()
            return StreamingResponse(io.BytesIO(text.encode("utf-8")), media_type="text/plain",
                                     headers={"Content-Disposition": f"attachment; filename={Path(file.filename).stem}.txt"})

        elif format == "image":
            doc = fitz.open(str(tmp_in))
            mem_zip = io.BytesIO()
            with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, page in enumerate(doc, start=1):
                    pix = page.get_pixmap(dpi=200)
                    zf.writestr(f"page_{i:03d}.png", pix.tobytes("png"))
            doc.close()
            mem_zip.seek(0)
            return StreamingResponse(mem_zip, media_type="application/zip",
                                     headers={"Content-Disposition": f"attachment; filename={Path(file.filename).stem}_pages.zip"})

        elif format == "docx":
            soffice = shutil.which("soffice") or shutil.which("libreoffice")
            if not soffice:
                raise HTTPException(status_code=500, detail="LibreOffice not found on server")
            cmd = [soffice, "--headless", "--convert-to", "docx", "--outdir", str(tmp_in.parent), str(tmp_in)]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
            converted = tmp_in.with_suffix(".docx")
            if not converted.exists():
                raise HTTPException(status_code=500, detail="Conversion failed")
            return StreamingResponse(converted.open("rb"),
                                     media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                     headers={"Content-Disposition": f"attachment; filename={converted.name}"})
    finally:
        cleanup_path(tmp_in)
        cleanup_path(tmp_in.with_suffix(".docx"))
        cleanup_path(tmp_in.with_suffix(".pdf"))

# --------------------
# Health check
# --------------------
@app.get("/health")
def health():
    return {"status": "ok"}
