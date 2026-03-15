from fastapi import FastAPI, UploadFile, File, HTTPException
from pathlib import Path
import ocrmypdf
import tempfile
import logging
import os
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="OCR Service",
    description="High-performance OCR using OCRmyPDF + Tesseract",
    version="1.0.0"
)

# Configuración
TESSERACT_LANG = os.getenv("TESSERACT_LANG", "spa+eng")
OCR_THREADS = int(os.getenv("OCR_THREADS", "4"))

@app.get("/")
async def root():
    """Root endpoint - información del servicio"""
    return {
        "service": "OCR Service",
        "engine": "OCRmyPDF + Tesseract",
        "languages": TESSERACT_LANG,
        "threads": OCR_THREADS,
        "status": "ready"
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "engine": "ocrmypdf+tesseract",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/extract")
async def extract_text(file: UploadFile = File(...)):
    """
    Extrae texto de PDF usando OCRmyPDF + Tesseract
    
    Compatible con interfaz de Tika original:
    - Input: PDF file (multipart/form-data)
    - Output: JSON {"text": "...", "status": "success"}
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    logger.info(f"📄 Processing PDF: {file.filename}")
    start_time = datetime.utcnow()
    
    # Crear archivo temporal para input
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_in:
        content = await file.read()
        tmp_in.write(content)
        tmp_in_path = tmp_in.name
    
    try:
        # ESTRATEGIA 1: Intentar extraer texto directamente primero
        logger.info(f"ℹ️  Trying direct text extraction for {file.filename}")
        import subprocess
        result = subprocess.run(
            ['pdftotext', tmp_in_path, '-'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        extracted_text = result.stdout.strip()
        
        # Si hay suficiente texto (>100 chars), usar eso
        if len(extracted_text) > 100:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"✅ Direct extraction successful for {file.filename} in {elapsed:.2f}s ({len(extracted_text)} chars)")
            
            return {
                "text": extracted_text,
                "status": "success",
                "filename": file.filename,
                "processing_time_seconds": elapsed,
                "engine": "pdftotext"
            }
        
        # ESTRATEGIA 2: Si no hay texto, hacer OCR completo
        logger.info(f"🔍 No text found, starting OCR for {file.filename}")
        tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        tmp_out_path = tmp_out.name
        tmp_out.close()
        
        try:
            # Ejecutar OCRmyPDF en subproceso para capturar el archivo output
            # ANTES de que pikepdf intente validarlo
            import subprocess
            import shlex
            
            cmd = [
                'ocrmypdf',
                '--language', TESSERACT_LANG,
                '--output-type', 'pdf',
                '--deskew',
                '--clean',
                '--force-ocr',
                '--jobs', str(OCR_THREADS),
                '--skip-big', '10',
                tmp_in_path,
                tmp_out_path
            ]
            
            logger.info(f"🚀 Running: ocrmypdf with {OCR_THREADS} threads")
            
            # Ejecutar OCRmyPDF como subproceso
            # Timeout aumentado a 30 minutos para PDFs grandes (17+ MB)
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minutos max para documentos grandes
            )
            
            # Si el archivo de salida existe, intentar extraer texto
            # independientemente del exit code (puede ser exitoso pero con warnings)
            if Path(tmp_out_path).exists() and Path(tmp_out_path).stat().st_size > 0:
                logger.info(f"✅ OCR generated output file, extracting text...")
                
                result = subprocess.run(
                    ['pdftotext', tmp_out_path, '-'],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                extracted_text = result.stdout
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                
                if len(extracted_text.strip()) > 50:
                    logger.info(f"✅ OCR completed for {file.filename} in {elapsed:.2f}s ({len(extracted_text)} chars)")
                    
                    return {
                        "text": extracted_text,
                        "status": "success",
                        "filename": file.filename,
                        "processing_time_seconds": elapsed,
                        "engine": "ocrmypdf+tesseract",
                        "exit_code": process.returncode
                    }
                else:
                    logger.warning(f"⚠️  OCR produced empty text for {file.filename}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"OCR completed but extracted no text"
                    )
            else:
                # OCR falló completamente
                logger.error(f"❌ OCR failed for {file.filename}: {process.stderr}")
                raise HTTPException(
                    status_code=500,
                    detail=f"OCR failed: {process.stderr[:200]}"
                )
        
        finally:
            Path(tmp_out_path).unlink(missing_ok=True)
        
    except subprocess.TimeoutExpired:
        logger.error(f"⏱️  Timeout processing {file.filename}")
        raise HTTPException(
            status_code=408,
            detail=f"Processing timeout for {file.filename}"
        )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
        
    except Exception as e:
        logger.error(f"❌ Unexpected error for {file.filename}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Processing failed: {str(e)}"
        )
    finally:
        Path(tmp_in_path).unlink(missing_ok=True)

@app.get("/version")
async def version():
    """Retorna versión de OCRmyPDF y Tesseract"""
    import subprocess
    
    # Versión de Tesseract
    tesseract_version = subprocess.run(
        ['tesseract', '--version'],
        capture_output=True,
        text=True
    ).stderr.split('\n')[0]
    
    return {
        "ocrmypdf": "15.4.4",
        "tesseract": tesseract_version,
        "languages": TESSERACT_LANG
    }
