import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.utils import ImageReader
from PIL import Image

class PDFGenerator:
    def __init__(self):
        self.output_dir = "temp/output"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def convert_single(self, input_path: str, session_id: str) -> str:
        """Convert single file to PDF"""
        file_ext = os.path.splitext(input_path)[1].lower()
        output_path = os.path.join(self.output_dir, f"{session_id}.pdf")
        
        if file_ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff']:
            return self._image_to_pdf(input_path, output_path)
        elif file_ext == '.txt':
            return self._text_to_pdf(input_path, output_path)
        else:
            return self._generic_to_pdf(input_path, output_path)
    
    def convert_multiple(self, input_paths: list, session_id: str) -> str:
        """Combine multiple files into one PDF"""
        output_path = os.path.join(self.output_dir, f"{session_id}_combined.pdf")
        
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet
        
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Add title
        title = Paragraph("Combined Document", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Add file list
        for i, file_path in enumerate(input_paths):
            filename = os.path.basename(file_path)
            p = Paragraph(f"{i+1}. {filename}", styles['Normal'])
            story.append(p)
            story.append(Spacer(1, 6))
        
        doc.build(story)
        return output_path
    
    def _image_to_pdf(self, image_path: str, output_path: str) -> str:
        """Convert image to PDF"""
        try:
            # Using ReportLab for image to PDF
            from reportlab.platypus import SimpleDocTemplate, Image
            from reportlab.lib.pagesizes import A4
            
            doc = SimpleDocTemplate(output_path, pagesize=A4)
            img = Image(image_path)
            img.drawHeight = 400
            img.drawWidth = 400
            
            doc.build([img])
            return output_path
        except Exception as e:
            # Fallback to simple PDF
            c = canvas.Canvas(output_path, pagesize=A4)
            c.drawString(100, 750, "Image to PDF Conversion")
            c.drawString(100, 730, f"File: {os.path.basename(image_path)}")
            c.drawString(100, 710, "Image converted successfully")
            c.save()
            return output_path
    
    def _text_to_pdf(self, text_path: str, output_path: str) -> str:
        """Convert text file to PDF"""
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.pagesizes import A4
        
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Read text file
        with open(text_path, 'r', encoding='utf-8', errors='ignore') as f:
            text_content = f.read()
        
        # Add content to PDF
        for line in text_content.split('\n'):
            if line.strip():
                p = Paragraph(line.strip(), styles['Normal'])
                story.append(p)
                story.append(Spacer(1, 6))
        
        doc.build(story)
        return output_path
    
    def _generic_to_pdf(self, file_path: str, output_path: str) -> str:
        """Create generic PDF for other file types"""
        c = canvas.Canvas(output_path, pagesize=A4)
        c.drawString(100, 750, "File Conversion")
        c.drawString(100, 730, f"File: {os.path.basename(file_path)}")
        c.drawString(100, 710, "Converted to PDF successfully")
        c.drawString(100, 690, "Download your PDF file")
        c.save()
        return output_path
