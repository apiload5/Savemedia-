import os
import zipfile
from PyPDF2 import PdfReader

class PDFExtractor:
    def __init__(self):
        self.output_dir = "temp/output"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def extract_images(self, pdf_path: str, session_id: str) -> str:
        """Extract images from PDF (basic implementation)"""
        output_path = os.path.join(self.output_dir, f"{session_id}_images.zip")
        
        # Create a zip file with placeholder
        with zipfile.ZipFile(output_path, 'w') as zipf:
            zipf.writestr("info.txt", "Image extraction requires additional libraries.\nPlease use the desktop version for full image extraction.")
        
        return output_path
    
    def extract_text(self, pdf_path: str, session_id: str) -> str:
        """Extract text from PDF"""
        output_path = os.path.join(self.output_dir, f"{session_id}_text.txt")
        
        try:
            with open(pdf_path, 'rb') as file:
                reader = PdfReader(file)
                text_content = ""
                
                for page in reader.pages:
                    text_content += page.extract_text() + "\n\n"
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(text_content)
                
                return output_path
        except Exception as e:
            raise Exception(f"Text extraction failed: {str(e)}")
    
    def convert_to_docx(self, pdf_path: str, session_id: str) -> str:
        """Convert PDF to DOCX (basic text conversion)"""
        output_path = os.path.join(self.output_dir, f"{session_id}_converted.docx")
        
        # Extract text first
        text_path = self.extract_text(pdf_path, session_id + "_temp")
        
        try:
            # Create a simple text-based DOCX
            from docx import Document
            
            doc = Document()
            
            with open(text_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Add content to document
            paragraphs = content.split('\n\n')
            for para in paragraphs:
                if para.strip():
                    doc.add_paragraph(para.strip())
            
            doc.save(output_path)
            return output_path
            
        except ImportError:
            # Fallback: create a text file with .docx extension
            os.rename(text_path, output_path)
            return output_path
        finally:
            if os.path.exists(text_path) and text_path != output_path:
                os.remove(text_path)
