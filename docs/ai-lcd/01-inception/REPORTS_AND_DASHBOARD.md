# Dashboard y Reportes - NewsAnalyzer-RAG

> Visión: tabla de progreso de archivos y reportes, reporte diario y semanal por temas, patrones y posturas

**Última actualización**: 2026-03-02
**Fase AI-DLC**: 01-inception
**Audiencia**: Product owner, desarrolladores
**Relación**: BR-11, BR-12, BR-13 | UC-08, UC-09, UC-10

---

## 1. Objetivo

- Dar **visibilidad** del estado de la ingesta (archivos subidos, en proceso, indexados) y de los **reportes generados**.
- Ofrecer **reportes automáticos** (diario y semanal) que resuman las noticias por **temas**, **patrones** y **posturas** (enfoques, líneas editoriales), ya que un mismo tema puede aparecer en distintos días.
- Que tanto la **familia** como el **admin** puedan consultar esos reportes (acceso para todos los usuarios autenticados).

---

## 2. Dashboard / Tabla de progreso

### 2.1 Archivos

Una vista (tabla o lista) que muestre:

| Campo (ejemplo) | Descripción |
|-----------------|-------------|
| Nombre / nombre de archivo | Identificación del documento |
| Fecha de ingesta | Cuándo se subió o entró por inbox |
| Estado | Pendiente, En proceso, Indexado, Error |
| Fecha de indexado | Cuando pasó a "Indexado" (opcional) |
| Notas / error | Si falló, mensaje breve |

- Filtros útiles: por fecha, por estado, por nombre.
- Base de datos o estado: puede venir de la lista actual de documentos indexados + una cola o log de procesamiento (inbox/upload) para los estados "en proceso" y "error".

### 2.2 Reportes generados

En la misma pantalla o en una pestaña "Reportes":

- Lista de **reportes diarios** (por fecha).
- Lista de **reportes semanales** (por periodo, p. ej. "Semana 1–7 Mar 2026").
- Para cada uno: fecha/periodo, tipo (diario/semanal), enlace o botón para **abrir/descargar** (vista web o PDF).
- Acceso: **todos los usuarios autenticados** (rol user, super_user, admin).

---

## 3. Contenido de los reportes

### 3.1 Temas

- Las noticias tratan **temas** (economía, política, sociedad, deportes, etc.).
- Un **mismo tema** puede aparecer en **varios días** y en varias fuentes.
- El reporte debe **agrupar y resumir por tema** (extracción vía LLM sobre el contenido indexado o metadatos/tags si se implementan).

### 3.2 Patrones

- **Patrones**: repetición de temas en el tiempo, evolución de un tema a lo largo de varios días, coincidencias entre fuentes.
- Útil sobre todo en el **reporte semanal** (vista de 7 días).

### 3.3 Posturas

- **Posturas** / enfoques: cómo se aborda un tema (línea editorial, tono, enfoque positivo/negativo/neutro, citas a unos u otros actores).
- El reporte puede incluir un apartado breve por tema: "posturas o enfoques detectados" (generado por LLM a partir de los chunks indexados).

### 3.4 Reporte diario

- **Alcance**: noticias **del día según la fecha de la noticia** (fecha de publicación/edición del medio), **no** por fecha de ingesta ni de procesamiento.
- **Fecha de la noticia**: debe obtenerse por convención del nombre del archivo (p. ej. `02-03-26-ABC.pdf` → 2 de marzo de 2026) y/o por extracción del contenido (fecha de portada, de edición). Esta fecha ha de persistirse (p. ej. en metadatos del documento o en `document_status`) para filtrar siempre por “día de la noticia”.
- **Contenido sugerido**: temas del día, resumen por tema, posturas/enfoques detectados, titulares o fuentes más relevantes.
- **Generación**: job programado (p. ej. al final del día) que consulta el RAG/LLM sobre los documentos **cuya fecha de noticia es ese día** y genera el texto del reporte; se guarda y se enlaza desde el dashboard.

#### 3.4.1 Actualización por contenido tardío y temas recurrentes

- **Archivo que llega tarde y corresponde a un día anterior**: si se recibe (o se procesa después) un archivo cuya **fecha de noticia** es un día ya pasado, el **reporte de ese día** debe **regenerarse/actualizarse** para incluir esa noticia, y los usuarios deben ser **notificados** de que el reporte de ese día ha cambiado (p. ej. “El reporte del 1 de marzo se ha actualizado”).
- **Tema que vuelve a aparecer**: si el nuevo contenido introduce o desarrolla un **tema que ya apareció en otro día**:
  - **Actualizar el reporte del día de la noticia actual** (incluir la nueva noticia y sus temas).
  - **Actualizar también el reporte del día donde ese tema apareció antes** (p. ej. añadir una nota tipo “Este tema vuelve a aparecer el día X” o regenerar ese reporte incorporando la nueva mención). Así se mantiene coherencia entre reportes y se reflejan patrones/evolución.
