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

/**
 * Transform dashboard data to Sankey format
 * Creates nodes (stages) and links (document flows between stages)
 * 
 * @param {Object} analysisData - Analysis data from /api/dashboard/analysis
 * @returns {Object} - {nodes: [], links: []} for d3.sankey()
 */
export const transformForSankey = (analysisData) => {
  if (!analysisData?.pipeline?.stages) {
    return { nodes: [], links: [] };
  }

  const stagesArray = analysisData.pipeline.stages;
  
  // Backend returns array, we need to work with it
  if (!Array.isArray(stagesArray) || stagesArray.length === 0) {
    return { nodes: [], links: [] };
  }

  const nodes = [];
  const links = [];
  const nodeMap = new Map(); // For quick lookup

  // Define stage colors
  const stageColors = {
    'Upload': '#f59e0b',       // Orange
    'OCR': '#3b82f6',          // Blue
    'Chunking': '#8b5cf6',     // Purple
    'Indexing': '#ec4899',     // Pink
    'Insights': '#10b981',     // Green
    'Indexing Insights': '#14b8a6'  // Teal
  };

  // Create nodes from array
  stagesArray.forEach((stageData, index) => {
    const stageName = stageData.name;
    const total = stageData.total_documents || stageData.completed_tasks || 0;
    
    if (total === 0 && index > 0) return; // Skip empty stages except first one
    
    nodes.push({
      id: `stage-${index}`,
      name: stageName,
      value: total,
      color: stageColors[stageName] || '#94a3b8',
      stage: stageName.toLowerCase(),
      index,
      meta: {
        pending: stageData.pending_tasks || 0,
        processing: stageData.processing_tasks || 0,
        done: stageData.completed_tasks || 0,
        error: stageData.error_tasks || 0
      }
    });
    
    nodeMap.set(stageName, nodes.length - 1);
  });

  // Create links between consecutive stages
  for (let i = 0; i < stagesArray.length - 1; i++) {
    const currentStage = stagesArray[i];
    const nextStage = stagesArray[i + 1];
    
    if (!currentStage || !nextStage) continue;

    const currentNodeIndex = nodeMap.get(currentStage.name);
    const nextNodeIndex = nodeMap.get(nextStage.name);
    
    if (currentNodeIndex === undefined || nextNodeIndex === undefined) continue;

    // Documents that completed current stage flow to next stage
    const flowValue = currentStage.completed_tasks || 0;
    
    if (flowValue > 0) {
      links.push({
        source: currentNodeIndex,
        target: nextNodeIndex,
        value: flowValue,
        stage: currentStage.name,
        nextStage: nextStage.name
      });
    }
  }

  return { nodes, links };
};

/**
 * Prepare sparkline data from historical metrics
 * Creates time-series data for KPI sparklines
 * 
 * @param {Array} historicalData - Array of historical snapshots
 * @param {string} metric - Metric to extract (e.g., 'total_docs', 'total_news')
 * @param {number} hours - How many hours to show (default 1)
 * @returns {Array} - [{timestamp, value}]
 */
export const prepareSparklineData = (historicalData = [], metric, hours = 1) => {
  if (!Array.isArray(historicalData) || historicalData.length === 0) {
    // Return empty sparkline with placeholders
    const now = new Date();
    const points = [];
    for (let i = 11; i >= 0; i--) {
      points.push({
        timestamp: new Date(now.getTime() - i * 5 * 60 * 1000), // 5-minute intervals
        value: 0
      });
    }
    return points;
  }

  const now = new Date();
  const startTime = new Date(now.getTime() - hours * 60 * 60 * 1000);
  
  // Filter to time range and extract metric
  return historicalData
    .filter(snapshot => {
      const snapshotTime = new Date(snapshot.timestamp);
      return snapshotTime >= startTime && snapshotTime <= now;
    })
    .map(snapshot => ({
      timestamp: new Date(snapshot.timestamp),
      value: snapshot[metric] || 0
    }))
    .sort((a, b) => a.timestamp - b.timestamp);
};

/**
 * Calculate comparison metrics (current vs previous period)
 * @param {number} current - Current value
 * @param {number} previous - Previous period value
 * @returns {Object} - {change, changePercent, direction, isImprovement}
 */
export const calculateComparison = (current, previous, metric = 'count') => {
  const change = current - previous;
  const changePercent = previous > 0 ? Math.round((change / previous) * 100) : 0;
  const direction = change > 0 ? 'up' : change < 0 ? 'down' : 'stable';
  
  // For most metrics, up is good. For errors, down is good.
  const isImprovement = metric === 'errors' 
    ? direction === 'down' 
    : direction === 'up';
  
  return {
    change,
    changePercent,
    direction,
    isImprovement,
    indicator: direction === 'up' ? '↑' : direction === 'down' ? '↓' : '→'
  };
};

/**
 * Extract comparison data from sparkline
 * Compares most recent value vs value from N intervals ago
 * 
 * @param {Array} sparklineData - Array from prepareSparklineData
 * @param {number} intervals - How many intervals back to compare (default 12 = 1 hour at 5min intervals)
 * @returns {Object} - Comparison metrics
 */
export const extractSparklineComparison = (sparklineData, intervals = 12) => {
  if (!sparklineData || sparklineData.length < 2) {
    return { change: 0, changePercent: 0, direction: 'stable', isImprovement: false, indicator: '→' };
  }

  const current = sparklineData[sparklineData.length - 1].value;
  const compareIndex = Math.max(0, sparklineData.length - intervals - 1);
  const previous = sparklineData[compareIndex].value;
  
  return calculateComparison(current, previous);
};

/**
 * Generate tooltip HTML for KPI card with sparkline
 * @param {Object} kpiData - KPI data with sparkline
 * @param {Object} comparison - Comparison metrics
 * @returns {string} - HTML string
 */
export const generateKPITooltipHTML = (kpiData, comparison) => {
  const trendLine = comparison.direction === 'up' 
    ? '📈 Tendencia ascendente'
    : comparison.direction === 'down'
    ? '📉 Tendencia descendente'
    : '➡️ Estable';
  
  const improvementText = comparison.isImprovement
    ? '<span style="color: #4caf50;">✓ Mejorando</span>'
    : '<span style="color: #f59e0b;">⚠ Requiere atención</span>';
  
  return `
    <div style="font-family: system-ui; font-size: 12px;">
      <strong style="font-size: 14px;">${kpiData.label}</strong><br/>
      <hr style="margin: 4px 0; border-color: #334155; opacity: 0.3;">
      Valor actual: <strong>${kpiData.current}</strong><br/>
      ${trendLine}<br/>
      Cambio: <strong>${comparison.indicator} ${Math.abs(comparison.change)}</strong> (${Math.abs(comparison.changePercent)}%)<br/>
      <br/>
      ${improvementText}
    </div>
  `;
};

