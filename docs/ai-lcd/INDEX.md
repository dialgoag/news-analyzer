# 📚 Índice de Documentación AI-LCD

> Guía rápida para navegar la documentación consolidada del NewsAnalyzer-RAG

**Última actualización**: 2026-03-30  
**Documentación consolidada**: ✅ Yes

**Principio**: Evitar redundancia — cada tema tiene una **fuente única**. Ej.: variables de entorno → `ENVIRONMENT_CONFIGURATION.md`; pipeline stages → `PIPELINE_GLOSARIO.md`.

---

## 🎯 Comienza Aquí

### ⭐ NUEVO SISTEMA DE PETICIONES (Comienza AQUÍ primero)
1. **00_COMIENZA_AQUI_NUEVO_SISTEMA.md** - Overview visual de 4 documentos nuevos (5 min read)
2. **COMO_USAR_WORKFLOW.md** - Guía paso a paso con ejemplo completo (10 min read)
3. **SISTEMA_DE_PETICIONES_GUIA.md** - Casos prácticos adicionales (5 min read)

### Para nuevos desarrolladores
1. **README.md** - Overview del proyecto (5 min read)
2. **CONSOLIDATED_STATUS.md** - Status actual completo (10 min read)
3. **PLAN_AND_NEXT_STEP.md** - Qué viene después (5 min read)

### Para retomar trabajo
1. **CONSOLIDATED_STATUS.md** - ¿Qué se ha hecho?
2. **SESSION_LOG.md** - ¿Qué decisiones se tomaron?
3. **EVENT_DRIVEN_ARCHITECTURE.md** - ¿Cómo funciona el sistema?

### Para procesar nueva petición
1. **REQUESTS_REGISTRY.md** - ¿Se pidió esto antes?
2. **request-workflow.mdc** - Cómo procesar (6 pasos + Paso 1.5)
3. **COMO_USAR_WORKFLOW.md** - Ejemplo paso a paso

### Para problemas
1. **03-operations/TROUBLESHOOTING_GUIDE.md** - Problemas comunes
2. **CONSOLIDATED_STATUS.md § Fixes Aplicados** - Bugs arreglados recientemente

---

## 📖 Documentos Principales (Consolidados)

### ✅ Status y Planificación
| Documento | Propósito | Última actualización |
|-----------|----------|---------------------|
| **README.md** | Overview ejecutivo | 2026-03-04 |
| **CONSOLIDATED_STATUS.md** | Status definitivo integrado | 2026-03-27 |
| **PLAN_AND_NEXT_STEP.md** | Plan + timeline + checklist | 2026-03-27 |
| **SESSION_LOG.md** | Decisiones entre sesiones | 2026-03-27 |
| **REQUESTS_REGISTRY.md** | Rastreo de peticiones + contradicciones | 2026-03-27 |
| **PENDING_BACKLOG.md** | Pendientes con prioridad y dependencias | 2026-03-17 |
| **00_COMIENZA_AQUI_NUEVO_SISTEMA.md** | Overview visual del nuevo sistema | 2026-03-05 ✨ NUEVO |
| **COMO_USAR_WORKFLOW.md** | Guía paso a paso con ejemplo completo | 2026-03-05 ✨ NUEVO |
| **SISTEMA_DE_PETICIONES_GUIA.md** | Cómo usar nuevo sistema de peticiones | 2026-03-05 ✨ NUEVO |

### ✅ Arquitectura y Design
| Documento | Propósito | Ubicación |
|-----------|----------|----------|
| **EVENT_DRIVEN_ARCHITECTURE.md** | Blueprint: database semaphores | `ai-lcd/` |
| **ARCHITECTURE_DETAILED.md** | Stack completo | `02-construction/` |
| **DATA_FLOWS.md** | Upload → OCR → RAG → Response | `02-construction/` |
| **SPIKE_REQ021_LOCAL_LLM_INSIGHTS_QUALITY.md** | Spike: LLM local vs API para insights (calidad); REQ-021 | `02-construction/` |
| **MIGRATIONS_SYSTEM.md** | Yoyo, migraciones 001–015 | `02-construction/` |