- **Notificación**: en ambos casos (contenido tardío o tema recurrente), notificar a los usuarios de que uno o más reportes se han actualizado (mecanismo a definir: bandeja en la app, correo, etc.).

### 3.5 Reporte semanal

- **Alcance**: noticias de la semana (p. ej. lunes a domingo).
- **Contenido sugerido**: temas que aparecieron en varios días, patrones (qué temas se repiten, cómo evolucionan), posturas recurrentes, resumen semanal por tema.
- **Generación**: job programado (p. ej. lunes por la mañana) que agrega documentos de la semana y pide al LLM un resumen con temas, patrones y posturas; se guarda y se enlaza desde el dashboard.

---

## 4. Acceso

- **Dashboard (progreso de archivos y lista de reportes)**: todos los usuarios autenticados.
- **Reporte diario**: todos (solo lectura).
- **Reporte semanal**: todos (solo lectura).
- **Generación de reportes**: tarea del sistema (jobs en backend); el admin puede disparar manualmente si se desea (futuro).

---

## 5. Fases sugeridas (roadmap)

*Estado (2026-03-02):* Reporte diario implementado. Siguiente: reporte semanal.

| Fase | Entregable | Dependencias |
|------|------------|--------------|
| **Ingesta** | Script carga masiva + carpeta inbox | — |
| **Estado de archivos** | API + UI para estado de documentos (pendiente/en proceso/indexado/error) y tabla en frontend | Cola o log de procesamiento |
| **Reporte diario** | Job que genera reporte del día (temas, posturas); alcance por **fecha de la noticia**; actualización cuando llega contenido tardío o tema recurrente; notificación a usuarios; almacenamiento; vista/descarga en UI | RAG/LLM, documentos con **news_date**, lógica de actualización y notificación |
| **Reporte semanal** | Job que genera reporte de la semana (temas, patrones, posturas); almacenamiento; vista/descarga | Igual + agregación por semana |
| **Dashboard unificado** | Una vista que combine tabla de archivos + lista de reportes diarios/semanales con enlaces | Todo lo anterior |

---

## 6. Notas técnicas (para construcción)

- **Fecha de la noticia**: campo obligatorio para reportes. Opciones de implementación:
  - Inferir desde el nombre del archivo (p. ej. `DD-MM-YY-*.pdf` o `YY-MM-DD-*.pdf`) y guardarlo en `document_status` y/o en el payload de Qdrant (p. ej. `news_date`).
  - Complementar con extracción por LLM del contenido (fecha de portada, “edición del día X”) si se desea mayor precisión.
- **Alcance del reporte**: filtrar documentos por `news_date = fecha_del_reporte`, no por `ingested_at` ni `indexed_at`.
- **Actualización de reportes**: al indexar un documento nuevo, obtener su `news_date`; si corresponde a un día ya pasado, regenerar el reporte de ese día y notificar. Si el contenido comparte temas con otro día, regenerar/actualizar también el reporte de ese otro día y notificar.
- **Almacenamiento de reportes**: tabla en SQLite (o archivos en disco) con fecha/periodo, tipo, contenido (HTML o markdown), opcional PDF generado. Considerar campo `updated_at` para saber si un reporte se regeneró tras la primera publicación.
- **Generación**: endpoints o jobs en backend que usen el RAG/LLM sobre documentos filtrados por **fecha de noticia**; prompt específico para "resumen por temas, patrones y posturas".
- **Frontend**: nueva ruta o sección "Dashboard" / "Reportes" con tabla de archivos (datos desde API existente o nueva) y lista de reportes con enlace a vista o descarga; indicador de “actualizado” cuando un reporte se haya regenerado.
- **Notificaciones**: mecanismo (bandeja en la app, correo, etc.) para avisar cuando uno o más reportes se actualizan.

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-02 | 1.0 | Creación: visión dashboard, reportes diario/semanal, temas/patrones/posturas, acceso para todos | AI-DLC |
| 2026-03-02 | 1.1 | Reporte diario por **fecha de la noticia** (no por ingesta); actualización por contenido tardío y temas recurrentes; notificación a usuarios | AI-DLC |
| 2026-03-02 | 1.2 | Estado de implementación en §5: reporte diario hecho; siguiente reporte semanal | AI-DLC |
