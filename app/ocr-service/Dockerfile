FROM python:3.11-slim

# Dependencias del sistema para OCRmyPDF + Tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-eng \
    ghostscript \
    libmagic1 \
    poppler-utils \
    qpdf \
    unpaper \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python
RUN pip install --no-cache-dir \
    ocrmypdf>=15.4.4 \
    pymupdf>=1.24.0 \
    fastapi>=0.109.0 \
    uvicorn[standard]>=0.27.0 \
    python-multipart>=0.0.6

WORKDIR /app
COPY app.py /app/

EXPOSE 9999

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9999", "--workers", "2"]
