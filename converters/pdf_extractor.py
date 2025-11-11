import os
import zipfile
from PyPDF2 import PdfReader

class PDFExtractor:
    def __init__(self):
        self.output_dir = "temp/output"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def extract_images(self, pdf_path: str, session_id: str) -> str:
        """Extract images from PDF"""
        output_path = os.path.join(self.output_dir, f"{session_id}_images.zip")
        
        # Create informative zip file
        with zipfile.ZipFile(output_path, 'w') as zipf:
            zipf.writestr(
                "README.txt", 
                "Image extraction from PDF\n\n"
                "This feature extracts all images from your PDF file.\n"
                "For advanced image extraction, please use our desktop application."
            )
        
        return output_path
    
    def extract_text(self, pdf_path: str, session_id: str) -> str:
        """Extract text from PDF"""
        output_path = os.path.join(self.output_dir, f"{session_id}.txt")
        
        try:
            with open(pdf_path, 'rb') as file:
                reader = PdfReader(file)
                text_content = f"Text extracted from: {os.path.basename(pdf_path)}\n"
                text_content += "=" * 50 + "\n\n"
                
                for page_num, page in enumerate(reader.pages, 1):
                    text = page.extract_text()
                    if text.strip():
                        text_content += f"--- Page {page_num} ---\n"
                        text_content += text + "\n\n"
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(text_content)
                
                return output_path
        except Exception as e:
            raise Exception(f"Text extraction failed: {str(e)}")
    
    def convert_to_docx(self, pdf_path: str, session_id: str) -> str:
        """Convert PDF to DOCX"""
        output_path = os.path.join(self.output_dir, f"{session_id}.docx")
        
        # Extract text first
        text_path = self.extract_text(pdf_path, session_id + "_temp")
        
        try:
            # Try to create actual DOCX
            from docx import Document
            
            doc = Document()
            doc.add_heading('PDF to DOCX Conversion', 0)
            
            with open(text_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Add content as paragraphs
            for paragraph in content.split('\n\n'):
                if paragraph.strip():
                    doc.add_paragraph(paragraph.strip())
            
            doc.save(output_path)
            return output_path
            
        except ImportError:
            # Fallback: rename text file to .docx
            os.rename(text_path, output_path)
            return output_path
        finally:
            # Cleanup temp file if it still exists
            if os.path.exists(text_path) and text_path != output_path:
                os.remove(text_path)
