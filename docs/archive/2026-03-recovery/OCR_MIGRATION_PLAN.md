# 🚀 Migración OCR: Tika → OCRmyPDF + Tesseract

**Fecha**: 2026-03-13  
**Versión**: v3.0  
**Estado**: 🔄 EN EJECUCIÓN

---

## 📊 Motivación

### Problemas Actuales con Tika:
- **Performance bajo**: ~60s por PDF (promedio)
- **Saturación**: Solo 3 workers concurrentes sin crashear
- **Alto consumo recursos**: 198% CPU, 940MB RAM
- **Success rate**: 40% (154/385 tareas)
- **Throughput limitado**: ~3 PDFs/minuto

### Beneficios Esperados con OCRmyPDF:
- **Performance**: 3-5x más rápido (~20s por PDF)
- **Escalabilidad**: 8-10 workers concurrentes
- **Menor consumo**: ~200MB RAM por worker
- **Success rate**: >95% esperado
- **Throughput**: ~30 PDFs/minuto (+900%)

---

## 🏗️ Arquitectura Propuesta

### Componente 1: Nuevo Servicio Docker `ocr-service`

```yaml
# docker-compose.yml
ocr-service:
  build:
    context: ./ocr-service
    dockerfile: Dockerfile
  container_name: rag-ocr-service
  volumes:
    - ./temp:/tmp
    - ./uploads:/uploads:ro
  ports:
    - "127.0.0.1:9999:9999"
  networks:
    - rag-network
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9999/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 20s
  deploy:
    resources:
      limits:
        cpus: '4.0'
        memory: 4G
      reservations:
        memory: 2G
  environment:
    - TESSERACT_LANG=spa+eng
    - OCR_THREADS=4
```

### Componente 2: API REST para OCRmyPDF

```python
# ocr-service/app.py
from fastapi import FastAPI, UploadFile, File
from pathlib import Path
import ocrmypdf
import tempfile

app = FastAPI()

@app.post("/extract")
async def extract_text(file: UploadFile = File(...)):
    """
    Extrae texto de PDF usando OCRmyPDF + Tesseract
    Compatible con interfaz actual de Tika
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_in:
        content = await file.read()
        tmp_in.write(content)
        tmp_in_path = tmp_in.name
    
    try:
        # OCRmyPDF procesa y extrae texto
        result = ocrmypdf.ocr(
            tmp_in_path,
            '/dev/null',  # No guardamos output PDF
            language='spa+eng',
            output_type='pdfa',
            deskew=True,
            clean=True,
            force_ocr=False,  # Solo OCR si no hay texto
            skip_text=False,
            redo_ocr=False,
            return_text=True
        )
        
        return {"text": result, "status": "success"}
    finally:
        Path(tmp_in_path).unlink(missing_ok=True)

@app.get("/health")
async def health():
    return {"status": "healthy", "engine": "ocrmypdf+tesseract"}
```

### Componente 3: Dockerfile Optimizado

```dockerfile
# ocr-service/Dockerfile
FROM python:3.11-slim

# Instalar dependencias del sistema
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

# Instalar OCRmyPDF y dependencias Python
RUN pip install --no-cache-dir \
    ocrmypdf==15.4.4 \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    python-multipart==0.0.6

WORKDIR /app
COPY app.py /app/

EXPOSE 9999

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9999", "--workers", "4"]
```

### Componente 4: Adaptador en Backend

```python
# backend/ocr_service_ocrmypdf.py
import requests
from pathlib import Path

class OCRServiceOCRmyPDF:
    def __init__(self):
        self.ocr_host = os.getenv("OCR_SERVICE_HOST", "ocr-service")
        self.ocr_port = os.getenv("OCR_SERVICE_PORT", "9999")
        self.ocr_url = f"http://{self.ocr_host}:{self.ocr_port}"
        logger.info(f"🔗 Using OCRmyPDF service at {self.ocr_url}")
    
    def extract_text(self, pdf_path: str, timeout: int = 120) -> str:
        """
        Extrae texto de PDF usando OCRmyPDF service
        Interfaz compatible con Tika original
        """
        with open(pdf_path, 'rb') as f:
            files = {'file': (Path(pdf_path).name, f, 'application/pdf')}
            response = requests.post(
                f"{self.ocr_url}/extract",
                files=files,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()['text']
```

### Componente 5: Configuración Dual (Tika + OCRmyPDF)

```python
# backend/ocr_service.py (modificado)
def get_ocr_service():
    """
    Factory para servicio OCR
    Soporta: tika, ocrmypdf
    """
    engine = os.getenv("OCR_ENGINE", "tika").lower()
    
    if engine == "ocrmypdf":
        from ocr_service_ocrmypdf import OCRServiceOCRmyPDF
        return OCRServiceOCRmyPDF()
    elif engine == "tika":
        return OCRService()  # Tika original (fallback)
    else:
        raise ValueError(f"Unknown OCR engine: {engine}")
```

---

## 📋 Plan de Implementación

### FASE 1: Setup Nuevo Servicio (1-2 horas) ✅ SIGUIENTE