### ✅ Operaciones
| Documento | Propósito | Ubicación |
|-----------|----------|----------|
| **DEPLOYMENT_GUIDE.md** | Despliegue paso a paso | `03-operations/` |
| **ENVIRONMENT_CONFIGURATION.md** | Variables de entorno | `03-operations/` |
| **TROUBLESHOOTING_GUIDE.md** | Problemas y soluciones | `03-operations/` |
| **REPROCESSING.md** | Reprocesar documentos preservando insights | `03-operations/` |
| **ORDERLY_SHUTDOWN_AND_REBUILD.md** | Shutdown API + rebuild backend/frontend | `03-operations/` |
| **LOCAL_LLM_VS_OPENAI_INSIGHTS.md** | Comparación manual curl Ollama/OpenAI (complemento REQ-021) | `03-operations/` |
| **DOCKER.md** | Docker Compose unificado (CPU/GPU) | `app/docs/` |
| **PERFORMANCE_OPTIMIZATION.md** | Optimizaciones | `03-operations/` |

---

## 🔍 Búsqueda Rápida

### ¿Dónde está...?

**...el status actual?**
→ `CONSOLIDATED_STATUS.md` (versión definitiva, 2026-03-27)

**...la arquitectura event-driven?**
→ `EVENT_DRIVEN_ARCHITECTURE.md` (technical blueprint completo)

**...cómo hacer deploy?**
→ `03-operations/DEPLOYMENT_GUIDE.md`

**...Docker CPU vs GPU?**
→ `app/docs/DOCKER.md`

**...los bugs arreglados hoy?**
→ `CONSOLIDATED_STATUS.md § 🔧 FIXES APLICADOS HOY`

**...cómo reprocesar un documento sin perder insights?**
→ `03-operations/REPROCESSING.md`

**...el próximo paso?**
→ `PLAN_AND_NEXT_STEP.md § Próximos Pasos`

**...mejoras pendientes / backlog?**
→ `PENDING_BACKLOG.md` (fuente única de pendientes técnicos)
→ `REQUESTS_REGISTRY.md` (peticiones usuario, ej. REQ-014)

**...spike LLM local vs API para insights?**
→ `02-construction/SPIKE_REQ021_LOCAL_LLM_INSIGHTS_QUALITY.md` (REQ-021); script `app/benchmark/compare_insights_models.py`

**...cómo verificar deduplicación?**
→ `CONSOLIDATED_STATUS.md § 🔍 VERIFICACIÓN PRÓXIMA`

**...las decisiones que se tomaron?**
→ `SESSION_LOG.md` (historial de decisiones)

**...un problema específico?**
→ `03-operations/TROUBLESHOOTING_GUIDE.md`

**...variables de entorno / workers / límites?**
→ `03-operations/ENVIRONMENT_CONFIGURATION.md` (fuente única)

**...incoherencias dashboard (totales, workers vs pipeline)?**
→ `02-construction/DASHBOARD_ANALYSIS_KNOWN_ISSUES.md`

**...migraciones (Yoyo, 014, indexed_in_qdrant_at)?**
→ `02-construction/MIGRATIONS_SYSTEM.md`

---

## 📊 Estado de Documentación

### Documentos Consolidados (Versión Definitiva)
- ✅ **README.md** - Overview
- ✅ **CONSOLIDATED_STATUS.md** - Status completo integrado (NUEVO 2026-03-04)
- ✅ **PLAN_AND_NEXT_STEP.md** - Plan + checklist
- ✅ **SESSION_LOG.md** - Decisiones
- ✅ **EVENT_DRIVEN_ARCHITECTURE.md** - Technical blueprint

### Documentos Legados (Por consolidar)
- ⚠️ **STATUS_AND_HISTORY.md** - Reemplazado por CONSOLIDATED_STATUS.md
- ⚠️ **IMPLEMENTATION_CHECKLIST.md** - Integrado en STATUS
- ⚠️ **COMPLETE_ROADMAP.md** - Integrado en PLAN

### Documentos de Referencia (Subfolderes)
- ✅ `01-inception/` - Business requirements, use cases, stakeholders
- ✅ `02-construction/` - Arquitectura, code org, data flows
- ✅ `03-operations/` - Deploy, config, troubleshooting, optimization

---

## 🚀 Quick Links

