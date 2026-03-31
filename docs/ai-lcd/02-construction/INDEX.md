# 📚 Índice de Documentación: Construcción (02-construction)

> **Propósito**: Referencia rápida a todos los documentos técnicos del proyecto.
>
> **Última actualización**: 2026-03-31

---

## 🏗️ Arquitectura

### Arquitectura Hexagonal + DDD + Event-Driven

- **[HEXAGONAL_ARCHITECTURE.md](./HEXAGONAL_ARCHITECTURE.md)**
  - 📖 Descripción: Arquitectura adoptada para el backend (Hexagonal + DDD + Event-Driven)
  - 🎯 Cuándo leer: Para entender la estructura del backend refactorizado
  - 📌 Conceptos clave: Ports & Adapters, Domain Events, CQRS, Repository Pattern
  - ✅ Estado: Documento vivo - se actualiza durante REQ-021

- **[ARCHITECTURE_DETAILED.md](./ARCHITECTURE_DETAILED.md)**
  - 📖 Descripción: Arquitectura detallada del sistema completo (legacy + nuevo)
  - 🎯 Cuándo leer: Para overview técnico del sistema end-to-end
  - 📌 Conceptos clave: Componentes principales, flujo de datos, tecnologías

---

## 🤖 Integración LLM: LangChain + LangGraph + LangMem

### Documentación Central de LangChain

- **[LANGCHAIN_INTEGRATION.md](./LANGCHAIN_INTEGRATION.md)** ⭐ **NUEVO**
  - 📖 Descripción: Cómo LangChain, LangGraph y LangMem se integran en NewsAnalyzer
  - 🎯 Cuándo leer: Para entender cómo funciona la generación de insights con LLMs
  - 📌 Conceptos clave:
    - Pipeline de 2 pasos (ExtractionChain → AnalysisChain)
    - LangGraph workflows con estado y validación
    - LangMem para caché de embeddings e insights
    - Providers intercambiables (OpenAI, Ollama, Perplexity)
  - 🔗 Relacionado: MIGRATION_GUIDE.md, HEXAGONAL_ARCHITECTURE.md

- **[LANGCHAIN_INTEGRATION_DIAGRAM.md](./LANGCHAIN_INTEGRATION_DIAGRAM.md)** ⭐ **NUEVO**
  - 📖 Descripción: Diagramas visuales completos del flujo LangChain
  - 🎯 Cuándo leer: Para visualizar cómo interactúan todos los componentes
  - 📌 Incluye:
    - Flujo end-to-end (Worker → LangGraph → Chains → Database)
    - Vista de componentes (Hexagonal + LangChain)
    - Diagramas de secuencia (interacción entre componentes)
    - Comparación Antes vs Después (monolítico vs hexagonal)
  - 🔗 Relacionado: LANGCHAIN_INTEGRATION.md

### Guía de Migración

- **[MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)** ⭐ **NUEVO**
  - 📖 Descripción: Mapeo detallado de cómo migrar código monolítico a Hexagonal + LangChain
  - 🎯 Cuándo leer: Para implementar el refactor paso a paso
  - 📌 Incluye:
    - Mapeo: Dónde va cada pieza de app.py
    - Ejemplos de código: Antes vs Después
    - Testing: Cómo testear con mocks
    - Checklist de migración por fase
    - Ejemplo completo: Migrar `_insights_worker_task`
  - 🔗 Relacionado: BACKEND_REFACTOR_TASK.md, HEXAGONAL_ARCHITECTURE.md

### Otros LLM Docs

- **[OPENAI_INTEGRATION.md](./OPENAI_INTEGRATION.md)**
  - 📖 Descripción: Integración de OpenAI para embeddings e insights (legacy)
  - 🎯 Cuándo leer: Referencia histórica de la integración OpenAI inicial
  - 📌 Estado: Legacy - reemplazado por LangChain providers

- **[SPIKE_REQ021_LOCAL_LLM_INSIGHTS_QUALITY.md](./SPIKE_REQ021_LOCAL_LLM_INSIGHTS_QUALITY.md)**
  - 📖 Descripción: Benchmark de calidad entre OpenAI y Local LLMs (Ollama)
  - 🎯 Cuándo leer: Para entender trade-offs entre providers
  - 📌 Conceptos clave: Calidad vs costo, latencia, métricas de evaluación

---

## 🔄 Backend Refactor (REQ-021)

- **[BACKEND_REFACTOR_TASK.md](./BACKEND_REFACTOR_TASK.md)**
  - 📖 Descripción: Análisis inicial del monolito app.py y plan de refactor
  - 🎯 Cuándo leer: Para entender motivación y alcance del refactor
  - 📌 Conceptos clave: SOLID violations, target structure, fases de implementación

- **[CODE_ORGANIZATION.md](./CODE_ORGANIZATION.md)**
  - 📖 Descripción: Convenciones de código y organización de archivos
  - 🎯 Cuándo leer: Para seguir estándares del proyecto
  - 📌 Conceptos clave: Naming conventions, folder structure

