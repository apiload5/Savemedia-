# ------------------------------
# SaveMedia PDF Tools — Full Dockerfile
# ------------------------------

FROM python:3.11-slim

LABEL maintainer="SaveMedia.online PDF Tools"
LABEL version="1.0"

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    libreoffice \
    poppler-utils \
    fonts-dejavu-core \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# ✅ Important fix for Railway (uses dynamic $PORT)
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
