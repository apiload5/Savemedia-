import os
from PIL import Image
import io

class PDFGenerator:
    def __init__(self):
        self.output_dir = "temp/output"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def convert_single(self, input_path: str, session_id: str) -> str:
        """Convert single file to PDF"""
        file_ext = os.path.splitext(input_path)[1].lower()
        output_path = os.path.join(self.output_dir, f"{session_id}_output.pdf")
        
        if file_ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff']:
            return self._image_to_pdf(input_path, output_path)
        elif file_ext == '.txt':
            return self._text_to_pdf(input_path, output_path)
        else:
            # For other file types, create a simple PDF with file info
            return self._generic_to_pdf(input_path, output_path)
    
    def convert_multiple(self, input_paths: list, session_id: str) -> str:
        """Combine multiple files into one PDF"""
        from PIL import Image
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.utils import ImageReader
        
        output_path = os.path.join(self.output_dir, f"{session_id}_combined.pdf")
        
        # Simple implementation - you can enhance this
        c = canvas.Canvas(output_path, pagesize=letter)
        width, height = letter
        
        y_position = height - 50
        c.drawString(50, y_position, "Combined Document")
        y_position -= 30
        
        for i, file_path in enumerate(input_paths):
            filename = os.path.basename(file_path)
            c.drawString(50, y_position, f"{i+1}. {filename}")
            y_position -= 20
            
            if y_position < 50:
                c.showPage()
                y_position = height - 50
        
        c.save()
        return output_path
    
    def _image_to_pdf(self, image_path: str, output_path: str) -> str:
        """Convert image to PDF using Pillow"""
        try:
            image = Image.open(image_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            image.save(output_path, "PDF", resolution=100.0)
            return output_path
        except Exception as e:
            raise Exception(f"Image to PDF conversion failed: {str(e)}")
    
    def _text_to_pdf(self, text_path: str, output_path: str) -> str:
        """Convert text file to PDF"""
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        
        c = canvas.Canvas(output_path, pagesize=letter)
        width, height = letter
        
        # Read text file
        with open(text_path, 'r', encoding='utf-8', errors='ignore') as f:
            text_content = f.read()
        
        # Simple text wrapping
        text_object = c.beginText(50, height - 50)
        text_object.setFont("Helvetica", 10)
        text_object.setTextOrigin(50, height - 50)
        
        lines = []
        for line in text_content.split('\n'):
            words = line.split()
            current_line = []
            for word in words:
                test_line = ' '.join(current_line + [word])
                if c.stringWidth(test_line, "Helvetica", 10) < (width - 100):
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(' '.join(current_line))
        
        # Add text to PDF
        y_position = height - 50
        for line in lines:
            if y_position < 50:
                c.showPage()
                y_position = height - 50
                text_object = c.beginText(50, y_position)
                text_object.setFont("Helvetica", 10)
            
            c.drawString(50, y_position, line[:100])  # Limit line length
            y_position -= 15
        
        c.save()
        return output_path
    
    def _generic_to_pdf(self, file_path: str, output_path: str) -> str:
        """Create a generic PDF for unsupported file types"""
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        c = canvas.Canvas(output_path, pagesize=letter)
        width, height = letter
        
        c.drawString(50, height - 50, f"File: {filename}")
        c.drawString(50, height - 80, f"Size: {file_size} bytes")
        c.drawString(50, height - 110, "This file type requires manual conversion.")
        c.drawString(50, height - 140, "Please use the desktop version for full support.")
        
        c.save()
        return output_path
