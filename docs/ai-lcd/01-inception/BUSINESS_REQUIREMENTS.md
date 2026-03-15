# Business Requirements - NewsAnalyzer-RAG

> Objetivos de negocio y necesidades que impulsan el proyecto

**Última actualización**: 2026-03-02
**Fase AI-DLC**: 01-inception
**Audiencia**: Product owner, desarrolladores

---

## 1. Contexto

Una familia necesita una herramienta para analizar artículos de noticias en formato PDF de forma
profunda y accesible. El análisis debe cubrir texto completo (no solo titulares), tablas de datos,
y eventualmente imágenes. La familia no es técnica, por lo que la interfaz debe ser una página web
simple con login.

## 2. Objetivos de Negocio

| ID | Objetivo | Prioridad |
|----|----------|-----------|
| BR-01 | Análisis completo de PDFs de noticias (texto, tablas, datos) | Alta |
| BR-02 | Interfaz web accesible para usuarios no técnicos | Alta |
| BR-03 | Sistema multi-usuario con roles y permisos | Alta |
| BR-04 | Acceso web público con dominio propio y autenticación | Alta |
| BR-05 | Uso de OpenAI GPT-4o para respuestas de alta calidad | Media |
| BR-06 | Self-hosted (control total de datos) | Media |
| BR-07 | Análisis de imágenes dentro de PDFs (futuro) | Baja |
| BR-08 | Extracción de links embebidos en PDFs (futuro) | Baja |
| **BR-09** | **Ingesta masiva**: subir muchos PDFs de una vez (p. ej. 150) sin ir uno a uno en la UI | Alta |
| **BR-10** | **Carpeta vigilada (inbox)**: detectar y procesar automáticamente archivos nuevos en una carpeta (p. ej. ~8 diarios) | Alta |
| **BR-11** | **Dashboard/tabla de progreso**: ver estado de archivos (subidos, en proceso, indexados) y de reportes generados | Alta |
| **BR-12** | **Reportes por temas**: las noticias tienen temas; un tema puede aparecer en distintos días; detectar patrones y posturas (enfoques, líneas editoriales) | Alta |
| **BR-13** | **Reporte diario y reporte semanal**: generados automáticamente por **fecha de la noticia** (no por fecha de procesamiento); cuando llega contenido tardío o un tema reaparece, actualizar los reportes afectados y **notificar** a los usuarios; accesibles para todos (familia + admin) | Alta |

## 3. Usuarios

| Tipo | Perfil | Cantidad |
|------|--------|----------|
| **Admin** | Diego (técnico, gestiona la plataforma) | 1 |
| **Familia** | Usuarios no técnicos, solo consultan | 3-5 |

## 4. Restricciones

- **Presupuesto**: Mínimo (solo costo de API de OpenAI + hosting + dominio)
- **Infraestructura**: Hosting propio con dominio ya disponible
- **Técnico**: La familia no debe instalar nada; solo usar un navegador web
- **Privacidad**: Los PDFs se almacenan en el servidor propio

## 5. Criterios de Éxito

1. Un familiar puede abrir `https://noticias.dominio.com`, hacer login, y preguntar sobre una noticia
2. Las respuestas incluyen contenido del PDF (no inventado) con citas a las fuentes
3. Solo el admin puede subir/borrar documentos; la familia solo consulta
4. El sistema responde en menos de 10 segundos

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-02 | 1.0 | Creación inicial | AI-DLC |
