/**
 * Error Data Transformation Service
 * 
 * Responsabilidad: Transformar datos de errores del API en datos listos para charts y retry actions
 * Sigue el mismo patrón que documentDataService.js y workerDataService.js
 */

/**
 * Error severity classification
 */
const ERROR_SEVERITY = {
  CRITICAL: 'critical',
  HIGH: 'high',
  MEDIUM: 'medium',
  LOW: 'low'
};

/**
 * Error type patterns and their severity
 */
const ERROR_PATTERNS = {
  'rate limit': { severity: ERROR_SEVERITY.HIGH, canRetry: true, autoRetryDelay: 60 },
  '429': { severity: ERROR_SEVERITY.HIGH, canRetry: true, autoRetryDelay: 60 },
  'insufficient context': { severity: ERROR_SEVERITY.MEDIUM, canRetry: false, note: 'Needs better chunking' },
  'connection': { severity: ERROR_SEVERITY.HIGH, canRetry: true, autoRetryDelay: 10 },
  'timeout': { severity: ERROR_SEVERITY.HIGH, canRetry: true, autoRetryDelay: 5 },
  'file not found': { severity: ERROR_SEVERITY.CRITICAL, canRetry: false, note: 'File missing from disk' },
  'validation': { severity: ERROR_SEVERITY.MEDIUM, canRetry: false, note: 'Data quality issue' },
  'llm refusal': { severity: ERROR_SEVERITY.LOW, canRetry: false, note: 'Content policy violation' }
};

/**
 * Classify error based on message
 * @param {string} errorMessage - Error message text
 * @returns {Object} - {severity, canRetry, autoRetryDelay, note}
 */
export const classifyError = (errorMessage) => {
  if (!errorMessage) {
    return {
      severity: ERROR_SEVERITY.LOW,
      canRetry: false,
      autoRetryDelay: 0,
      note: 'Unknown error'
    };
  }

  const messageLower = errorMessage.toLowerCase();
  
  for (const [pattern, classification] of Object.entries(ERROR_PATTERNS)) {
    if (messageLower.includes(pattern)) {
      return classification;
    }
  }
  
  // Default classification for unknown errors
  return {
    severity: ERROR_SEVERITY.MEDIUM,
    canRetry: true,
    autoRetryDelay: 30,
    note: 'Generic error'
  };
};

/**
 * Group errors by type (message pattern)
 * @param {Array} errors - Array of error objects from API
 * @returns {Array} - Array of grouped errors with metadata
 */
export const groupErrorsByType = (errors = []) => {
  if (!Array.isArray(errors)) {
    console.warn('groupErrorsByType: expected array, got', typeof errors);
    return [];
  }

  const groups = new Map();

  errors.forEach(error => {
    const key = error.error_message || 'Unknown error';
    
    if (!groups.has(key)) {
      const classification = classifyError(key);
      groups.set(key, {
        error_message: key,
        count: 0,
        document_ids: [],
        news_item_ids: [],
        stages: new Set(),
        first_seen: error.created_at || error.error_at,
        last_seen: error.created_at || error.error_at,
        ...classification
      });
    }

    const group = groups.get(key);
    group.count++;
    
    if (error.document_id) group.document_ids.push(error.document_id);
    if (error.news_item_id) group.news_item_ids.push(error.news_item_id);
    if (error.stage) group.stages.add(error.stage);
    
    // Update time range
    const errorTime = new Date(error.created_at || error.error_at);
    const firstTime = new Date(group.first_seen);
    const lastTime = new Date(group.last_seen);
    
    if (errorTime < firstTime) group.first_seen = error.created_at || error.error_at;
    if (errorTime > lastTime) group.last_seen = error.created_at || error.error_at;
  });

  return Array.from(groups.values()).map(group => ({
    ...group,
    stages: Array.from(group.stages),
    document_ids: [...new Set(group.document_ids)],
    news_item_ids: [...new Set(group.news_item_ids)]
  }));
};

/**
 * Sort errors by priority
 * Priority order: severity (critical > high > medium > low), then count (descending)
 * 
 * @param {Array} errorGroups - Array from groupErrorsByType
 * @returns {Array} - Sorted array
 */
export const sortErrorsByPriority = (errorGroups) => {
  const severityOrder = {
    [ERROR_SEVERITY.CRITICAL]: 0,
    [ERROR_SEVERITY.HIGH]: 1,
    [ERROR_SEVERITY.MEDIUM]: 2,
    [ERROR_SEVERITY.LOW]: 3
  };

  return [...errorGroups].sort((a, b) => {
    // First by severity
    const severityDiff = severityOrder[a.severity] - severityOrder[b.severity];
    if (severityDiff !== 0) return severityDiff;
    
    // Then by count (descending)
    return b.count - a.count;
  });
};

/**
 * Prepare error timeline data
 * Groups errors into time buckets for sparkline/timeline visualization
 * 
 * @param {Array} errors - Array of error objects with timestamps
 * @param {number} hours - How many hours of history to show
 * @param {number} intervalMinutes - Bucket size in minutes
 * @returns {Array} - Timeline data [{timestamp, count, severity}]
 */
