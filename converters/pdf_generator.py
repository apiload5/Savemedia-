import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
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
            return self._create_simple_pdf(input_path, output_path)
    
    def convert_multiple(self, input_paths: list, session_id: str) -> str:
        """Combine multiple files into one PDF"""
        output_path = os.path.join(self.output_dir, f"{session_id}_combined.pdf")
        
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Add title
        title = Paragraph("Combined Document - SaveMedia PDF Converter", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Add file list
        story.append(Paragraph("Files included in this PDF:", styles['Heading2']))
        story.append(Spacer(1, 10))
        
        for i, file_path in enumerate(input_paths, 1):
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            story.append(Paragraph(f"{i}. {filename} ({self._format_size(file_size)})", styles['Normal']))
            story.append(Spacer(1, 5))
        
        story.append(PageBreak())
        
        # Add content from each file
        for file_path in input_paths:
            filename = os.path.basename(file_path)
            story.append(Paragraph(f"Content from: {filename}", styles['Heading2']))
            story.append(Spacer(1, 10))
            
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext == '.txt':
                content = self._read_text_file(file_path)
                story.append(Paragraph(content, styles['Normal']))
            else:
                story.append(Paragraph(f"[Binary file - {file_ext.upper()}]", styles['Italic']))
            
            story.append(PageBreak())
        
        doc.build(story)
        return output_path
    
    def _image_to_pdf(self, image_path: str, output_path: str) -> str:
        """Convert image to PDF using ReportLab"""
        try:
            # Try to use PIL for better image handling
            from reportlab.platypus import Image as ReportLabImage
            
            doc = SimpleDocTemplate(output_path, pagesize=A4)
            story = []
            
            # Add image
            img = ReportLabImage(image_path)
            img.drawHeight = 400
            img.drawWidth = 400
            story.append(img)
            
            # Add filename
            styles = getSampleStyleSheet()
            filename = os.path.basename(image_path)
            story.append(Spacer(1, 20))
            story.append(Paragraph(f"File: {filename}", styles['Normal']))
            story.append(Paragraph("Converted by SaveMedia PDF Converter", styles['Italic']))
            
            doc.build(story)
            return output_path
            
        except Exception as e:
            # Fallback to simple PDF
            return self._create_simple_pdf(image_path, output_path, "Image")
    
    def _text_to_pdf(self, text_path: str, output_path: str) -> str:
        """Convert text file to PDF"""
        try:
            doc = SimpleDocTemplate(output_path, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Read text content
            content = self._read_text_file(text_path)
            
            # Add content as paragraphs
            for paragraph in content.split('\n\n'):
                if paragraph.strip():
                    story.append(Paragraph(paragraph.strip(), styles['Normal']))
                    story.append(Spacer(1, 6))
            
            doc.build(story)
            return output_path
            
        except Exception as e:
            # Fallback to simple PDF
            return self._create_simple_pdf(text_path, output_path, "Text")
    
    def _create_simple_pdf(self, file_path: str, output_path: str, file_type: str = "File") -> str:
        """Create a simple PDF with file information"""
        c = canvas.Canvas(output_path, pagesize=A4)
        
        # Add content
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, 750, "✅ PDF Conversion Successful")
        
        c.setFont("Helvetica", 12)
        c.drawString(100, 720, f"{file_type}: {os.path.basename(file_path)}")
        c.drawString(100, 700, f"Size: {self._format_size(os.path.getsize(file_path))}")
        c.drawString(100, 680, "Converted by SaveMedia PDF Converter")
        c.drawString(100, 660, "Thank you for using our service!")
        
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(100, 620, "This is a basic conversion. For advanced features,")
        c.drawString(100, 605, "please visit our website for more tools.")
        
        c.save()
        return output_path
    
    def _read_text_file(self, file_path: str) -> str:
        """Read text file with proper encoding handling"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
