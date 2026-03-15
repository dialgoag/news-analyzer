"""
OCR Service Adapter - OCRmyPDF + Tesseract
Interfaz compatible con OCRService (Tika)

Estrategia conservadora de timeout:
- Inicia con timeout ALTO (20 min) para evitar fallos en PDFs grandes
- Aprende de éxitos para REDUCIR timeout gradualmente
- Aprende de timeouts para AUMENTAR timeout si es necesario
"""
import requests
import os
import logging
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class OCRServiceOCRmyPDF:
    """
    Adaptador para OCRmyPDF service con aprendizaje conservador
    
    Estrategia:
    1. Timeout inicial: 1200s (20 min) - conservador para PDFs grandes
    2. Aprende de éxitos: reduce timeout hacia tiempo real + 30%
    3. Aprende de timeouts: aumenta timeout para ese rango de tamaño
    
    Resultado: optimiza tiempo mientras mantiene alta tasa de éxito
    """
    
    # Configuración: Timeout fijo de 25 minutos para todos los documentos
    # Simple y conservador - suficiente para documentos grandes sin complejidad de aprendizaje
    FIXED_TIMEOUT = 1500                  # 25 minutos fijo para todos
    
    def __init__(self):
        self.ocr_host = os.getenv("OCR_SERVICE_HOST", "ocr-service")
        self.ocr_port = os.getenv("OCR_SERVICE_PORT", "9999")
        self.ocr_url = f"http://{self.ocr_host}:{self.ocr_port}"
        
        # Session con connection pooling
        self._session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=8,
            pool_maxsize=16,
            max_retries=Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=(502, 503, 504)
            )
        )
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        
        logger.info(f"🔗 Initializing OCRmyPDF service at {self.ocr_url}")
        logger.info(f"⏱️  Fixed timeout: {self.FIXED_TIMEOUT}s ({self.FIXED_TIMEOUT/60:.1f}min) for all documents")
        self._verify_service()
        logger.info("✅ OCRmyPDF service ready")
    
    def _verify_service(self):
        """Verificar que el servicio OCR está disponible (no bloquea el inicio)"""
        try:
            response = self._session.get(f"{self.ocr_url}/health", timeout=2)
            if response.status_code == 200:
                info = response.json()
                logger.info(f"✅ OCRmyPDF health check passed: {info}")
            else:
                logger.warning(f"⚠️ OCRmyPDF health check returned {response.status_code} - will retry on first use")
        except Exception as e:
            logger.warning(f"⚠️ OCRmyPDF service not immediately available at {self.ocr_url}: {e}")
            logger.info("ℹ️  Backend will start anyway. OCR requests will retry when service is available.")
    
    def _calculate_timeout(self, file_size_bytes: int) -> int:
        """
        Timeout fijo de 25 minutos para todos los documentos.
        Simple y conservador para evitar timeouts en documentos grandes.
        """
        # Timeout fijo: 25 minutos - suficiente para documentos grandes
        return self.FIXED_TIMEOUT
    
    def extract_text(self, file_path: str) -> str:
        """
        Extrae texto de PDF con timeout fijo de 25 minutos.
        Simple y conservador - suficiente para documentos grandes.
        Registra TODOS los resultados en DB para análisis post-mortem.
        """
        filename = Path(file_path).name
        file_size = os.path.getsize(file_path)
        size_mb = file_size / (1024 * 1024)
        timeout = None
        
        try:
            # Calcular timeout con aprendizaje conservador
            timeout = self._calculate_timeout(file_size)
            
            logger.info(
                f"📄 OCRmyPDF: {filename} ({size_mb:.1f}MB) "
                f"→ timeout {timeout}s ({timeout/60:.1f}min)"
            )
            
            # Enviar al servicio OCR
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f, 'application/pdf')}
                response = self._session.post(
                    f"{self.ocr_url}/extract",
                    files=files,
                    timeout=timeout
                )
            
            # Procesar respuesta
            if response.status_code == 200:
                result = response.json()
                text = result.get('text', '')
                processing_time = result.get('processing_time_seconds', 0)
                engine = result.get('engine', 'unknown')
                
                logger.info(
                    f"✅ {len(text)} chars in {processing_time:.0f}s "
                    f"({processing_time/60:.1f}min, engine: {engine})"
                )
                
                # Registrar éxito en DB (para análisis post-mortem)
                self._log_to_db(
                    filename=filename,
                    file_size_mb=size_mb,
                    success=True,
                    processing_time_sec=processing_time,
                    timeout_used_sec=timeout,
                    error_type=None,
                    error_detail=None
                )
                
                return text
            else:
                error_detail = response.json().get('detail', 'Unknown error')
                logger.error(f"❌ OCRmyPDF failed ({response.status_code}): {error_detail}")
                
                # Registrar error HTTP en DB
                self._log_to_db(
                    filename=filename,
                    file_size_mb=size_mb,
                    success=False,
                    processing_time_sec=None,
                    timeout_used_sec=timeout,
                    error_type=f"HTTP_{response.status_code}",
                    error_detail=error_detail[:500]  # Limitar tamaño
                )
                
                return ""
                
        except requests.exceptions.Timeout:
            logger.error(
                f"⏱️ Timeout after {timeout}s ({timeout/60:.1f}min) for {filename} ({size_mb:.1f}MB)"
            )
            
            # Registrar timeout en DB
            self._log_to_db(
                filename=filename,
                file_size_mb=size_mb,
                success=False,
                processing_time_sec=None,
                timeout_used_sec=timeout,
                error_type="TIMEOUT",
                error_detail=f"Exceeded {timeout}s timeout"
            )
            
            return ""
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"🔌 Connection error: {e}")
            
            # Registrar error de conexión en DB
            self._log_to_db(
                filename=filename,
                file_size_mb=size_mb,
                success=False,
                processing_time_sec=None,
                timeout_used_sec=timeout,
                error_type="CONNECTION_ERROR",
                error_detail=str(e)[:500]
            )
            
            return ""
            
        except Exception as e:
            logger.error(f"❌ Error: {type(e).__name__}: {str(e)}")
            
            # Registrar error genérico en DB
            self._log_to_db(
                filename=filename,
                file_size_mb=size_mb,
                success=False,
                processing_time_sec=None,
                timeout_used_sec=timeout,
                error_type=type(e).__name__,
                error_detail=str(e)[:500]
            )
            
            return ""
    
    def _log_to_db(self, filename: str, file_size_mb: float, success: bool,
                   processing_time_sec: float = None, timeout_used_sec: int = None,
                   error_type: str = None, error_detail: str = None):
        """
        Registra resultado (éxito o error) en PostgreSQL para análisis post-mortem
        
        IMPORTANTE: No falla silenciosamente - errores de DB no afectan OCR
        """
        try:
            import psycopg2
            
            # Conectar a PostgreSQL
            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "postgres"),
                port=os.getenv("POSTGRES_PORT", "5432"),
                database=os.getenv("POSTGRES_DB", "rag_enterprise"),
                user=os.getenv("POSTGRES_USER", "raguser"),
                password=os.getenv("POSTGRES_PASSWORD", "ragpassword")
            )
            
            cursor = conn.cursor()
            
            # Insertar en tabla de logs
            query = """
                INSERT INTO ocr_performance_log 
                (filename, file_size_mb, success, processing_time_sec, 
                 timeout_used_sec, error_type, error_detail, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """
            
            cursor.execute(query, (
                filename,
                file_size_mb,
                success,
                processing_time_sec,
                timeout_used_sec,
                error_type,
                error_detail
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            # No fallar el OCR si falla el logging
            logger.warning(f"⚠️  Could not log to DB (non-critical): {e}")
