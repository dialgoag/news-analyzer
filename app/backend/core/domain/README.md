# Domain Layer - NewsAnalyzer-RAG

Domain layer con entities y value objects siguiendo Domain-Driven Design (DDD).

## ⚠️ IMPORTANTE: Domain Model vs. Production

Este domain model es una **abstracción simplificada** para entities.  
El código de **producción** usa nombres más específicos con prefijos de stage.

### Dos Sistemas Coexisten (Temporalmente)

| Aspecto | Domain Model (este directorio) | Production (`pipeline_states.py`) |
|---------|-------------------------------|----------------------------------|
| **Propósito** | Entities, business logic, tests | Database, SQL queries, workers |
| **Document Status** | `queued`, `processing`, `completed` | `ocr_pending`, `ocr_processing`, `ocr_done`, `chunking_done`, etc. |
| **Insight Status** | `pending`, `queued`, `generating`, `done` | ✅ MISMO (no usa prefijos) |
| **Worker Status** | `assigned`, `started`, `completed` | ✅ MISMO |
| **Usado en** | `entities/`, tests unitarios | `app.py`, `database.py`, SQL |
| **Status** | ⏳ En desarrollo (Fase 1 completa) | ✅ En producción |

### ¿Por Qué Dos Sistemas?

**Production (prefijos explícitos)**:
- ✅ **Claridad en logs**: `status="ocr_processing"` es auto-explicativo
- ✅ **SQL simple**: `WHERE status = 'ocr_done'` (no necesita JOIN con stage)
- ✅ **Debugging fácil**: Ves el status y sabes exactamente dónde está

**Domain Model (genérico)**:
- ✅ **Reutilizable**: Mismo enum para diferentes contextos
- ✅ **Type-safe**: No strings sueltos, validación automática
- ✅ **Business logic clara**: Transiciones validadas en entities
- ✅ **Testing simple**: No necesitas saber detalles de stages

### Mapeo (Fase 2: Repositories)

Los **Repositories** harán la traducción:

```python
# Repository: DB → Domain
db_row = {"status": "ocr_processing", "processing_stage": "ocr"}
domain_status = "processing"  # Simplificado para entity

# Repository: Domain → DB
entity.mark_queued()  # Entity usa "queued"
db_status = determine_stage_status(entity, stage)  # → "ocr_pending"
```

**Ejemplo completo**:

```python
class PostgresDocumentRepository:
    def get(self, doc_id: DocumentId) -> Document:
        row = self.cursor.execute(
            "SELECT * FROM document_status WHERE document_id = %s",
            (str(doc_id),)
        ).fetchone()
        
        # Mapeo: producción → domain
        domain_status = self._map_to_domain_status(
            row['status'], 
            row['processing_stage']
        )
        
        return Document(
            id=DocumentId.from_string(row['document_id']),
            status=PipelineStatus.for_document(domain_status),
            # ...
        )
    
    def _map_to_domain_status(self, db_status: str, stage: str) -> str:
        """Map production status to domain model status."""
        # Estados terminales (sin cambio)
        if db_status in ("completed", "error", "paused"):
            return db_status
        
        # Estados con prefijos → genéricos
        if db_status.endswith("_pending"):
            return "queued"
        elif db_status.endswith("_processing"):
            return "processing"
        elif db_status.endswith("_done"):
            # Si no es el último stage, sigue en "processing"
            if stage in ("upload", "ocr", "chunking"):
                return "processing"
            # Si es indexing_done o insights_done, casi completo
            return "processing"
        
        return "queued"  # Default safe
```

## Estructura

```
core/domain/
├── entities/              # Entities con identity y lifecycle
│   ├── document.py       # Document aggregate root
│   ├── news_item.py      # NewsItem entity
│   └── worker.py         # Worker entity
├── value_objects/        # Value objects inmutables
│   ├── document_id.py    # IDs únicos
│   ├── text_hash.py      # SHA256 hashes
│   └── pipeline_status.py # Status con validación
├── events/               # Domain events (futuro)
└── services/             # Domain services (futuro)
```

## Testing

Los tests usan el domain model simplificado:

```bash
pytest tests/unit/test_value_objects.py  # 27 tests
pytest tests/unit/test_entities.py       # 21 tests
```

**Total**: 48 tests, 100% pass

## Referencias

- **Documentación completa**: `docs/PIPELINE_STATE_TRANSITIONS.md`
- **Production states**: `pipeline_states.py`
- **Arquitectura**: `docs/HEXAGONAL_ARCHITECTURE.md`
- **Session log**: `docs/SESSION_LOG.md` (Sesión 49)

---

**Última actualización**: 2026-03-31  
**Status**: Fase 1 (Entities + Value Objects) ✅ COMPLETA
