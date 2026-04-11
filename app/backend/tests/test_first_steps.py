"""
Test Simplificado - Primeros Pasos del Orchestrator

Solo ejecuta: validation → ocr (sin segmentation, chunking, indexing, insights)
Para testeo rápido sin esperar el pipeline completo.
"""

import asyncio
import asyncpg
import sys
import os
import logging
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


async def test_first_steps(document_id: str, filename: str, filepath: str):
    """
    Test solo de validation y OCR (primeros pasos).
    """
    logger.info("=" * 80)
    logger.info("🧪 TEST SIMPLIFICADO - Primeros Pasos")
    logger.info("=" * 80)
    
    # Build database URL
    user = os.getenv("POSTGRES_USER", "raguser")
    password = os.getenv("POSTGRES_PASSWORD", "ragpassword")
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "rag_enterprise")
    
    db_url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    
    logger.info(f"📡 Connecting to: {host}:{port}/{db}")
    db_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2, command_timeout=120)
    
    try:
        # Verify file
        logger.info(f"\n📄 Verificando archivo: {filepath}")
        if not os.path.exists(filepath):
            logger.error(f"❌ Archivo no encontrado")
            return False
        
        file_size = os.path.getsize(filepath) / (1024 * 1024)
        logger.info(f"   Tamaño: {file_size:.2f} MB")
        logger.info(f"   Filename: {filename}")
        logger.info(f"   Document ID: {document_id}")
        
        # Import modules
        logger.info("\n🔧 Importando módulos...")
        from ocr_service import analyze_pdf
        from ocr_service_ocrmypdf import OCRServiceOCRmyPDF
        
        # STEP 1: Validation (simple check)
        logger.info("\n" + "=" * 80)
        logger.info("📋 STEP 1: VALIDATION")
        logger.info("=" * 80)
        
        start_validation = time.time()
        
        # Check if file is valid PDF
        try:
            with open(filepath, 'rb') as f:
                header = f.read(5)
            is_valid_pdf = header == b'%PDF-'
            
            if is_valid_pdf:
                logger.info("✅ Validation: Archivo es un PDF válido")
            else:
                logger.error(f"❌ Validation: No es un PDF (header: {header})")
                return False
        except Exception as e:
            logger.error(f"❌ Validation failed: {e}")
            return False
        
        validation_duration = time.time() - start_validation
        logger.info(f"⏱️  Validation duration: {validation_duration:.2f}s")
        
        # STEP 2: OCR
        logger.info("\n" + "=" * 80)
        logger.info("🔍 STEP 2: OCR")
        logger.info("=" * 80)
        
        start_ocr = time.time()
        
        # Analyze PDF to determine strategy
        logger.info("📊 Analizando PDF...")
        pdf_info = analyze_pdf(filepath)
        
        logger.info(f"   Páginas: {pdf_info['page_count']}")
        logger.info(f"   Text ratio: {pdf_info['text_ratio']:.2%}")
        logger.info(f"   Es escaneado: {pdf_info['is_scanned']}")
        logger.info(f"   Tiene texto: {pdf_info['has_text']}")
        
        # Decide strategy
        if pdf_info['is_scanned'] or pdf_info['text_ratio'] < 0.5:
            logger.info("\n🤖 Estrategia: OCRmyPDF (PDF escaneado)")
            logger.info("   ⚠️  NOTA: OCRmyPDF puede tardar varios minutos...")
            
            ocr_service = OCRServiceOCRmyPDF()
            text = ocr_service.extract_text(filepath)
            engine = 'ocrmypdf'
        else:
            logger.info("\n⚡ Estrategia: PyMuPDF (PDF de texto)")
            import fitz
            doc = fitz.open(filepath)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            engine = 'pymupdf'
        
        ocr_duration = time.time() - start_ocr
        text_length = len(text)
        
        logger.info("\n" + "=" * 80)
        logger.info("📊 RESULTADOS OCR")
        logger.info("=" * 80)
        logger.info(f"✅ Engine usado: {engine}")
        logger.info(f"✅ Texto extraído: {text_length:,} caracteres")
        logger.info(f"✅ Páginas procesadas: {pdf_info['page_count']}")
        logger.info(f"⏱️  Duración OCR: {ocr_duration:.2f}s ({ocr_duration/60:.2f} min)")
        
        # Show text sample
        if text:
            logger.info("\n📝 Muestra de texto extraído (primeros 500 chars):")
            logger.info("-" * 80)
            sample = text[:500].strip()
            logger.info(sample)
            if len(text) > 500:
                logger.info("... (truncado)")
            logger.info("-" * 80)
        
        # Summary
        total_duration = validation_duration + ocr_duration
        logger.info("\n" + "=" * 80)
        logger.info("📈 RESUMEN FINAL")
        logger.info("=" * 80)
        logger.info(f"✅ Validation: {validation_duration:.2f}s")
        logger.info(f"✅ OCR: {ocr_duration:.2f}s ({engine})")
        logger.info(f"✅ Total: {total_duration:.2f}s ({total_duration/60:.2f} min)")
        logger.info(f"✅ Texto extraído: {text_length:,} caracteres")
        
        # Check if should skip insights
        if ocr_duration > 300:  # > 5 min
            logger.warning(f"\n⚠️  OCR tardó {ocr_duration:.2f}s (> 5 min)")
            logger.warning("   Recomendación: skip_insights=True para este documento")
        
        return True
    
    except Exception as e:
        logger.error(f"\n❌ ERROR: {e}", exc_info=True)
        return False
    
    finally:
        await db_pool.close()


async def main():
    if len(sys.argv) < 4:
        print("Usage: python test_first_steps.py <document_id> <filename> <filepath>")
        print()
        print("Example:")
        print("  python test_first_steps.py test-doc-001 '13-02-26-El Pais.pdf' '/app/local-data/inbox/processed/c35ba0f3_13-02-26-El Pais.pdf'")
        sys.exit(1)
    
    document_id = sys.argv[1]
    filename = sys.argv[2]
    filepath = sys.argv[3]
    
    success = await test_first_steps(document_id, filename, filepath)
    
    if success:
        print("\n🎉 TEST EXITOSO")
    else:
        print("\n❌ TEST FALLIDO")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
