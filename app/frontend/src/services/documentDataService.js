/**
 * Document Data Transformation Service
 * 
 * Responsabilidad: Transformar datos crudos del API en datos listos para visualización
 * Los componentes NO deben hacer transformaciones, solo pintar
 */

/**
 * Normaliza métricas de documento, asignando valores mínimos visibles para nullos
 * Esto asegura que todos los documentos tengan líneas visibles en el Sankey
 */
export const normalizeDocumentMetrics = (doc) => {
  // Valores mínimos para que los documentos en espera sean visibles (pero delgados)
  const MIN_FILE_SIZE_MB = 0.5;  // Mínimo 0.5 MB para líneas delgadas
  const MIN_NEWS_COUNT = 1;      // Mínimo 1 noticia
  const MIN_CHUNKS_COUNT = 5;    // Mínimo 5 chunks
  const MIN_INSIGHTS_COUNT = 1;  // Mínimo 1 insight
  
  return {
    ...doc,
    // File size (para upload/ocr stage)
    file_size_mb: doc.file_size_mb || MIN_FILE_SIZE_MB,
    
    // News count (para chunking stage)
    news_count: doc.news_count || doc.total_news_items || MIN_NEWS_COUNT,
    total_news_items: doc.total_news_items || doc.news_count || MIN_NEWS_COUNT,
    
    // Chunks count (para indexing stage)
    chunks_count: doc.chunks_count || doc.num_chunks || MIN_CHUNKS_COUNT,
    num_chunks: doc.num_chunks || doc.chunks_count || MIN_CHUNKS_COUNT,
    
    // Insights count (para insights/completed stage)
    insights_count: doc.insights_count || MIN_INSIGHTS_COUNT,
    
    // Asegurar que document_id y filename existan
    document_id: doc.document_id || doc.id || 'unknown',
    filename: doc.filename || 'Unknown Document',
    
    // Status y stage sin cambios (pueden ser null, el componente los maneja)
    status: doc.status,
    processing_stage: doc.processing_stage,
  };
};

/**
 * Transforma lista completa de documentos del API
 * @param {Array} rawDocuments - Array de documentos del API
 * @returns {Array} - Array de documentos normalizados
 */
export const transformDocumentsForVisualization = (rawDocuments) => {
  if (!Array.isArray(rawDocuments)) {
    console.warn('transformDocumentsForVisualization: expected array, got', typeof rawDocuments);
    return [];
  }
  
  return rawDocuments.map(normalizeDocumentMetrics);
};

/**
 * Calcula el ancho de línea para un documento en un stage específico
 * Usa valores normalizados (ya transformados por normalizeDocumentMetrics)
 * 
 * @param {Object} doc - Documento normalizado
 * @param {string} stage - Stage actual ('upload', 'ocr', 'chunking', 'indexing', 'insights', 'completed')
 * @returns {number} - Ancho en píxeles (1-12)
 */
export const calculateStrokeWidth = (doc, stage) => {
  const MIN_WIDTH = 1;   // Ancho mínimo (documentos en espera)
  const MAX_WIDTH = 12;  // Ancho máximo
  
  // Factores de escala para cada métrica
  const SCALES = {
    fileSize: { max: 10, factor: 1.2 },      // 1-10 MB → 1-12px
    news: { max: 50, factor: 0.3 },          // 1-50 news → 1-15px
    chunks: { max: 500, factor: 0.05 },      // 5-500 chunks → 1-25px
    insights: { max: 100, factor: 0.15 },    // 1-100 insights → 1-15px
  };
  
  switch(stage) {
    case 'upload':
    case 'ocr':
      // Ancho basado en tamaño de archivo
      const fileSizeMB = doc.file_size_mb; // Ya normalizado (min 0.5)
      return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, fileSizeMB * SCALES.fileSize.factor));
      
    case 'chunking':
      // Ancho basado en número de noticias extraídas
      const newsCount = doc.news_count; // Ya normalizado (min 1)
      return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, newsCount * SCALES.news.factor));
      
    case 'indexing':
      // Ancho basado en número de chunks generados
      const chunksCount = doc.chunks_count; // Ya normalizado (min 5)
      return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, chunksCount * SCALES.chunks.factor));
      
    case 'insights':
    case 'completed':
      // Ancho basado en número de insights generados
      const insightsCount = doc.insights_count; // Ya normalizado (min 1)
      return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, insightsCount * SCALES.insights.factor));
      
    default:
      return MIN_WIDTH;
  }
};

/**
 * Genera texto de tooltip para un documento
 * @param {Object} doc - Documento normalizado
 * @param {string} currentStage - Stage actual del documento
 * @param {boolean} isActive - Si el documento está siendo procesado
 * @returns {string} - HTML del tooltip
 */
export const generateTooltipHTML = (doc, currentStage, isActive) => {
  const stageColors = {
    upload: '#f59e0b',
    ocr: '#3b82f6',
    chunking: '#8b5cf6',
    indexing: '#ec4899',
    insights: '#10b981',
    completed: '#6b7280',
  };
  
  const stageNames = {
    upload: 'Upload',
    ocr: 'OCR',
    chunking: 'Chunking',
    indexing: 'Indexing',
    insights: 'Insights',
    completed: 'Done',
  };
  
  const statusText = isActive ? '🟢 <strong>PROCESANDO</strong>' : '⚫ En cola';
  const color = stageColors[currentStage] || '#6b7280';
  const stageName = stageNames[currentStage] || currentStage;
  
  return `
    <strong>${doc.filename}</strong><br/>
    Estado: <span style="color: ${color}">${stageName}</span><br/>
    ${statusText}<br/>
    <hr style="margin: 4px 0; border-color: #334155;">
    <small>
    📄 Archivo: ${doc.file_size_mb.toFixed(1)} MB<br/>
    🔤 Noticias: ${doc.news_count}<br/>
    ✂️ Chunks: ${doc.chunks_count}<br/>
    💡 Insights: ${doc.insights_count}
    </small>
  `;
};

/**
 * Agrupa documentos por stage para estadísticas
 * @param {Array} documents - Array de documentos normalizados
 * @param {Function} mapStageFunc - Función que mapea doc → stage
 * @returns {Object} - Objeto con keys = stages, values = arrays de documentos
 */
export const groupDocumentsByStage = (documents, mapStageFunc) => {
  const stages = {
    upload: [],
    ocr: [],
    chunking: [],
    indexing: [],
    insights: [],
    completed: [],
    error: []
  };
  
  if (!Array.isArray(documents)) return stages;
  
  documents.forEach(doc => {
    const stage = mapStageFunc(doc);
    if (stages[stage]) {
      stages[stage].push(doc);
    }
  });
  
  return stages;
};