**Tareas**:
1. [ ] Crear directorio `ocr-service/`
2. [ ] Crear `Dockerfile` con OCRmyPDF + Tesseract
3. [ ] Crear `app.py` con API REST compatible
4. [ ] Crear `requirements.txt`
5. [ ] Actualizar `docker-compose.yml` con nuevo servicio
6. [ ] Build y verificar health check

**Verificación**:
```bash
docker-compose build ocr-service
docker-compose up ocr-service
curl http://localhost:9999/health
# Esperado: {"status": "healthy", "engine": "ocrmypdf+tesseract"}
```

### FASE 2: Integración Backend (1-2 horas)

**Tareas**:
1. [ ] Crear `backend/ocr_service_ocrmypdf.py`
2. [ ] Modificar `backend/ocr_service.py` (factory pattern)
3. [ ] Agregar variables de entorno:
   - `OCR_ENGINE=ocrmypdf|tika`
   - `OCR_SERVICE_HOST=ocr-service`
   - `OCR_SERVICE_PORT=9999`
4. [ ] Testing con 5-10 PDFs de muestra

**Verificación**:
```bash
# Testing con Tika (fallback)
OCR_ENGINE=tika docker-compose up backend

# Testing con OCRmyPDF (nuevo)
OCR_ENGINE=ocrmypdf docker-compose up backend
```

### FASE 3: Testing Comparativo (1 hora)

**Métricas a medir**:
- [ ] Tiempo promedio por PDF (Tika vs OCRmyPDF)
- [ ] Memoria consumida (peak)
- [ ] CPU utilizado
- [ ] Calidad del texto extraído (muestra aleatoria)
- [ ] Workers concurrentes máximos sin errores

**Script de testing**:
```bash
# Testing con 20 PDFs
for i in {1..20}; do
    time curl -X POST \
        -F "file=@test_pdf_$i.pdf" \
        http://localhost:9999/extract
done
```

### FASE 4: Migration Completa (30 min)

**Tareas**:
1. [ ] Cambiar default: `OCR_ENGINE=ocrmypdf`
2. [ ] Aumentar `OCR_PARALLEL_WORKERS=8` (de 3)
3. [ ] Reiniciar sistema completo
4. [ ] Monitorear logs y performance
5. [ ] Procesar batch de 50 PDFs de prueba

**Rollback** (si hay problemas):
```bash
# Volver a Tika inmediatamente
docker-compose down
OCR_ENGINE=tika docker-compose up -d
```

### FASE 5: Deprecación Tika (Futuro)

**Cuando OCRmyPDF esté 100% estable**:
1. [ ] Remover servicio `tika` de docker-compose
2. [ ] Eliminar código Tika legacy
3. [ ] Actualizar documentación
4. [ ] Marcar REQ-001 y REQ-002 como SUPERSEDIDAS

---

## 🎯 Métricas Esperadas

### Baseline (Tika actual):
```
Workers concurrentes: 3
Tiempo/PDF: ~60s
Memoria/worker: ~300MB
Throughput: 3 PDFs/min
Success rate: 40%
```

### Target (OCRmyPDF):
```
Workers concurrentes: 8-10
Tiempo/PDF: ~20s
Memoria/worker: ~200MB
Throughput: 24-30 PDFs/min (+800%)
Success rate: >95%
```

---

## 🚨 Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| OCRmyPDF más lento que Tika | Bajo | Alto | Testing comparativo FASE 3 |
| Problemas de encoding (español) | Medio | Medio | Configurar `TESSERACT_LANG=spa+eng` |
| API incompatible | Bajo | Alto | Mantener interfaz compatible |
| Workers crashean | Medio | Alto | Mantener Tika como fallback |
| Migración rompe sistema | Bajo | Crítico | Configuración dual + rollback rápido |

---

## ✅ Checklist de Verificación

### Pre-implementación:
- [x] Análisis de performance actual
- [x] Decisión: OCRmyPDF vs otras alternativas
- [x] Aprobación del usuario
- [ ] Backup de configuración actual
- [ ] Documentación creada

### Post-FASE 1:
- [ ] Servicio OCR corriendo
- [ ] Health check funcionando
- [ ] API REST respondiendo

### Post-FASE 2:
- [ ] Backend se conecta a OCRmyPDF
- [ ] Testing con 5 PDFs exitoso
- [ ] Sin errores en logs

### Post-FASE 3:
- [ ] Métricas comparativas documentadas
- [ ] Decisión: continuar o rollback
- [ ] Performance confirmado >3x mejora

### Post-FASE 4:
- [ ] OCRmyPDF como default
- [ ] 8-10 workers concurrentes
- [ ] Sistema estable
- [ ] Tika disponible como fallback

---

## 📚 Referencias

- **OCRmyPDF Docs**: https://ocrmypdf.readthedocs.io/
- **Tesseract**: https://github.com/tesseract-ocr/tesseract
- **Request original**: REQ-012 (REQUESTS_REGISTRY.md)
- **Sesión**: Sesión 17 (SESSION_LOG.md)

---

**Última actualización**: 2026-03-13  
**Responsable**: AI Agent  
**Estado**: 🔄 FASE 1 INICIANDO
