# Use Cases - NewsAnalyzer-RAG

> Casos de uso principales del sistema

**Última actualización**: 2026-03-02
**Fase AI-DLC**: 01-inception
**Audiencia**: Desarrolladores, QA

---

## UC-01: Admin sube PDF de noticia

**Actor**: Admin
**Precondición**: Autenticado como admin o super_user
**Flujo**:
1. Admin accede a la interfaz web
2. Click en "Upload Document"
3. Selecciona PDF de noticia desde su dispositivo
4. Sistema procesa el PDF (OCR si es escaneado, extracción de texto si es digital)
5. Sistema chunquea el texto y genera embeddings
6. Sistema indexa en Qdrant
7. Documento aparece en la lista, disponible para consultas

**Postcondición**: El documento es consultable por todos los usuarios autenticados

---

## UC-02: Familiar consulta una noticia

**Actor**: User (familiar, read-only)
**Precondición**: Autenticado, existen documentos indexados
**Flujo**:
1. Familiar accede a `https://dominio.com` desde su navegador (móvil o desktop)
2. Hace login con usuario/contraseña
3. Escribe una pregunta: "¿Qué dice la noticia sobre los impuestos?"
4. Sistema busca chunks relevantes en Qdrant
5. Sistema envía contexto + pregunta al LLM (OpenAI GPT-4o)
6. LLM genera respuesta basada en el contenido del PDF
7. Sistema muestra respuesta con citas a las fuentes (nombre del archivo, score de relevancia)

**Postcondición**: El familiar obtiene la información sin poder modificar nada

---

## UC-03: Admin gestiona usuarios

**Actor**: Admin
**Precondición**: Autenticado como admin
**Flujo**:
1. Admin accede al panel de administración
2. Crea usuario nuevo: nombre, email, contraseña, rol (user/super_user)
3. Comparte credenciales con el familiar
4. El familiar puede hacer login

**Roles disponibles**:
- `admin`: Gestión total (usuarios, documentos, configuración)
- `super_user`: Subir y borrar documentos + consultar
- `user`: Solo consultar documentos (read-only)

---

## UC-04: Admin elimina un documento

**Actor**: Admin o Super User
**Precondición**: Autenticado con permisos de delete
**Flujo**:
1. Admin ve la lista de documentos
2. Selecciona documento a eliminar
3. Confirma eliminación
4. Sistema elimina el documento, sus chunks y embeddings de Qdrant

---

## UC-05: Consulta conversacional (con historial)

**Actor**: Cualquier usuario autenticado
**Precondición**: Existen documentos indexados
**Flujo**:
1. Usuario hace una primera pregunta: "¿De qué trata la noticia?"
2. Sistema responde con resumen
3. Usuario hace pregunta de seguimiento: "¿Qué datos numéricos menciona?"
4. Sistema usa el historial de la conversación (últimas 5 preguntas) para contextualizar
5. Responde con datos específicos del PDF

---

## UC-06: Admin ingesta masiva desde carpeta

**Actor**: Admin o Super User
**Precondición**: Autenticado con permisos de upload
**Flujo**:
1. Admin coloca todos los PDFs (p. ej. 150) en una carpeta local
2. Ejecuta un script de línea de comandos indicando la ruta de la carpeta y credenciales (o variables de entorno)
3. El script hace login contra la API, recorre la carpeta y sube cada archivo admitido vía `POST /api/documents/upload`
4. El backend procesa cada documento en segundo plano (OCR → chunk → index)
5. Los documentos quedan disponibles para consulta sin usar la UI

**Postcondición**: Todos los archivos de la carpeta están indexados. Útil para carga inicial o lotes grandes.

---

## UC-07: Carpeta inbox (auto-procesado)

**Actor**: Sistema (sin intervención del usuario)
**Precondición**: Backend configurado con `INBOX_DIR` (carpeta vigilada)
**Flujo**:
1. Admin (o un proceso externo) copia o mueve archivos nuevos a la carpeta inbox (p. ej. `local-data/inbox`)
2. Un job programado en el backend (cada X minutos) lista la carpeta inbox
3. Por cada archivo nuevo con extensión admitida: lo procesa (OCR → chunk → index) y lo mueve a una subcarpeta `processed/` para no reprocesarlo
4. Los documentos quedan indexados sin abrir la UI

**Postcondición**: Archivos nuevos añadidos a la inbox se procesan solos. Ideal para ~8 documentos diarios recibidos por correo/carpeta compartida.

---

## UC-08: Ver dashboard de progreso (archivos y reportes)

**Actor**: Cualquier usuario autenticado
**Precondición**: Autenticado
**Flujo**:
1. Usuario accede a una vista "Dashboard" o "Progreso" en la interfaz
2. Ve una tabla (o paneles) con:
   - **Archivos**: estado de cada documento (pendiente / en proceso / indexado / error), fecha de ingesta, nombre
   - **Reportes**: reportes diarios y semanales generados (fecha, tipo, enlace o vista)
3. Puede filtrar por fecha, estado o tipo de reporte
4. Puede abrir un reporte para leerlo

**Postcondición**: Usuario tiene visibilidad del estado de la ingesta y de los reportes disponibles.

---

## UC-09: Consultar reporte diario

**Actor**: Cualquier usuario autenticado (familia + admin)
**Precondición**: Existe al menos un reporte diario generado (el reporte corresponde a la **fecha de la noticia**, no a la fecha de procesamiento).
**Flujo**:
1. Usuario accede al dashboard o a la sección "Reportes"
2. Selecciona "Reporte diario" y la fecha deseada (día de la noticia)
3. El sistema muestra el reporte generado para ese día: temas cubiertos en las noticias, patrones, posturas o enfoques detectados, resumen por tema
4. El contenido es legible (texto/HTML o descarga PDF) y accesible para todos los roles
5. Si el reporte se actualizó tras la primera publicación (p. ej. por contenido tardío o tema recurrente), el usuario puede ver que está actualizado y, si está definido el mecanismo, recibe notificación de reportes actualizados

**Postcondición**: Usuario obtiene una visión sintética de las noticias del día (por fecha de la noticia) por temas y enfoques.

---

## UC-10: Consultar reporte semanal

**Actor**: Cualquier usuario autenticado (familia + admin)
**Precondición**: Existe al menos un reporte semanal generado
**Flujo**:
1. Usuario accede al dashboard o a la sección "Reportes"
2. Selecciona "Reporte semanal" y el periodo (p. ej. semana del 1 al 7 de marzo)
3. El sistema muestra el reporte: temas que aparecieron en varios días, patrones entre días, posturas o líneas recurrentes, resumen semanal
4. Accesible para todos los roles (read-only suficiente)

**Postcondición**: Usuario obtiene una visión agregada de la semana para ver temas transversales y patrones.

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-02 | 1.0 | Creación inicial | AI-DLC |