---

## 🗄️ Base de Datos

### Diseño y Migraciones

- **[DATABASE_DESIGN_REVIEW.md](./DATABASE_DESIGN_REVIEW.md)**
  - 📖 Descripción: Review completo del diseño de base de datos
  - 🎯 Cuándo leer: Para entender el schema actual y decisiones de diseño
  - 📌 Conceptos clave: Tablas principales, relaciones, índices

- **[DATABASE_MIGRATIONS.md](./DATABASE_MIGRATIONS.md)**
  - 📖 Descripción: Cómo funcionan las migraciones de base de datos
  - 🎯 Cuándo leer: Para crear o ejecutar migraciones
  - 📌 Conceptos clave: Sistema de versiones, rollback, best practices

- **[MIGRATIONS_SYSTEM.md](./MIGRATIONS_SYSTEM.md)**
  - 📖 Descripción: Sistema de migraciones automatizado
  - 🎯 Cuándo leer: Para entender cómo se ejecutan migraciones en deploy
  - 📌 Conceptos clave: Auto-run, verificación, logs

- **[PLAN_MIGRACIONES_LIMPIEZA.md](./PLAN_MIGRACIONES_LIMPIEZA.md)**
  - 📖 Descripción: Plan para limpiar y consolidar migraciones legacy
  - 🎯 Cuándo leer: Referencia histórica de limpieza
  - 📌 Estado: Completado en versiones anteriores

---

## 📊 Pipeline y Flujo de Datos

### Pipeline Principal

- **[PIPELINE_FULL_AUDIT.md](./PIPELINE_FULL_AUDIT.md)**
  - 📖 Descripción: Auditoría completa del pipeline OCR + Insights
  - 🎯 Cuándo leer: Para entender el flujo completo de procesamiento
  - 📌 Conceptos clave: PASO 0-6, scheduler, workers, event-driven

- **[INSIGHTS_PIPELINE_REVIEW.md](./INSIGHTS_PIPELINE_REVIEW.md)**
  - 📖 Descripción: Review específico del pipeline de insights
  - 🎯 Cuándo leer: Para debugging o mejoras en insights generation
  - 📌 Conceptos clave: Deduplicación, fallback providers, retry logic

- **[INDEXING_INSIGHTS_GAP_ANALYSIS.md](./INDEXING_INSIGHTS_GAP_ANALYSIS.md)**
  - 📖 Descripción: Análisis de gaps entre indexing e insights
  - 🎯 Cuándo leer: Para entender problemas de sincronización
  - 📌 Conceptos clave: Missing insights, timing issues

---

## 🎨 Frontend y Dashboard

### Dashboard Principal

- **[FRONTEND_DASHBOARD_API.md](./FRONTEND_DASHBOARD_API.md)**
  - 📖 Descripción: Documentación de API para el dashboard React
  - 🎯 Cuándo leer: Para integrar frontend con backend
  - 📌 Conceptos clave: Endpoints, response schema, WebSocket events

- **[DASHBOARD_ANALYSIS_KNOWN_ISSUES.md](./DASHBOARD_ANALYSIS_KNOWN_ISSUES.md)**
  - 📖 Descripción: Issues conocidos del dashboard y análisis
  - 🎯 Cuándo leer: Para debugging o mejoras en UX
  - 📌 Conceptos clave: Performance, UX issues, fixes aplicados

### Visualizaciones

- **[VISUAL_ANALYTICS_GUIDELINES.md](./VISUAL_ANALYTICS_GUIDELINES.md)**
  - 📖 Descripción: Guías para crear visualizaciones efectivas
  - 🎯 Cuándo leer: Para crear nuevos componentes de visualización
  - 📌 Conceptos clave: Best practices, D3.js, React patterns

- **[D3_SANKEY_REFERENCE.md](./D3_SANKEY_REFERENCE.md)**
  - 📖 Descripción: Referencia completa de D3 Sankey diagrams
  - 🎯 Cuándo leer: Para trabajar con gráficos de flujo de pipeline
  - 📌 Conceptos clave: D3 API, layout, customization

---

## 🐛 Fixes y Resoluciones

