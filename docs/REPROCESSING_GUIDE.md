# 🔄 Reprocesamiento de Documentos - Guía de Uso

## 📋 Resumen de Funcionalidad

Esta funcionalidad permite reprocesar documentos completos (OCR + Chunking + Indexing) mientras **preserva** noticias e insights existentes.

## ✨ Características Principales

### ✅ Se Preserva (NO se elimina):
- **Noticias existentes** (`news_items`) - comparadas por `text_hash`
- **Insights generados** (`news_item_insights`)
- **Datos históricos valiosos**

### 🔄 Se Reprocesa:
- **Texto OCR** - se extrae nuevamente del PDF original
- **Segmentación de noticias** - se ejecuta el algoritmo de detección
- **Chunks vectorizados** - se re-indexan en Qdrant con nuevos vectores

### 🧠 Lógica Inteligente:
1. **Deduplicación por Hash**: Cada noticia tiene un `text_hash` único
2. **Reutilización de IDs**: Si una noticia existe (mismo hash), se reutiliza su ID
3. **Solo Nuevas**: Solo se agregan noticias con hash diferente
4. **Insights Selectivos**: Solo se generan insights para noticias nuevas

## 🎯 Caso de Uso: "28-12-26-El Mundo.pdf"

### Problema Detectado:
```
📄 Documento: 28-12-26-El Mundo.pdf
📊 Estado actual: indexed
📰 Noticias detectadas: 2
   1. VENTANILLA ÚNICA
   2. CD NUMANCIA. Ángel Rodríguez confía

❌ PROBLEMA: Un periódico típico tiene 30-80 noticias, no solo 2
```

### Solución: Reprocesar con Preservación

1. **Ir al Dashboard** → http://localhost:3000
2. **Buscar el documento** en la tabla
3. **Click en 🔄 Requeue**
4. **Confirmar** la operación

### Qué Sucederá:

```
🔄 Reprocesamiento Iniciado
├─ 📄 OCR: Extraer texto completo del PDF
├─ 🔍 Segmentación: Detectar TODAS las noticias (esperamos 30-80)
├─ 🧬 Comparación por Hash:
│  ├─ Noticia 1 (VENTANILLA ÚNICA) → Hash existe ✓ Reutilizar ID
│  ├─ Noticia 2 (CD NUMANCIA...) → Hash existe ✓ Reutilizar ID
│  ├─ Noticia 3 (Nueva) → Hash no existe → Crear nueva ✨
│  ├─ Noticia 4 (Nueva) → Hash no existe → Crear nueva ✨
│  └─ ... (28-78 noticias más nuevas) → Crear nuevas ✨
├─ 📦 Chunking: Dividir texto en chunks
├─ 🔢 Indexación: Re-indexar en Qdrant
└─ 💡 Insights: Solo para noticias NUEVAS (las 2 existentes se preservan)

✅ Resultado:
   📰 2 noticias preservadas (con sus insights)
   ✨ 28-78 noticias nuevas agregadas
   💾 Datos históricos intactos
```

## 🔧 Comandos de Despliegue

### 1. Reconstruir y Reiniciar Servicios

```bash
cd app
chmod +x deploy.sh
./deploy.sh
```

### 2. Iniciar Tika Manualmente (si es necesario)

```bash
cd app
chmod +x start-tika.sh
./start-tika.sh
```

O directamente:
```bash
docker compose exec backend bash -c 'java -jar /opt/tika-server.jar --host 0.0.0.0 --port 9998 > /tmp/tika.log 2>&1 &'
```

## 📊 Verificación

### Verificar Estado de Servicios:
```bash
docker compose ps
```

### Verificar Logs del Backend:
```bash
docker compose logs backend --tail=50
```

### Verificar Tika:
```bash
docker compose exec backend ps aux | grep tika
docker compose exec backend netstat -tln | grep 9998
```

### Verificar Columna OCR en BD:
```bash
docker compose exec backend python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/rag_enterprise.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(document_status)')
for row in cursor.fetchall():
    print(f'{row[1]} ({row[2]})')
conn.close()
"
```

## 🔍 Endpoint de Diagnóstico

Una vez que el texto OCR esté almacenado, puedes usar el botón **🔬** en la tabla para ver el diagnóstico de segmentación:

```
GET /api/documents/{document_id}/segmentation-diagnostic
```

Esto te mostrará:
- Estadísticas de OCR (caracteres, líneas)
- Noticias detectadas por el algoritmo
- Títulos candidatos encontrados
- Comparación con noticias almacenadas
- Preview del texto OCR

## 📁 Archivos Modificados

### Backend:
- ✅ `app.py` - Endpoint `/requeue`, lógica de deduplicación
- ✅ `database.py` - Métodos `store_ocr_text()`, `get()`
- ✅ `migrations/013_add_ocr_text_column.py` - Migración de BD

### Frontend:
- ✅ `App.jsx` - Función `requeueDocument()`, botón de requeue

### Scripts:
- ✅ `deploy.sh` - Script de despliegue
- ✅ `start-tika.sh` - Script para iniciar Tika

## ⚠️ Notas Importantes

1. **Preservación de Datos**: Los insights y noticias NUNCA se eliminan durante el reprocesamiento
2. **Comparación por Hash**: La deduplicación usa SHA-256 del texto normalizado
3. **Tika Requerido**: El servicio Tika debe estar corriendo para el OCR
4. **Workers Automáticos**: El sistema procesará automáticamente los documentos en cola
5. **Tiempo de Procesamiento**: Depende del tamaño del PDF (típicamente 30-120 segundos)

## 🎯 Próximos Pasos

Después del despliegue:

1. ✅ Verificar que los servicios estén corriendo
2. ✅ Verificar que Tika esté activo
3. ✅ Probar el botón 🔄 Requeue en "28-12-26-El Mundo.pdf"
4. ✅ Monitorear los logs del backend durante el procesamiento
5. ✅ Verificar que se detecten más de 2 noticias
6. ✅ Usar el botón 🔬 para ver el diagnóstico de segmentación
7. ✅ Confirmar que los 2 insights originales se preservaron

## 📞 Troubleshooting

### Tika no inicia:
```bash
# Ver logs de Tika
docker compose exec backend cat /tmp/tika.log

# Reiniciar Tika
./start-tika.sh
```

### Servicios no responden:
```bash
# Ver logs completos
docker compose logs --tail=100

# Reiniciar todo
docker compose down
docker compose up -d --build
```

### Base de datos no migró:
```bash
# Verificar migraciones aplicadas
docker compose exec backend python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/rag_enterprise.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM _yoyo_migration ORDER BY id DESC LIMIT 5')
for row in cursor.fetchall():
    print(row)
conn.close()
"
```
