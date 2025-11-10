from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import aiofiles
import asyncio
from converters.pdf_generator import PDFGenerator
from converters.pdf_extractor import PDFExtractor

app = FastAPI(title="SaveMedia PDF Converter")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://pdf.savemedia.online"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
UPLOAD_DIR = "temp/uploads"
OUTPUT_DIR = "temp/output"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Create directories
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Allowed file extensions (without magic)
ALLOWED_TO_PDF_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.tiff', '.bmp', '.txt', 
                      '.doc', '.docx', '.odt', '.ppt', '.pptx', '.xls', '.xlsx', '.pdf'}

ALLOWED_FROM_PDF_EXT = {'.pdf'}

@app.get("/")
async def root():
    return JSONResponse({
        "message": "SaveMedia PDF Converter API is running!",
        "status": "active",
        "version": "2.0.0"
    })

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "pdf-converter"}

@app.post("/convert/to-pdf")
async def convert_to_pdf(
    files: list[UploadFile] = File(...),
    conversion_type: str = Form("single")
):
    """Convert files to PDF format"""
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        # Validate file size and type
        for file in files:
            await validate_file(file, ALLOWED_TO_PDF_EXT)

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
    """Convert PDF to other formats"""
    try:
        # Validate file
        await validate_file(file, ALLOWED_FROM_PDF_EXT)
        
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

async def validate_file(file: UploadFile, allowed_extensions: set):
    """Validate file extension and size"""
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")
    
    # Check file extension
    file_ext = os.path.splitext(file.filename.lower())[1]
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"File type not allowed: {file_ext}")

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
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
