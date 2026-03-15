"""
OCR Service - Smart PDF Detection + Tika/OCR Processing
Automatically detects PDF type (text vs scanned) and routes appropriately.
"""
import logging
import subprocess
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import xml.etree.ElementTree as ET
from pathlib import Path
import re
import os
import threading

logger = logging.getLogger(__name__)


def analyze_pdf(file_path: str) -> dict:
    """
    Analyze a PDF to determine if it's text-based or scanned.

    Returns dict with:
    - is_scanned: True if PDF appears to be scanned/image-based
    - has_text: True if PDF has extractable text
    - page_count: Number of pages
    - text_ratio: Ratio of pages with text vs total pages
    - sample_text: Sample of extracted text (first 500 chars)
    """
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        page_count = len(doc)
        pages_with_text = 0
        total_text = ""

        # Check first 10 pages (or all if less)
        pages_to_check = min(10, page_count)

        for i in range(pages_to_check):
            page = doc[i]
            text = page.get_text().strip()
            if len(text) > 50:  # Meaningful text (not just page numbers)
                pages_with_text += 1
                if len(total_text) < 1000:
                    total_text += text + "\n"

        doc.close()

        text_ratio = pages_with_text / pages_to_check if pages_to_check > 0 else 0
        is_scanned = text_ratio < 0.3  # Less than 30% of pages have text

        result = {
            "is_scanned": is_scanned,
            "has_text": text_ratio > 0,
            "page_count": page_count,
            "text_ratio": text_ratio,
            "sample_text": total_text[:500] if total_text else ""
        }

        logger.info(f"📊 PDF Analysis: {page_count} pages, text_ratio={text_ratio:.1%}, is_scanned={is_scanned}")
        return result

    except ImportError:
        logger.warning("⚠️ PyMuPDF not installed, skipping PDF analysis")
        return {"is_scanned": False, "has_text": True, "page_count": 0, "text_ratio": 1.0, "sample_text": ""}
    except Exception as e:
        logger.error(f"❌ PDF analysis failed: {e}")
        return {"is_scanned": False, "has_text": True, "page_count": 0, "text_ratio": 1.0, "sample_text": ""}