- **[FIX_095_FILE_NAMING.md](./FIX_095_FILE_NAMING.md)**
  - 📖 Descripción: Fix detallado del issue de naming de archivos (Fix #95)
  - 🎯 Cuándo leer: Referencia histórica de fix importante
  - 📌 Conceptos clave: Duplicados de archivos, normalización de nombres

---

## 🗺️ Mapa de Navegación

### 🚀 Empezando con el proyecto

1. **[ARCHITECTURE_DETAILED.md](./ARCHITECTURE_DETAILED.md)** - Overview general
2. **[HEXAGONAL_ARCHITECTURE.md](./HEXAGONAL_ARCHITECTURE.md)** - Arquitectura del backend
3. **[LANGCHAIN_INTEGRATION.md](./LANGCHAIN_INTEGRATION.md)** - Cómo funcionan los LLMs

### 🔨 Trabajando en el backend

1. **[BACKEND_REFACTOR_TASK.md](./BACKEND_REFACTOR_TASK.md)** - Plan de refactor
2. **[MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)** - Cómo migrar código
3. **[HEXAGONAL_ARCHITECTURE.md](./HEXAGONAL_ARCHITECTURE.md)** - Estructura objetivo
4. **[LANGCHAIN_INTEGRATION_DIAGRAM.md](./LANGCHAIN_INTEGRATION_DIAGRAM.md)** - Diagramas

### 🧠 Trabajando con LLMs

1. **[LANGCHAIN_INTEGRATION.md](./LANGCHAIN_INTEGRATION.md)** - Overview completo
2. **[LANGCHAIN_INTEGRATION_DIAGRAM.md](./LANGCHAIN_INTEGRATION_DIAGRAM.md)** - Visualización
3. **[MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)** - Implementación paso a paso
4. **[SPIKE_REQ021_LOCAL_LLM_INSIGHTS_QUALITY.md](./SPIKE_REQ021_LOCAL_LLM_INSIGHTS_QUALITY.md)** - Benchmarks

### 🗄️ Trabajando con base de datos

1. **[DATABASE_DESIGN_REVIEW.md](./DATABASE_DESIGN_REVIEW.md)** - Schema actual
2. **[DATABASE_MIGRATIONS.md](./DATABASE_MIGRATIONS.md)** - Crear migraciones
3. **[MIGRATIONS_SYSTEM.md](./MIGRATIONS_SYSTEM.md)** - Sistema automatizado

### 🎨 Trabajando en el dashboard

1. **[FRONTEND_DASHBOARD_API.md](./FRONTEND_DASHBOARD_API.md)** - API reference
2. **[VISUAL_ANALYTICS_GUIDELINES.md](./VISUAL_ANALYTICS_GUIDELINES.md)** - Best practices
3. **[D3_SANKEY_REFERENCE.md](./D3_SANKEY_REFERENCE.md)** - D3 Sankey charts

### 🐛 Debugging

1. **[PIPELINE_FULL_AUDIT.md](./PIPELINE_FULL_AUDIT.md)** - Flujo completo
2. **[INSIGHTS_PIPELINE_REVIEW.md](./INSIGHTS_PIPELINE_REVIEW.md)** - Insights specifics
3. **[DASHBOARD_ANALYSIS_KNOWN_ISSUES.md](./DASHBOARD_ANALYSIS_KNOWN_ISSUES.md)** - Known issues

---

## 📊 Estadísticas

| Categoría | # Documentos | Actualización |
|-----------|--------------|---------------|
| Arquitectura | 2 | Activo (REQ-021) |
| LangChain/LLM | 5 | **Nuevo (2026-03-31)** |
| Backend Refactor | 2 | Activo (REQ-021) |
| Base de Datos | 4 | Estable |
| Pipeline | 3 | Estable |
| Frontend/Dashboard | 4 | Estable |
| Fixes históricos | 1 | Archivo |
| **TOTAL** | **21** | — |

---

## 🔄 Estado de Documentación

| Estado | Documentos |
|--------|-----------|
| ✅ **Activo** (actualizándose) | HEXAGONAL_ARCHITECTURE, LANGCHAIN_INTEGRATION*, BACKEND_REFACTOR_TASK, MIGRATION_GUIDE |
| 🟢 **Estable** (referencia actual) | DATABASE_*, PIPELINE_*, FRONTEND_*, VISUAL_* |
| 🟡 **Legacy** (referencia histórica) | OPENAI_INTEGRATION, PLAN_MIGRACIONES_LIMPIEZA, FIX_095_FILE_NAMING |

---

## 📝 Convenciones

### Emojis de Estado en Documentos

- ⭐ **NUEVO**: Documento recién creado
- ✅ **COMPLETADO**: Tarea/fix documentado completamente
- 🔄 **EN PROGRESO**: Documento actualizándose activamente
- 🟢 **ESTABLE**: Documento completo y actualizado
- 🟡 **LEGACY**: Referencia histórica, no activo

### Metadata en Documentos

Cada documento debe incluir:
```markdown
> **Propósito**: [Descripción concisa]
> **Última actualización**: YYYY-MM-DD
> **Estado**: [Activo/Estable/Legacy]
> **Relacionado**: [Links a otros docs]
```

---

## 🚀 Próximos Documentos (Roadmap)

- [ ] **DOMAIN_SERVICES.md** - Documentación de domain services (REQ-021)
- [ ] **REPOSITORIES_PATTERN.md** - Implementación de repositories (REQ-021)
- [ ] **EVENT_BUS_ADVANCED.md** - Event bus con Redis pub/sub (futuro)
- [ ] **KNOWLEDGE_GRAPH.md** - Knowledge graph builder (futuro)
- [ ] **TESTING_STRATEGY.md** - Testing strategy completa (futuro)

---

**Última actualización**: 2026-03-31  
**Mantenido por**: REQ-021 Backend Refactor  
**Versión**: 2.0 (Post-LangChain integration)