### Para empezar rápido
```bash
# Ver estado actual
cat docs/ai-lcd/CONSOLIDATED_STATUS.md

# Ver próximos pasos
cat docs/ai-lcd/PLAN_AND_NEXT_STEP.md

# Hacer deploy
cd app/
docker compose up -d
```

### Para verificar código
```bash
# Ver si algo está donde debería
grep "task_id" backend/app.py  # Debería mostrar "document_id" ahora
grep "asyncio.run_coroutine_threadsafe" backend/app.py  # Debería encontrarse
```

### Para ver logs
```bash
# Backend logs
docker-compose logs backend -f

# Verificación automática
docker-compose exec backend python3 /app/verify_deduplication.py
```

---

## 📈 Cambios Recientes

### 2026-03-04 (Hoy)
✨ **Documentación Consolidada + Docker Optimization + Bug Fixes**

- ✅ Creado `CONSOLIDATED_STATUS.md` (versión definitiva integrada)
- ✅ Arreglados 3 SQL errors (task_id, id, async dispatch)
- ✅ Implementado Docker base image (3-5x más rápido)
- ✅ Preparado script de verificación de deduplicación

### 2026-03-03
✨ **Event-Driven Architecture + Dashboard UI**

- ✅ Processing queue + worker_tasks tables
- ✅ OCR/Insights event-driven dispatchers
- ✅ Dashboard 2-column layout + i18n
- ✅ Recovery mechanism (crashed workers)

### 2026-03-02
✨ **Project Inception**

- ✅ Project setup + structure
- ✅ Initial documentation framework
- ✅ Basic RAG pipeline

---

## 💡 Recomendaciones

### Primera sesión
1. Leer `README.md` (5 min)
2. Leer `CONSOLIDATED_STATUS.md` (10 min)
3. Leer `EVENT_DRIVEN_ARCHITECTURE.md` (15 min)
4. Hacer deploy: `docker-compose up -d`
5. Ejecutar verificación: `/app/verify_deduplication.py`

### Retomar trabajo
1. Actualizar `CONSOLIDATED_STATUS.md` con cambios del día
2. Documentar decisiones en `SESSION_LOG.md`
3. Actualizar `PLAN_AND_NEXT_STEP.md` con progreso

### Agregar feature nueva
1. Revisar `PLAN_AND_NEXT_STEP.md § Próximos Pasos`
2. Leer `EVENT_DRIVEN_ARCHITECTURE.md` si es cola/worker
3. Actualizar `CONSOLIDATED_STATUS.md` cuando esté hecho
4. Documentar en `SESSION_LOG.md`

---

## 🎯 Status de Implementación

| Feature | Status | Donde |
|---------|--------|-------|
| Event-Driven OCR | ✅ Completo | `EVENT_DRIVEN_ARCHITECTURE.md` |
| Event-Driven Insights | ✅ Completo | `EVENT_DRIVEN_ARCHITECTURE.md` |
| Dashboard UI | ✅ Completo | `CONSOLIDATED_STATUS.md § Frontend` |
| Docker Optimization | ✅ Completo | `CONSOLIDATED_STATUS.md § Docker` |
| Bug Fixes | ✅ Completo | `CONSOLIDATED_STATUS.md § Fixes` |
| Deduplication Verify | 🔄 Auto | `CONSOLIDATED_STATUS.md § Verification` |
| PostgreSQL Migration | ✅ Completo | `CONSOLIDATED_STATUS.md § Fix #22` |
| OCRmyPDF Migration | ✅ Completo | `CONSOLIDATED_STATUS.md § Fix #27` |
| Frontend Resiliente | ✅ Completo | `CONSOLIDATED_STATUS.md § Fix #23` |
| Pipeline States | ✅ Completo | `CONSOLIDATED_STATUS.md § Fix #43` |
| Dashboard Paneles | ✅ Completo | `CONSOLIDATED_STATUS.md § Fixes #36-40` |
| Frontend Modular | ✅ Recuperado | 17 JS/JSX + 11 CSS desde source map |
| Docker Unificado | ✅ Completo | `CONSOLIDATED_STATUS.md § Fix #56` |
| Startup Recovery | ✅ Completo | `CONSOLIDATED_STATUS.md § Fix #52` |

---

**Documentación consolidada y actualizada a 2026-03-27**
