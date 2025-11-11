from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import aiofiles
import asyncio

app = FastAPI()

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
ALLOWED_TO_PDF_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.tiff', '.bmp', '.txt', '.pdf'}
ALLOWED_FROM_PDF_EXT = {'.pdf'}

@app.get("/")
async def root():
    return {"message": "SaveMedia PDF Converter API", "status": "active"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/convert/to-pdf")
async def convert_to_pdf(
    files: list[UploadFile] = File(...),
    conversion_type: str = Form("single")
):
    try:
        print(f"Conversion request received: {len(files)} files")
        
        if not files or len(files) == 0:
            raise HTTPException(status_code=400, detail="No files provided")

        # Validate files
        for file in files:
            await validate_file(file, ALLOWED_TO_PDF_EXT)

        session_id = str(uuid.uuid4())

        if conversion_type == "single" and len(files) == 1:
            # Single file conversion
            file = files[0]
            input_path = await save_uploaded_file(file, session_id)
            
            try:
                # ACTUAL CONVERSION CALL
                from converters.pdf_generator import PDFGenerator
                pdf_generator = PDFGenerator()
                output_path = await asyncio.get_event_loop().run_in_executor(
                    None, pdf_generator.convert_single, input_path, session_id
                )
                
                print(f"Conversion successful: {output_path}")
                return FileResponse(
                    output_path,
                    media_type='application/pdf',
                    filename=f"{os.path.splitext(file.filename)[0]}.pdf"
                )
                
            except Exception as e:
                print(f"Conversion error: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")
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
                # ACTUAL CONVERSION CALL
                from converters.pdf_generator import PDFGenerator
                pdf_generator = PDFGenerator()
                output_path = await asyncio.get_event_loop().run_in_executor(
                    None, pdf_generator.convert_multiple, input_paths, session_id
                )
                
                print(f"Multiple conversion successful: {output_path}")
                return FileResponse(
                    output_path,
                    media_type='application/pdf',
                    filename="combined_document.pdf"
                )
                
            except Exception as e:
                print(f"Multiple conversion error: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")
            finally:
                for path in input_paths:
                    await cleanup_file(path)
                if 'output_path' in locals():
                    await cleanup_file(output_path)
                    
    except HTTPException:
        raise
    except Exception as e:
        print(f"General error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.post("/convert/from-pdf")
async def convert_from_pdf(
    file: UploadFile = File(...),
    format_type: str = Form("image")
):
    try:
        print(f"PDF extraction request: {file.filename}, format: {format_type}")
        
        # Validate file
        await validate_file(file, ALLOWED_FROM_PDF_EXT)
        
        # Validate format type
        valid_formats = ['image', 'text', 'docx']
        if format_type not in valid_formats:
            raise HTTPException(status_code=400, detail="Invalid format type")

        session_id = str(uuid.uuid4())

        # Save uploaded file
        input_path = await save_uploaded_file(file, session_id)
        
        try:
            # ACTUAL EXTRACTION CALL
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
            
            print(f"Extraction successful: {output_path}")
            return FileResponse(
                output_path,
                media_type=media_type,
                filename=filename
            )
            
        except Exception as e:
            print(f"Extraction error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
        finally:
            await cleanup_file(input_path)
            if 'output_path' in locals():
                await cleanup_file(output_path)
                
    except HTTPException:
        raise
    except Exception as e:
        print(f"General extraction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# MISSING FUNCTIONS - YEH ADD KARNA HAI

async def validate_file(file: UploadFile, allowed_extensions: set):
    """Validate file extension and size"""
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
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

# END OF MISSING FUNCTIONS

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
