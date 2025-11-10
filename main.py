import os
import uuid
import asyncio
import aiofiles
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import magic
from converters.pdf_generator import PDFGenerator
from converters.pdf_extractor import PDFExtractor

app = FastAPI(
    title="SaveMedia PDF Converter API",
    description="Fast and lightweight PDF conversion service",
    version="2.0.0"
)

# CORS configuration - ONLY YOUR DOMAIN
ALLOWED_ORIGINS = [
    "https://pdf.savemedia.online",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Configuration
UPLOAD_DIR = "temp/uploads"
OUTPUT_DIR = "temp/output"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Create directories
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Allowed file types
ALLOWED_TO_PDF = {
    'image/jpeg', 'image/jpg', 'image/png', 'image/webp', 
    'image/tiff', 'image/bmp', 'text/plain',
    'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.oasis.opendocument.text',
    'application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/pdf'
}

ALLOWED_FROM_PDF = {'application/pdf'}

@app.get("/")
async def root():
    return {
        "message": "SaveMedia PDF Converter API",
        "status": "active",
        "version": "2.0.0",
        "endpoints": {
            "convert_to_pdf": "/convert/to-pdf",
            "convert_from_pdf": "/convert/from-pdf"
        }
    }

@app.post("/convert/to-pdf")
async def convert_to_pdf(
    files: list[UploadFile] = File(...),
    conversion_type: str = Form("single")
):
    """
    Convert files to PDF format
    - Single file: Convert one file to PDF
    - Multiple files: Combine multiple files into one PDF
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        # Validate file size and type
        for file in files:
            await validate_file(file, ALLOWED_TO_PDF)

        session_id = str(uuid.uuid4())
        pdf_generator = PDFGenerator()

        if conversion_type == "single" and len(files) == 1:
            # Single file conversion
            file = files[0]
            input_path = await save_uploaded_file(file, session_id)
            
            try:
                output_path = await asyncio.get_event_loop().run_in_executor(
                    None, pdf_generator.convert_single, input_path, session_id
                )
                
                return FileResponse(
                    output_path,
                    media_type='application/pdf',
                    filename=f"{os.path.splitext(file.filename)[0]}.pdf"
                )
                
            finally:
                await cleanup_file(input_path)
                if 'output_path' in locals():
                    await cleanup_file(output_path)
                    
        else:
            # Multiple files conversion
            input_paths = []
            for file in files:
                input_path = await save_uploaded_file(file, session_id)
                input_paths.append(input_path)
            
            try:
                output_path = await asyncio.get_event_loop().run_in_executor(
                    None, pdf_generator.convert_multiple, input_paths, session_id
                )
                
                return FileResponse(
                    output_path,
                    media_type='application/pdf',
                    filename="combined_document.pdf"
                )
                
            finally:
                for path in input_paths:
                    await cleanup_file(path)
                if 'output_path' in locals():
                    await cleanup_file(output_path)
                    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")

@app.post("/convert/from-pdf")
async def convert_from_pdf(
    file: UploadFile = File(...),
    format_type: str = Form("image")
):
    """
    Convert PDF to other formats:
    - image: Extract images as ZIP
    - text: Extract text as TXT
    - docx: Convert to DOCX (basic conversion)
    """
    try:
        # Validate file
        await validate_file(file, ALLOWED_FROM_PDF)
        
        # Validate format type
        valid_formats = ['image', 'text', 'docx']
        if format_type not in valid_formats:
            raise HTTPException(status_code=400, detail="Invalid format type")

        session_id = str(uuid.uuid4())
        pdf_extractor = PDFExtractor()

        # Save uploaded file
        input_path = await save_uploaded_file(file, session_id)
        
        try:
            # Process based on format type
            if format_type == 'image':
                output_path = await asyncio.get_event_loop().run_in_executor(
                    None, pdf_extractor.extract_images, input_path, session_id
                )
                media_type = 'application/zip'
                filename = f"{os.path.splitext(file.filename)[0]}_images.zip"
                
            elif format_type == 'text':
                output_path = await asyncio.get_event_loop().run_in_executor(
                    None, pdf_extractor.extract_text, input_path, session_id
                )
                media_type = 'text/plain'
                filename = f"{os.path.splitext(file.filename)[0]}.txt"
                
            else:  # docx
                output_path = await asyncio.get_event_loop().run_in_executor(
                    None, pdf_extractor.convert_to_docx, input_path, session_id
                )
                media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                filename = f"{os.path.splitext(file.filename)[0]}.docx"
            
            return FileResponse(
                output_path,
                media_type=media_type,
                filename=filename
            )
            
        finally:
            await cleanup_file(input_path)
            if 'output_path' in locals():
                await cleanup_file(output_path)
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")

async def validate_file(file: UploadFile, allowed_types: set):
    """Validate file type and size"""
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")
    
    # Check file type using python-magic
    file_content = await file.read(1024)  # Read first 1KB for magic number detection
    file.file.seek(0)  # Reset to beginning
    
    mime = magic.Magic(mime=True)
    file_type = mime.from_buffer(file_content)
    
    if file_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"File type not allowed: {file_type}")

async def save_uploaded_file(file: UploadFile, session_id: str) -> str:
    """Save uploaded file to temporary directory"""
    filename = f"{session_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    return file_path

async def cleanup_file(file_path: str):
    """Clean up temporary file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Cleanup error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
