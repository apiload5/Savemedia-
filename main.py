from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import aiofiles
import asyncio
from typing import List

app = FastAPI()

# CORS configuration - IMPORTANT: Add response headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://pdf.savemedia.online"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]  # This is IMPORTANT for file downloads
)

# Configuration
UPLOAD_DIR = "temp/uploads"
OUTPUT_DIR = "temp/output"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Create directories
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.get("/")
async def root():
    return {"message": "SaveMedia PDF Converter API", "status": "active"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/convert/to-pdf")
async def convert_to_pdf(
    files: List[UploadFile] = File(...),
    conversion_type: str = Form("single")
):
    try:
        print(f"🔄 Conversion request: {len(files)} files")
        
        if not files or len(files) == 0:
            return JSONResponse(
                {"error": "No files provided", "status": "failed"},
                status_code=400
            )

        session_id = str(uuid.uuid4())
        
        if conversion_type == "single" and len(files) == 1:
            return await handle_single_conversion(files[0], session_id)
        else:
            return await handle_multiple_conversion(files, session_id)
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return JSONResponse(
            {"error": str(e), "status": "failed"},
            status_code=500
        )

async def handle_single_conversion(file: UploadFile, session_id: str):
    """Handle single file conversion"""
    input_path = None
    output_path = None
    
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
        
        # Return the PDF file for download
        response = FileResponse(
            path=output_path,
            media_type='application/pdf',
            filename=f"converted_{os.path.splitext(file.filename)[0]}.pdf",
            background=None  # Important: Don't use background tasks for cleanup
        )
        
        return response
        
    except Exception as e:
        raise e
    finally:
        # Cleanup files after response is sent
        if input_path and os.path.exists(input_path):
            await cleanup_file(input_path)
        # Don't cleanup output_path immediately - let it be downloaded first

async def handle_multiple_conversion(files: List[UploadFile], session_id: str):
    """Handle multiple files conversion"""
    input_paths = []
    
    try:
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
        
        # Return the combined PDF file
        response = FileResponse(
            path=output_path,
            media_type='application/pdf',
            filename="combined_document.pdf",
            background=None
        )
        
        return response
        
    except Exception as e:
        raise e
    finally:
        # Cleanup input files
        for path in input_paths:
            if os.path.exists(path):
                await cleanup_file(path)

@app.post("/convert/from-pdf")
async def convert_from_pdf(
    file: UploadFile = File(...),
    format_type: str = Form("text")
):
    try:
        print(f"🔄 PDF extraction: {file.filename}")
        
        if not file.filename.lower().endswith('.pdf'):
            return JSONResponse(
                {"error": "Only PDF files are allowed", "status": "failed"},
                status_code=400
            )

        session_id = str(uuid.uuid4())
        input_path = None
        output_path = None
        
        try:
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
                filename = f"images_{os.path.splitext(file.filename)[0]}.zip"
                
            elif format_type == 'text':
                output_path = await asyncio.get_event_loop().run_in_executor(
                    None, pdf_extractor.extract_text, input_path, session_id
                )
                media_type = 'text/plain'
                filename = f"text_{os.path.splitext(file.filename)[0]}.txt"
                
            else:  # docx
                output_path = await asyncio.get_event_loop().run_in_executor(
                    None, pdf_extractor.convert_to_docx, input_path, session_id
                )
                media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                filename = f"document_{os.path.splitext(file.filename)[0]}.docx"
            
            print(f"✅ Extraction successful: {output_path}")
            
            # Return the file for download
            response = FileResponse(
                path=output_path,
                media_type=media_type,
                filename=filename,
                background=None
            )
            
            return response
            
        except Exception as e:
            raise e
        finally:
            # Cleanup input file
            if input_path and os.path.exists(input_path):
                await cleanup_file(input_path)
                
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return JSONResponse(
            {"error": str(e), "status": "failed"},
            status_code=500
        )

async def save_uploaded_file(file: UploadFile, session_id: str) -> str:
    """Save uploaded file to temporary directory"""
    filename = f"{session_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    # Read and save file
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")
    
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

# Background task to cleanup old files (optional)
import threading
import time

def cleanup_old_files():
    """Clean up files older than 1 hour"""
    while True:
        try:
            now = time.time()
            for dir_path in [UPLOAD_DIR, OUTPUT_DIR]:
                if os.path.exists(dir_path):
                    for filename in os.listdir(dir_path):
                        file_path = os.path.join(dir_path, filename)
                        if os.path.isfile(file_path):
                            # Delete files older than 1 hour
                            if now - os.path.getctime(file_path) > 3600:
                                os.remove(file_path)
                                print(f"🧹 Cleaned old file: {file_path}")
        except Exception as e:
            print(f"Cleanup error: {e}")
        time.sleep(3600)  # Run every hour

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
