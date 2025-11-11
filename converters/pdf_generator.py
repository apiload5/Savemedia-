import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

class PDFGenerator:
    def __init__(self):
        self.output_dir = "temp/output"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def convert_single(self, input_path: str, session_id: str) -> str:
        """Create a simple PDF"""
        output_path = os.path.join(self.output_dir, f"{session_id}_output.pdf")
        
        c = canvas.Canvas(output_path, pagesize=letter)
        c.drawString(100, 750, "PDF Conversion Successful")
        c.drawString(100, 730, f"File: {os.path.basename(input_path)}")
        c.save()
        
        return output_path
    
    def convert_multiple(self, input_paths: list, session_id: str) -> str:
        """Create a combined PDF"""
        output_path = os.path.join(self.output_dir, f"{session_id}_combined.pdf")
        
        c = canvas.Canvas(output_path, pagesize=letter)
        y_position = 750
        
        c.drawString(100, y_position, "Combined PDF Document")
        y_position -= 30
        
        for i, file_path in enumerate(input_paths):
            c.drawString(100, y_position, f"{i+1}. {os.path.basename(file_path)}")
            y_position -= 20
            
            if y_position < 50:
                c.showPage()
                y_position = 750
        
        c.save()
        return output_path