export const prepareErrorTimeline = (errors = [], hours = 24, intervalMinutes = 60) => {
  const now = new Date();
  const startTime = new Date(now.getTime() - hours * 60 * 60 * 1000);
  const buckets = [];
  
  // Create time buckets
  const numBuckets = Math.ceil((hours * 60) / intervalMinutes);
  for (let i = 0; i < numBuckets; i++) {
    const timestamp = new Date(startTime.getTime() + i * intervalMinutes * 60 * 1000);
    buckets.push({
      timestamp,
      count: 0,
      critical: 0,
      high: 0,
      medium: 0,
      low: 0
    });
  }
  
  // Fill buckets with error data
  errors.forEach(error => {
    const errorTime = new Date(error.created_at || error.error_at);
    if (errorTime < startTime || errorTime > now) return;
    
    const bucketIndex = Math.floor((errorTime - startTime) / (intervalMinutes * 60 * 1000));
    if (bucketIndex >= 0 && bucketIndex < buckets.length) {
      buckets[bucketIndex].count++;
      
      const classification = classifyError(error.error_message);
      buckets[bucketIndex][classification.severity]++;
    }
  });
  
  return buckets;
};

/**
 * Generate tooltip HTML for error bar chart
 * @param {Object} errorGroup - Error group object
 * @returns {string} - HTML string
 */
export const generateErrorTooltipHTML = (errorGroup) => {
  const severityEmoji = {
    [ERROR_SEVERITY.CRITICAL]: '🔴',
    [ERROR_SEVERITY.HIGH]: '🟠',
    [ERROR_SEVERITY.MEDIUM]: '🟡',
    [ERROR_SEVERITY.LOW]: '⚪'
  };
  
  const canRetryText = errorGroup.canRetry 
    ? `✅ Auto-retry: ${errorGroup.autoRetryDelay}s delay`
    : `❌ No auto-retry: ${errorGroup.note}`;
  
  const stagesText = errorGroup.stages.length > 0
    ? `Stages: ${errorGroup.stages.join(', ')}`
    : 'Stage: Unknown';
  
  return `
    <div style="font-family: system-ui; font-size: 12px; max-width: 320px;">
      <strong style="font-size: 14px;">${severityEmoji[errorGroup.severity]} ${errorGroup.error_message}</strong><br/>
      <hr style="margin: 6px 0; border-color: #334155; opacity: 0.3;">
      📊 Ocurrencias: <strong>${errorGroup.count}</strong><br/>
      📄 Documentos afectados: ${errorGroup.document_ids.length}<br/>
      📰 News items afectados: ${errorGroup.news_item_ids.length}<br/>
      ${stagesText}<br/>
      <br/>
      ${canRetryText}<br/>
      <br/>
      <small style="color: #94a3b8;">
        Primera: ${new Date(errorGroup.first_seen).toLocaleString()}<br/>
        Última: ${new Date(errorGroup.last_seen).toLocaleString()}
      </small>
    </div>
  `;
};

/**
 * Filter errors by stage
 * @param {Array} errorGroups - Array from groupErrorsByType
 * @param {string} stage - Stage to filter by (e.g., 'ocr', 'insights')
 * @returns {Array} - Filtered array
 */
export const filterErrorsByStage = (errorGroups, stage) => {
  if (!stage) return errorGroups;
  
  return errorGroups.filter(group => 
    group.stages.includes(stage)
  );
};

/**
 * Filter errors by retry capability
 * @param {Array} errorGroups - Array from groupErrorsByType
 * @param {boolean} retriable - true = can retry, false = cannot retry
 * @returns {Array} - Filtered array
 */
export const filterErrorsByRetriable = (errorGroups, retriable = true) => {
  return errorGroups.filter(group => group.canRetry === retriable);
};

/**
 * Calculate error statistics
 * @param {Array} errorGroups - Array from groupErrorsByType
 * @returns {Object} - Statistics
 */
export const calculateErrorStats = (errorGroups) => {
  const total = errorGroups.reduce((sum, g) => sum + g.count, 0);
  const retriable = errorGroups.filter(g => g.canRetry).reduce((sum, g) => sum + g.count, 0);
  const critical = errorGroups.filter(g => g.severity === ERROR_SEVERITY.CRITICAL).reduce((sum, g) => sum + g.count, 0);
  const high = errorGroups.filter(g => g.severity === ERROR_SEVERITY.HIGH).reduce((sum, g) => sum + g.count, 0);
  
  return {
    total,
    retriable,
    nonRetriable: total - retriable,
    critical,
    high,
    medium: errorGroups.filter(g => g.severity === ERROR_SEVERITY.MEDIUM).reduce((sum, g) => sum + g.count, 0),
    low: errorGroups.filter(g => g.severity === ERROR_SEVERITY.LOW).reduce((sum, g) => sum + g.count, 0),
    uniqueTypes: errorGroups.length,
    retriablePercent: total > 0 ? Math.round((retriable / total) * 100) : 0
  };
};

/**
 * Prepare batch retry payload
 * @param {Array} errorGroups - Selected error groups to retry
 * @returns {Object} - Payload for API
 */
export const prepareBatchRetryPayload = (errorGroups) => {
  const document_ids = [];
  const news_item_ids = [];
  
  errorGroups
    .filter(group => group.canRetry)
    .forEach(group => {
      document_ids.push(...group.document_ids);
      news_item_ids.push(...group.news_item_ids);
    });
  
  return {
    document_ids: [...new Set(document_ids)],
    news_item_ids: [...new Set(news_item_ids)],
    error_types: errorGroups.map(g => g.error_message),
    total_affected: document_ids.length + news_item_ids.length
  };
};
