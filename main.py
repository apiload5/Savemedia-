from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import aiofiles
import asyncio
from typing import List

app = FastAPI(title="SaveMedia PDF Converter", version="1.0.0")

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

# Allowed file extensions
ALLOWED_TO_PDF = {'.png', '.jpg', '.jpeg', '.webp', '.tiff', '.bmp', '.txt', '.pdf'}
ALLOWED_FROM_PDF = {'.pdf'}

@app.get("/")
async def root():
    return {
        "message": "SaveMedia PDF Converter API", 
        "status": "active",
        "version": "1.0.0"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "pdf-converter"}

@app.post("/convert/to-pdf")
async def convert_to_pdf(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    conversion_type: str = Form("single")
):
    """
    Convert files to PDF format
    """
    try:
        print(f"🔄 Conversion request: {len(files)} files, type: {conversion_type}")
        
        if not files or len(files) == 0:
            raise HTTPException(status_code=400, detail="No files provided")

        # Validate files
        for file in files:
            file_ext = os.path.splitext(file.filename.lower())[1]
            if file_ext not in ALLOWED_TO_PDF:
                raise HTTPException(status_code=400, detail=f"File type not allowed: {file_ext}")

        session_id = str(uuid.uuid4())
        
        if conversion_type == "single" and len(files) == 1:
            # Single file conversion
            return await convert_single_file(background_tasks, files[0], session_id)
        else:
            # Multiple files conversion
            return await convert_multiple_files(background_tasks, files, session_id)
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Conversion error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")

async def convert_single_file(background_tasks: BackgroundTasks, file: UploadFile, session_id: str):
    """Convert single file to PDF"""
    try:
        # Save uploaded file
        input_path = await save_uploaded_file(file, session_id)
        print(f"💾 File saved: {input_path}")
        
        # Convert to PDF
        from converters.pdf_generator import PDFGenerator
        pdf_generator = PDFGenerator()
        
        output_path = await asyncio.get_event_loop().run_in_executor(
            None, pdf_generator.convert_single, input_path, session_id
        )
        
        print(f"✅ PDF created: {output_path}")
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_file, input_path)
        background_tasks.add_task(cleanup_file, output_path)
        
        # Return PDF file
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename=f"{os.path.splitext(file.filename)[0]}.pdf"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Single conversion failed: {str(e)}")

async def convert_multiple_files(background_tasks: BackgroundTasks, files: List[UploadFile], session_id: str):
    """Convert multiple files to single PDF"""
    try:
        input_paths = []
        
        # Save all uploaded files
        for file in files:
            input_path = await save_uploaded_file(file, session_id)
            input_paths.append(input_path)
            print(f"💾 File saved: {input_path}")
        
        # Convert to combined PDF
        from converters.pdf_generator import PDFGenerator
        pdf_generator = PDFGenerator()
        
        output_path = await asyncio.get_event_loop().run_in_executor(
            None, pdf_generator.convert_multiple, input_paths, session_id
        )
        
        print(f"✅ Combined PDF created: {output_path}")
        
        # Schedule cleanup
        for path in input_paths:
            background_tasks.add_task(cleanup_file, path)
        background_tasks.add_task(cleanup_file, output_path)
        
        # Return combined PDF
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="combined_document.pdf"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multiple conversion failed: {str(e)}")

@app.post("/convert/from-pdf")
async def convert_from_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    format_type: str = Form("text")
):
    """
    Convert PDF to other formats
    """
    try:
        print(f"🔄 PDF extraction: {file.filename}, format: {format_type}")
        
        # Validate file
        file_ext = os.path.splitext(file.filename.lower())[1]
        if file_ext not in ALLOWED_FROM_PDF:
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Validate format type
        valid_formats = ['image', 'text', 'docx']
        if format_type not in valid_formats:
            raise HTTPException(status_code=400, detail="Invalid format type")

        session_id = str(uuid.uuid4())
        
        # Save uploaded file
        input_path = await save_uploaded_file(file, session_id)
        print(f"💾 PDF saved: {input_path}")
        
        # Process based on format type
        from converters.pdf_extractor import PDFExtractor
        pdf_extractor = PDFExtractor()

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
        
        print(f"✅ Extraction successful: {output_path}")
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_file, input_path)
        background_tasks.add_task(cleanup_file, output_path)
        
        return FileResponse(
            output_path,
            media_type=media_type,
            filename=filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Extraction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

async def save_uploaded_file(file: UploadFile, session_id: str) -> str:
    """Save uploaded file to temporary directory"""
    filename = f"{session_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    # Read file content
    content = await file.read()
    
    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    return file_path

async def cleanup_file(file_path: str):
    """Clean up temporary file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🧹 Cleaned up: {file_path}")
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
