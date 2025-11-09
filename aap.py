
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import shutil, tempfile, os, subprocess, io, zipfile
from pathlib import Path
from PIL import Image
import img2pdf
import fitz  # PyMuPDF

# --------------------
# Configuration
# --------------------
ALLOWED_ORIGINS = [
    "https://pdf-savemedia.blogspot.com",
    "https://www.pdf.savemedia.online",
    "https://pdf.savemedia.online",
]
MAX_UPLOAD_SIZE = 200 * 1024 * 1024  # 200 MB max (adjust as needed)

# --------------------
# FastAPI app
# --------------------
app = FastAPI(title="app", version="1.0")

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
        if p and p.exists():
            p.unlink()
    except Exception:
        pass

# --------------------
# Endpoints
# --------------------

@app.post("/convert/to-pdf")
async def convert_to_pdf(
    file: UploadFile = File(...),
    as_single_pdf: Optional[bool] = Form(True)
):
    """Convert uploaded file (image, text, docx/odt, pdf) to PDF and stream back.
    Single request per operation; temporary files are deleted immediately after streaming.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    tmp_in = save_upload_tmp(file)

    try:
        ext = tmp_in.suffix.lower()

        # Image -> PDF
        if ext in [".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp"]:
            pil = Image.open(tmp_in)
            pil_rgb = pil.convert("RGB")
            buf = io.BytesIO()
            pil_rgb.save(buf, format="PDF")
            buf.seek(0)
            return StreamingResponse(buf, media_type="application/pdf",
                                     headers={"Content-Disposition": f"attachment; filename=\"{Path(file.filename).stem}.pdf\""})

        # Plain text -> PDF via reportlab
        elif ext in [".txt"]:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            buf = io.BytesIO()
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
            buf.seek(0)
            return StreamingResponse(buf, media_type="application/pdf",
                                     headers={"Content-Disposition": f"attachment; filename=\"{Path(file.filename).stem}.pdf\""})

        # Office docs -> PDF using LibreOffice (system binary required)
        elif ext in [".doc", ".docx", ".odt", ".ppt", ".pptx", ".xls", ".xlsx"]:
            soffice = shutil.which("soffice") or shutil.which("libreoffice")
            if not soffice:
                raise HTTPException(status_code=500, detail="LibreOffice (soffice) not found on server; cannot convert office docs to PDF")
            # LibreOffice will create converted file next to tmp_in
            cmd = [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(tmp_in.parent), str(tmp_in)]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
            converted = tmp_in.with_suffix('.pdf')
            if not converted.exists():
                raise HTTPException(status_code=500, detail=f"Conversion failed: {proc.stderr.decode(errors='ignore')}")
            def iter_file(path: Path):
                with path.open('rb') as f:
                    for chunk in iter(lambda: f.read(1024*1024), b""):
                        yield chunk
            headers = {"Content-Disposition": f"attachment; filename=\"{converted.name}\""}
            return StreamingResponse(iter_file(converted), media_type="application/pdf", headers=headers)

        # If already PDF, stream back
        elif ext == ".pdf":
            return StreamingResponse(tmp_in.open('rb'), media_type="application/pdf",
                                     headers={"Content-Disposition": f"attachment; filename=\"{Path(file.filename).name}\""})

        else:
            raise HTTPException(status_code=400, detail="Unsupported input format for to-pdf conversion")

    finally:
        # Cleanup temporary files and any LibreOffice outputs
        try:
            cleanup_path(tmp_in)
            cleanup_path(tmp_in.with_suffix('.pdf'))
        except Exception:
            pass


@app.post("/convert/from-pdf")
async def convert_from_pdf(
    file: UploadFile = File(...),
    format: str = Form("image")  # 'image' | 'docx' | 'text'
):
    if format not in ("image", "docx", "text"):
        raise HTTPException(status_code=400, detail="format must be one of: image, docx, text")

    tmp_in = save_upload_tmp(file)
    try:
        if tmp_in.suffix.lower() != ".pdf":
            raise HTTPException(status_code=400, detail="Uploaded file is not a PDF")

        if format == "text":
            doc = fitz.open(str(tmp_in))
            text_pages = []
            for page in doc:
                text_pages.append(page.get_text())
            doc.close()
            joined = "\n\n----- PAGE BREAK -----\n\n".join(text_pages)
            return StreamingResponse(io.BytesIO(joined.encode('utf-8')), media_type="text/plain",
                                     headers={"Content-Disposition": f"attachment; filename=\"{Path(file.filename).stem}.txt\""})

        elif format == "image":
            doc = fitz.open(str(tmp_in))
            mem_zip = io.BytesIO()
            with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                for i, page in enumerate(doc, start=1):
                    pix = page.get_pixmap(dpi=200)
                    img_bytes = pix.tobytes("png")
                    zf.writestr(f"page_{i:03d}.png", img_bytes)
            doc.close()
            mem_zip.seek(0)
            return StreamingResponse(mem_zip, media_type="application/zip",
                                     headers={"Content-Disposition": f"attachment; filename=\"{Path(file.filename).stem}_pages.zip\""})

        elif format == "docx":
            soffice = shutil.which("soffice") or shutil.which("libreoffice")
            if not soffice:
                raise HTTPException(status_code=500, detail="LibreOffice not found; cannot convert PDF -> DOCX on this server")
            cmd = [soffice, "--headless", "--convert-to", "docx", "--outdir", str(tmp_in.parent), str(tmp_in)]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
            converted = tmp_in.with_suffix('.docx')
            if not converted.exists():
                raise HTTPException(status_code=500, detail=f"Conversion failed: {proc.stderr.decode(errors='ignore')}")
            def iter_file(path: Path):
                with path.open('rb') as f:
                    for chunk in iter(lambda: f.read(1024*1024), b""):
                        yield chunk
            headers = {"Content-Disposition": f"attachment; filename=\"{converted.name}\""}
            return StreamingResponse(iter_file(converted), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers=headers)

    finally:
        try:
            cleanup_path(tmp_in)
            cleanup_path(tmp_in.with_suffix('.docx'))
            cleanup_path(tmp_in.with_suffix('.pdf'))
        except Exception:
            pass


@app.get('/health')
def health():
    return {"status": "ok"}
