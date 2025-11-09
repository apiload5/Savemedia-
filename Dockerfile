# ------------------------------
# SaveMedia PDF Tools — Full Dockerfile
# ------------------------------

# Base image (Python 3.11 slim version)
FROM python:3.11-slim

# Maintainer info (optional)
LABEL maintainer="SaveMedia.online PDF Tools"
LABEL version="1.0"

# Prevent interactive apt installs
ENV DEBIAN_FRONTEND=noninteractive

# Update + install system dependencies for PDF & DOCX conversions
RUN apt-get update && apt-get install -y \
    libreoffice \
    poppler-utils \
    fonts-dejavu-core \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project into container
COPY . .

# Expose port 8000 for Uvicorn
EXPOSE 8000

# Default run command
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