class OCRService:
    # Get Tika host from environment variable (supports external Tika container)
    TIKA_HOST = os.getenv("TIKA_HOST", "localhost")
    TIKA_PORT = os.getenv("TIKA_PORT", "9998")
    TIKA_URL = f"http://{TIKA_HOST}:{TIKA_PORT}"
    
    MIME_TYPES = {
        '.pdf': 'application/pdf',
        '.txt': 'text/plain',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.doc': 'application/msword',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.xls': 'application/vnd.ms-excel',
        '.odt': 'application/vnd.oasis.opendocument.text',
        '.rtf': 'application/rtf',
        '.html': 'text/html',
        '.htm': 'text/html',
        '.xml': 'application/xml',
        '.json': 'application/json',
        '.csv': 'text/csv',
        '.md': 'text/markdown',
    }
    
    def __init__(self):
        logger.info("Initializing OCR Service...")
        logger.info(f"Tika URL: {self.TIKA_URL}")
        self.tika_ready = False
        self.tika_process = None
        self._tika_restart_lock = threading.Lock()
        self.is_external_tika = self.TIKA_HOST != "localhost"
        self.tika_container_name = os.getenv("TIKA_CONTAINER_NAME", "rag-tika")
        
        # Session con connection pooling para no saturar Tika con muchas conexiones nuevas
        self._session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=8,
            pool_maxsize=16,
            max_retries=Retry(total=3, backoff_factor=1, status_forcelist=(502, 503)),
        )
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        
        if self.is_external_tika:
            logger.info(f"🔗 Using external Tika service at {self.TIKA_URL}")
            self._wait_for_tika()
        else:
            logger.info("🚀 Starting embedded Tika server...")
            self._aggressive_kill_tika()
            self._start_tika()
        
        logger.info("✅ OCR Service ready")
    
    def _wait_for_tika(self):
        """Esperar a que Tika esté disponible (en lugar de iniciarlo)"""
        logger.info(f"Waiting for Tika at {self.TIKA_URL} (60 sec)...")
        for i in range(60):
            try:
                response = self._session.get(f"{self.TIKA_URL}/version", timeout=1)
                if response.status_code == 200:
                    logger.info(f"✅ Tika ready at {i}s - Version: {response.text[:100]}")
                    self.tika_ready = True
                    return
            except Exception as e:
                if i % 10 == 0:
                    logger.warning(f"Attempt {i}/60 - {type(e).__name__}: {str(e)}")
            time.sleep(1)
        
        logger.error(f"❌ Tika startup timeout! URL: {self.TIKA_URL}")
        # Try to get Tika error logs
        try:
            if self.tika_process and self.tika_process.stderr:
                stderr_output = self.tika_process.stderr.read(1000).decode('utf-8', errors='ignore')
                if stderr_output:
                    logger.error(f"Tika stderr: {stderr_output}")
        except:
            pass
        raise RuntimeError("Tika not available")
    
    def _aggressive_kill_tika(self):
        """Kill any existing Tika process"""
        try:
            # Kill any existing java process on port 9998
            subprocess.run("lsof -ti:9998 | xargs kill -9", shell=True, capture_output=True, timeout=5)
            logger.info("✅ Killed existing Tika process(es)")
        except Exception as e:
            logger.warning(f"Could not kill Tika: {e}")
        self.tika_process = None
    
    def _start_tika(self):
        """Start Tika server as a subprocess"""
        try:
            logger.info("🚀 Starting Tika server...")
            self.tika_process = subprocess.Popen(
                ["java", "-Xmx6g", "-XX:+UseG1GC", "-jar", "/opt/tika-server.jar", "-noFork"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            logger.info(f"Tika process started (PID: {self.tika_process.pid})")
            self._wait_for_tika()
        except Exception as e:
            logger.error(f"❌ Failed to start Tika: {e}")
            self.tika_ready = False
            raise

    def _restart_external_tika(self):
        """Restart external Tika Docker container using Docker socket API"""
        try:
            logger.warning(f"🔄 Restarting external Tika container: {self.tika_container_name}...")
            
            # Try using docker-py library if available
            try:
                import docker
                client = docker.DockerClient(base_url='unix://var/run/docker.sock')
                container = client.containers.get(self.tika_container_name)
                container.restart(timeout=30)
                logger.info(f"✅ Tika container restarted successfully (via Docker API)")
                # Wait for Tika to be ready
                self._wait_for_tika()
                return True
            except ImportError:
                logger.warning("Docker library not available, trying HTTP API...")
                # Fallback to HTTP API if docker-py not available
                import http.client
                import json
                
                conn = http.client.HTTPConnection('localhost', timeout=30)
                conn.request('POST', f'/containers/{self.tika_container_name}/restart?t=30', 
                           headers={'Content-Type': 'application/json'})
                
                # Connect via Unix socket
                conn = http.client.HTTPConnection('/var/run/docker.sock')
                conn.request('POST', f'/v1.41/containers/{self.tika_container_name}/restart?t=30')
                response = conn.getresponse()
                
                if response.status in (204, 200):
                    logger.info(f"✅ Tika container restarted successfully (via HTTP API)")
                    self._wait_for_tika()
                    return True
                else:
                    logger.error(f"❌ Failed to restart Tika: HTTP {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error restarting Tika container: {e}")
            logger.warning("⚠️ Will use Tesseract fallback instead")
            return False

    def _get_mime_type(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        return self.MIME_TYPES.get(ext, 'application/octet-stream')

    def _ensure_tika_healthy(self):
        """Check if Tika is responding, restart if not. Thread-safe: only one restart at a time."""
        try:
            response = self._session.get(f"{self.TIKA_URL}/version", timeout=5)
            if response.status_code == 200:
                return True
        except Exception as e:
            logger.warning(f"⚠️ Tika health check failed: {e}")

        with self._tika_restart_lock:
            # Double-check before restarting
            try:
                response = self._session.get(f"{self.TIKA_URL}/version", timeout=5)
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            
            # Si Tika es externo (Docker), intentar reiniciar el contenedor
            if self.is_external_tika:
                logger.warning("⚠️ External Tika not responding - attempting Docker restart")
                return self._restart_external_tika()
            
            # Si Tika es local (no debería existir en esta arquitectura)
            logger.warning("🔄 Restarting local Tika server...")
            self._aggressive_kill_tika()
            self._start_tika()
        return self.tika_ready

    def extract_text(self, file_path: str) -> str:
        try:
            logger.info(f"Extracting: {Path(file_path).name}")
            ext = Path(file_path).suffix.lower()

            # 1. Plain text files - read directly
            if ext in ['.txt', '.md', '.csv']:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read()
                    if text and len(text.strip()) > 0:
                        logger.info(f"✅ {len(text)} chars (direct)")
                        return text.strip()
                except Exception as e:
                    logger.warning(f"Direct read failed: {str(e)}")

            # 2. For PDFs: Analyze and route appropriately
            if ext == '.pdf':
                pdf_info = analyze_pdf(file_path)

                # TEXT PDFs: Try PyMuPDF first - it's fast and handles text PDFs well
                # SCANNED PDFs: Fall through to Tika (which uses Tesseract internally)
                if pdf_info["has_text"] and pdf_info["text_ratio"] > 0.5:
                    logger.info(f"📄 Trying PyMuPDF extraction (text_ratio={pdf_info['text_ratio']:.1%})...")
                    try:
                        import fitz
                        doc = fitz.open(file_path)
                        full_text = ""
                        for page in doc:
                            full_text += page.get_text() + "\n"
                        doc.close()
                        if full_text and len(full_text.strip()) > 500:
                            logger.info(f"✅ {len(full_text)} chars (PyMuPDF)")
                            return full_text.strip()
                        else:
                            logger.debug(f"PyMuPDF got only {len(full_text)} chars, trying Tika...")
                    except Exception as e:
                        logger.warning(f"PyMuPDF failed: {e}, trying Tika...")

            # 3. Ensure Tika is healthy
            self._ensure_tika_healthy()
            logger.debug(f"Tika ready: {self.tika_ready}")
            
            if self.tika_ready:
                try:
                    logger.debug(f"Opening file: {file_path}")
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                    logger.debug(f"File size: {len(file_data)} bytes ({len(file_data)/1024/1024:.1f}MB)")

                    mime_type = self._get_mime_type(file_path)
                    logger.debug(f"MIME type: {mime_type}")
                    # Timeout de 120s (2 minutos) - si Tika tarda más, reiniciamos y retomamos
                    logger.debug(f"Sending to Tika: {self.TIKA_URL}/tika (timeout: 120s)")
                    
                    # Track timing for performance monitoring
                    import time as time_module
                    start_time = time_module.time()

                    # Reintentos ante ConnectionError antes de reiniciar Tika (evita que 4 workers reinicien a la vez)
                    last_error = None
                    response = None
                    for attempt in range(3):
                        try:
                            attempt_start = time_module.time()
                            response = self._session.put(
                                f"{self.TIKA_URL}/tika",
                                data=file_data,
                                headers={
                                    'Content-Type': mime_type,
                                    'Accept-Charset': 'utf-8'
                                },
                                timeout=120
                            )
                            attempt_time = time_module.time() - attempt_start
                            logger.debug(f"✅ Tika request completed in {attempt_time:.2f}s (attempt {attempt + 1})")
                            last_error = None
                            break
                        except requests.exceptions.ConnectionError as e:
                            last_error = e
                            if attempt < 2:
                                wait = 3 * (attempt + 1)
                                logger.warning(f"🔌 Tika connection error (attempt {attempt + 1}/3), retry in {wait}s... Error: {e}")
                                time.sleep(wait)
                            else:
                                logger.error(f"🔌 Tika connection error after 3 attempts: {e}")
                                # Intentar reiniciar Tika (Docker si es externo, proceso local si no)
                                with self._tika_restart_lock:
                                    if self.is_external_tika:
                                        logger.warning("🔄 Attempting to restart external Tika container...")
                                        self._restart_external_tika()
                                    else:
                                        logger.warning("🔄 Restarting local Tika process...")
                                        self._aggressive_kill_tika()
                                        self._start_tika()
                                response = None
                                break
                        except requests.exceptions.ReadTimeout as e:
                            last_error = e
                            attempt_time = time_module.time() - attempt_start
                            logger.error(f"⏱️ Tika read timeout after {attempt_time:.2f}s (attempt {attempt + 1}/3): {e}")
                            if attempt < 2:
                                wait = 5 * (attempt + 1)
                                logger.warning(f"Retrying in {wait}s...")
                                time.sleep(wait)
                            else:
                                logger.error(f"Tika timeouts after 3 attempts - file may be too large/complex")
                                response = None
                                break
                    if last_error and response is None:
                        # Tras reiniciar Tika, dejamos que el fallback Tesseract intente este archivo
                        pass
                    elif last_error:
                        raise last_error
                    elif response is not None:
                        response.encoding = 'utf-8'
                        total_time = time_module.time() - start_time
                        logger.debug(f"Tika response status: {response.status_code} (total time: {total_time:.2f}s)")
                        logger.debug(f"Tika response encoding: {response.encoding}")
                        logger.debug(f"Tika response length: {len(response.text)} chars")
                        if response.status_code == 200:
                            text = self._extract_text_from_tika_xml(response.text)
                            if text and len(text.strip()) > 100:
                                logger.info(f"✅ {len(text)} chars extracted (Tika)")
                                return text
                except requests.exceptions.Timeout:
                    logger.error(f"⏱️ Tika timeout after 600s - file may be too large/complex")
                    logger.warning("Falling back to Tesseract...")
                except requests.exceptions.ConnectionError:
                    raise
                except Exception as e:
                    logger.error(f"Tika request error: {type(e).__name__}: {str(e)}")

            # 🔧 FALLBACK TO TESSERACT if Tika didn't extract enough
            logger.warning("⚠️  Tika extraction insufficient, trying Tesseract...")
            tesseract_text = self._extract_with_tesseract(file_path)
            if tesseract_text and len(tesseract_text.strip()) > 0:
                logger.info(f"✅ {len(tesseract_text)} chars (Tesseract fallback)")
                return tesseract_text

            logger.warning("⚠️  No extraction worked")
            return ""
        except Exception as e:
            logger.error(f"Extract error: {str(e)}")
            return ""
    
    def _extract_text_from_tika_xml(self, xml_text: str) -> str:
        try:
            logger.info(f"XML length: {len(xml_text)} chars")
            
            if xml_text.startswith('\ufeff'):
                xml_text = xml_text[1:]
            
            xml_text = re.sub(r'&#0;', '', xml_text)
            xml_text = re.sub(r'&#[0-9]+;', '', xml_text)
            
            root = ET.fromstring(xml_text)
            logger.info(f"XML parsed successfully")
            
            ns = {'xhtml': 'http://www.w3.org/1999/xhtml'}
            
            body = root.find('.//xhtml:body', ns)
            if body is not None:
                text = ''.join(body.itertext()).strip()
                logger.info(f"Found xhtml:body with {len(text)} chars")
                if text:
                    return text
            
            body = root.find('.//body')
            if body is not None:
                text = ''.join(body.itertext()).strip()
                logger.info(f"Found body with {len(text)} chars")
                if text:
                    return text
            
            text = ''.join(root.itertext()).strip()
            logger.info(f"Got all text: {len(text)} chars")
            return text if text else ""
            
        except Exception as e:
            logger.error(f"XML error: {type(e).__name__}: {str(e)}")
            return ""
    
    def _extract_with_tesseract(self, file_path: str) -> str:
        """Fallback: extract text using Tesseract directly"""
        try:
            import pytesseract
            from pdf2image import convert_from_path

            logger.info(f"🔍 Tesseract: converting PDF to images...")
            images = convert_from_path(file_path)
            logger.info(f"📄 {len(images)} pages converted")

            text = ""
            for i, img in enumerate(images):
                logger.info(f"  OCR page {i+1}/{len(images)}...")
                page_text = pytesseract.image_to_string(img, lang='ita+eng')
                text += page_text + "\n"

            logger.info(f"✅ Tesseract extracted {len(text)} chars")
            logger.info(f"📋 TESSERACT TEXT:\n{text[:1000]}")
            return text

        except ImportError as e:
            logger.error(f"❌ Missing module: {e}")
            return ""
        except Exception as e:
            logger.error(f"❌ Tesseract failed: {type(e).__name__}: {str(e)}")
            return ""


def get_ocr_service():
    """
    Factory para servicio OCR
    
    Soporta múltiples engines via variable de entorno OCR_ENGINE:
    - 'tika' (default): Usa Apache Tika (legacy, fallback)
    - 'ocrmypdf': Usa OCRmyPDF + Tesseract (recomendado)
    
    Returns:
        OCRService instance (Tika o OCRmyPDF)
    
    Example:
        >>> ocr = get_ocr_service()
        >>> text = ocr.extract_text('/path/to/document.pdf')
    """
    engine = os.getenv("OCR_ENGINE", "ocrmypdf").lower()
    
    if engine == "ocrmypdf":
        try:
            from ocr_service_ocrmypdf import OCRServiceOCRmyPDF
            logger.info("🚀 Using OCRmyPDF engine (high performance)")
            return OCRServiceOCRmyPDF()
        except Exception as e:
            logger.error(f"❌ Failed to load OCRmyPDF engine: {e}")
            logger.error("❌ OCRmyPDF is required. Tika fallback disabled. Please ensure OCR service is running.")
            raise RuntimeError(f"OCRmyPDF engine failed to initialize: {e}") from e
    
    elif engine == "tika":
        logger.info("🚀 Using Tika engine (legacy)")
        return OCRService()
    
    else:
        logger.warning(f"⚠️ Unknown OCR engine '{engine}', using Tika as default")
        return OCRService()
