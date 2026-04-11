# Dashboard Operativo IA-LCD · Wireframe vNext (2026-04-11)

## Resumen
- **Objetivo:** Documentar el wireframe aprobado del dashboard operativo y dejar listos los artefactos para implementación.
- **Figma:** [Wy9Gscw0ao4MpPcIMhl7J5](https://www.figma.com/design/Wy9Gscw0ao4MpPcIMhl7J5/Untitled?node-id=104-2). Frames relevantes: “RAG Dashboard – Concept vNext” (referencia) y “RAG Dashboard – Wireframe vNext” (detalle actual).
- **Estado:** Wireframe alineado con `DASHBOARD_REFACTOR_PLAN.md`, `PARALLEL_COORDINATES_IMPROVEMENTS.md` y `DASHBOARD_VISUAL_IMPROVEMENTS_PLAN.md`. Los requisitos de pipeline (Upload/Validación → OCR → Segmentación → Chunking → Indexaciones → Insights → Publicación) se cubren explícitamente.

## Layout y secciones
1. **Encabezado global**: contexto y objetivo del dashboard.
2. **Barra de controles**: filtros (cluster/fuente, rango temporal, auto-refresh, pausa, idioma) y acciones (reprocesar, exportar CSV, nueva ingesta, auditoría).
3. **Fila de KPIs**: métricas Documento → Noticias → Insights → Alertas con porcentajes y tendencia.
4. **Zona analítica principal**:
   - **Coordenadas paralelas con zoom semántico** (overview/detalle, agrupar por fuente, resaltar errores, modo comparativo).
   - **Panel de detalle enlazado** (PDF, noticia, valores crudos por etapa) sincronizado con brushing.
   - **Nota de expansión**: doble click en cualquier etapa despliega subcolumnas con métricas contextuales (MB, caracteres, % cobertura, relevancia, etc.) y mantiene brushes.
5. **Panel lateral**:
   - Salud del pipeline con badges de latencia/errores y controles de pausa/retry por etapa.
   - Nota que describe cómo los iconos de alerta viven sobre cada columna del chart y se enlazan con “Exploración de documentos”.
   - Timeline SLA + feed de errores (24h) sincronizado con brushing.
6. **Explorador de documentos**: tabla + detalle editable con tabs (PDF, noticias, insights, errores) y acciones directas.
7. **Correlaciones Noticias/Insights**: mapa de clusters/heatmap + comparador de insights con acciones (marcar vigente, expirar, etc.).
8. **Operaciones y backlog**: tarjetas para backlog priorizado, checklist de validaciones (idioma ES+i18n, visibilidad de etapas, SLA) y acciones del monitor.

## Interacciones clave
- **Brushing & linking**: coordenadas ↔ timeline ↔ panel de salud ↔ tabla/preview.
- **Expansión horizontal/vertical**: cada panel puede expandirse para foco (siguiendo `SEMANTIC_ZOOM_GUIDE.md`).
- **Alert icons**: se renderizan encima de la columna correspondiente en las coordenadas; hover/click abre detalle en panel de salud y filtra el explorador de documentos.
- **Valores exactos**: tooltips/HUD muestran siempre el dato crudo (MB, segundos, nº errores, relevancia) aunque la proporción esté codificada por longitud/color.

## Datos y endpoints previstos
| Componentes | Endpoint/Servicio | Notas |
|-------------|------------------|-------|
| GlobalControlsBar | `GET /api/dashboard/filters`, `POST /api/pipeline/stages/{stage}/pause|resume`, `POST /api/documents/requeue` | Controles de pausa, idioma, auto-refresh.
| KpiRow | `GET /api/dashboard/kpis` | Totales + % vectorizado + tendencia.
| ParallelCoordinatesPanel | `GET /api/dashboard/pipeline-flow?range=…` | Incluye metrics stageTimes, errors, sizeMb, newsCount, insightStatus.
| PipelineHealthPanel | `GET /api/dashboard/stages` | KPIs agregados + acciones.
| IncidentTimeline | `GET /api/dashboard/incidents` | Timeline SLA 24h + feed textual.
| DocumentExplorer | `GET /api/documents`, `GET /api/documents/{id}`, `GET /api/documents/{id}/news` | Tabla filtrable + detalle con tabs.
| NewsInsightCorrelation | `GET /api/news/clusters`, `GET /api/insights/comparison` | Cluster map + comparador.
| OperationsBacklog | `GET /api/dashboard/backlog` | Basado en `PENDING_BACKLOG.md` y `REQ-026_UPLOAD_WORKER_IMPLEMENTED.md`.

## Colores y codificación de estados
- Escala secuencial **azul → verde → ámbar → rojo** aplicada en coordenadas, panel de salud y badges. Cada 10 % se usa un tono preseleccionado (`--color-pipeline-{state}-{0..9}`) alineado con `DASHBOARD_VISUAL_IMPROVEMENTS_PLAN.md`.
- Azul/frío = pendiente/esperando; verde = procesando/completado; ámbar = advertencia/latencia alta; rojo = error crítico.

## i18n
- Idioma por defecto español; toggle EN disponible en controles globales.
- Todos los strings se registrarán en `dashboard.monitor.*` vía `react-intl` (ver `REQ-026_DOCUMENTATION_INDEX.md`).

## Artefactos
- **Backup estructural**: `docs/ai-lcd/artifacts/figma_wireframe_vnext_2026-04-11.json` (árbol jerárquico con IDs/nombres de cada frame y sección del wireframe en Figma).
- **Plan técnico**: descrito en `docs/ai-lcd/DASHBOARD_REFACTOR_PLAN.md` (sección “Fase 3”) + este documento.

## Próximos pasos
1. Aprobar documento y artefactos.
2. Implementar `DashboardService`/`DashboardController` con los endpoints listados.
3. Construir componentes React/D3 siguiendo este wireframe y la codificación de colores definida.
