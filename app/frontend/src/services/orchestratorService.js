/**
 * Orchestrator API Service
 * 
 * Servicio para consumir los endpoints del Orchestrator Agent v2
 * Proporciona acceso a timeline de eventos, métricas, y progreso de migración
 */

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * Fetch document processing timeline (eventos del pipeline para un documento)
 * @param {string} documentId - ID del documento
 * @param {string} token - JWT token for authentication
 * @returns {Promise<Object>} - Timeline con eventos ordenados
 */
export const fetchDocumentTimeline = async (documentId, token) => {
  const response = await fetch(
    `${API_BASE_URL}/api/orchestrator/document-timeline/${documentId}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch timeline: ${response.status} ${response.statusText}`);
  }

  return await response.json();
};

/**
 * Fetch pipeline metrics (métricas de performance por stage)
 * @param {string} token - JWT token for authentication
 * @returns {Promise<Object>} - Métricas agregadas por stage
 */
export const fetchPipelineMetrics = async (token) => {
  const response = await fetch(
    `${API_BASE_URL}/api/orchestrator/pipeline-metrics`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch metrics: ${response.status} ${response.statusText}`);
  }

  return await response.json();
};

/**
 * Fetch migration progress (progreso de migración legacy → orchestrator)
 * @param {string} token - JWT token for authentication
 * @returns {Promise<Object>} - Estado de migración por stage
 */
export const fetchMigrationProgress = async (token) => {
  const response = await fetch(
    `${API_BASE_URL}/api/orchestrator/migration-progress`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch migration progress: ${response.status} ${response.statusText}`);
  }

  return await response.json();
};

/**
 * Fetch recent errors (últimos errores del pipeline)
 * @param {string} token - JWT token for authentication
 * @param {number} limit - Cantidad máxima de errores (default 50)
 * @returns {Promise<Array>} - Array de errores recientes
 */
export const fetchRecentErrors = async (token, limit = 50) => {
  const response = await fetch(
    `${API_BASE_URL}/api/orchestrator/recent-errors?limit=${limit}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch recent errors: ${response.status} ${response.statusText}`);
  }

  return await response.json();
};

/**
 * Fetch active processing documents (documentos en procesamiento activo)
 * @param {string} token - JWT token for authentication
 * @returns {Promise<Array>} - Array de documentos siendo procesados
 */
export const fetchActiveProcessing = async (token) => {
  const response = await fetch(
    `${API_BASE_URL}/api/orchestrator/active-processing`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch active processing: ${response.status} ${response.statusText}`);
  }

  return await response.json();
};

/**
 * Transform timeline data for visualization
 * Convierte eventos del backend en formato listo para UI
 * 
 * @param {Object} timelineData - Datos del endpoint document-timeline
 * @returns {Array} - Array de eventos transformados
 */
export const transformTimelineForUI = (timelineData) => {
  if (!timelineData?.events || !Array.isArray(timelineData.events)) {
    return [];
  }

  return timelineData.events.map(event => ({
    ...event,
    timestamp: new Date(event.timestamp),
    duration_formatted: event.duration_sec 
      ? `${Math.round(event.duration_sec)}s`
      : 'N/A',
    has_error: event.status === 'error',
    metadata_summary: generateMetadataSummary(event.metadata),
  }));
};

/**
 * Transform pipeline metrics for dashboard cards
 * @param {Object} metricsData - Datos del endpoint pipeline-metrics
 * @returns {Array} - Array de métricas por stage
 */
export const transformMetricsForDashboard = (metricsData) => {
  if (!metricsData?.stages || !Array.isArray(metricsData.stages)) {
    return [];
  }

  return metricsData.stages.map(stage => ({
    ...stage,
    success_rate_percent: stage.success_rate 
      ? Math.round(stage.success_rate * 100) 
      : 0,
    avg_duration_formatted: stage.avg_duration_sec
      ? formatDuration(stage.avg_duration_sec)
      : 'N/A',
    has_errors: stage.total_errors > 0,
  }));
};

/**
 * Generate metadata summary text for an event
 * @param {Object|null} metadata - Metadata del evento
 * @returns {string} - Texto resumido
 */
const generateMetadataSummary = (metadata) => {
  if (!metadata) return 'No metadata';

  const keys = Object.keys(metadata);
  if (keys.length === 0) return 'Empty';

  // Extraer valores relevantes
  const summaryParts = [];
  
  if (metadata.pages) summaryParts.push(`${metadata.pages} pages`);
  if (metadata.articles) summaryParts.push(`${metadata.articles} articles`);
  if (metadata.chunks) summaryParts.push(`${metadata.chunks} chunks`);
  if (metadata.engine) summaryParts.push(`${metadata.engine}`);
  if (metadata.confidence) summaryParts.push(`conf: ${(metadata.confidence * 100).toFixed(0)}%`);

  return summaryParts.join(', ') || `${keys.length} fields`;
};

/**
 * Format duration in seconds to human-readable string
 * @param {number} seconds - Duration in seconds
 * @returns {string} - Formatted string
 */
const formatDuration = (seconds) => {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${Math.round(seconds / 3600)}h`;
};

/**
 * Get stage color for UI visualization
 * @param {string} stage - Stage name
 * @returns {string} - Hex color
 */
export const getStageColor = (stage) => {
  const colors = {
    upload: '#f59e0b',        // Orange
    validation: '#fbbf24',     // Amber
    ocr: '#3b82f6',           // Blue
    ocr_validation: '#60a5fa', // Light blue
    segmentation: '#8b5cf6',   // Purple
    chunking: '#a78bfa',       // Light purple
    indexing: '#ec4899',       // Pink
    insights: '#10b981',       // Green
    indexing_insights: '#14b8a6', // Teal
  };

  return colors[stage?.toLowerCase()] || '#6b7280'; // Gray fallback
};

/**
 * Get status icon for event
 * @param {string} status - Event status
 * @returns {string} - Emoji/icon
 */
export const getStatusIcon = (status) => {
  const icons = {
    started: '▶️',
    in_progress: '⏳',
    completed: '✅',
    error: '❌',
    skipped: '⏭️',
  };

  return icons[status] || '❓';
};

/**
 * Fetch full result for a specific stage
 * @param {string} documentId - Document UUID
 * @param {string} stage - Pipeline stage
 * @param {string} token - JWT token
 * @returns {Promise<Object>} - Stage result with full content
 */
export const fetchStageResult = async (documentId, stage, token) => {
  const response = await fetch(
    `${API_BASE_URL}/api/orchestrator/stage-result/${documentId}/${stage}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch stage result: ${response.status} ${response.statusText}`);
  }

  return await response.json();
};

