/**
 * Semantic Zoom Service for Pipeline Sankey
 * 
 * Implements hierarchical grouping with collapse/expand functionality:
 * - Level 1 (collapsed): "Active" vs "Inactive" meta-groups
 * - Level 2 (expanded): Individual stages within each group
 * 
 * Benefits:
 * - Reduces visual clutter when many documents
 * - Maintains flow understanding at different detail levels
 * - Aggregates values: sum of all documents in group
 */

/**
 * Define grouping hierarchy:
 * - Active: pending, ocr, chunking, indexing, insights (currently processing)
 * - Inactive: completed, error (final states)
 */
export const GROUP_HIERARCHY = {
  active: {
    label: '🟢 Activos',
    color: '#10b981',
    stages: ['upload', 'ocr', 'chunking', 'indexing', 'insights'],
    description: 'Documentos en proceso'
  },
  inactive: {
    label: '⚫ No Activos',
    color: '#6b7280',
    stages: ['completed', 'error', 'paused'],
    description: 'Documentos finalizados'
  }
};

/**
 * Get meta-group for a stage
 * @param {string} stage - Stage name
 * @returns {string} - 'active' or 'inactive'
 */
export function getMetaGroup(stage) {
  for (const [groupKey, groupData] of Object.entries(GROUP_HIERARCHY)) {
    if (groupData.stages.includes(stage)) {
      return groupKey;
    }
  }
  return 'active'; // Default fallback
}

/**
 * Group documents by meta-group (active/inactive)
 * @param {Array} documents - Array of normalized documents
 * @param {Function} mapStageToColumn - Function to map doc to stage
 * @returns {Object} - { active: [...], inactive: [...] }
 */
export function groupDocumentsByMetaGroup(documents, mapStageToColumn) {
  const groups = {
    active: [],
    inactive: []
  };
  
  documents.forEach(doc => {
    const stage = mapStageToColumn(doc);
    const metaGroup = getMetaGroup(stage);
    groups[metaGroup].push(doc);
  });
  
  return groups;
}

/**
 * Calculate aggregated values for a meta-group
 * Used when the group is collapsed to show total flow
 * 
 * @param {Array} documents - Documents in the group
 * @returns {Object} - Aggregated metrics
 */
export function aggregateGroupMetrics(documents) {
  return {
    count: documents.length,
    totalSize: documents.reduce((sum, doc) => sum + (doc.file_size || 0), 0),
    totalChunks: documents.reduce((sum, doc) => sum + (doc.chunks_count || 0), 0),
    totalNews: documents.reduce((sum, doc) => sum + (doc.news_count || 0), 0),
    totalInsights: documents.reduce((sum, doc) => sum + (doc.insights_count || 0), 0),
    processing: documents.filter(doc => doc.status && doc.status.endsWith('_processing')).length,
    completed: documents.filter(doc => doc.status === 'completed').length,
    error: documents.filter(doc => doc.status === 'error').length
  };
}

/**
 * Transform documents for semantic zoom visualization
 * Returns hierarchical structure that can be rendered collapsed or expanded
 * 
 * @param {Array} documents - Normalized documents
 * @param {Function} mapStageToColumn - Stage mapping function
 * @param {boolean} collapsed - Whether groups are collapsed
 * @returns {Object} - Visualization data structure
 */
export function transformForSemanticZoom(documents, mapStageToColumn, collapsed = false) {
  const metaGroups = groupDocumentsByMetaGroup(documents, mapStageToColumn);
  
  if (collapsed) {
    // Level 1: Show only meta-groups (active/inactive)
    return {
      type: 'collapsed',
      groups: Object.entries(metaGroups).map(([groupKey, docs]) => ({
        id: groupKey,
        label: GROUP_HIERARCHY[groupKey].label,
        color: GROUP_HIERARCHY[groupKey].color,
        description: GROUP_HIERARCHY[groupKey].description,
        metrics: aggregateGroupMetrics(docs),
        documents: docs, // Keep for drill-down
        collapsed: true
      }))
    };
  } else {
    // Level 2: Show individual stages within each group
    return {
      type: 'expanded',
      groups: Object.entries(metaGroups).map(([groupKey, docs]) => {
        // Group documents by individual stage
        const stageGroups = {};
        GROUP_HIERARCHY[groupKey].stages.forEach(stage => {
          stageGroups[stage] = docs.filter(doc => mapStageToColumn(doc) === stage);
        });
        
        return {
          id: groupKey,
          label: GROUP_HIERARCHY[groupKey].label,
          color: GROUP_HIERARCHY[groupKey].color,
          description: GROUP_HIERARCHY[groupKey].description,
          metrics: aggregateGroupMetrics(docs),
          stages: Object.entries(stageGroups).map(([stage, stageDocs]) => ({
            id: stage,
            metaGroup: groupKey,
            documents: stageDocs,
            metrics: aggregateGroupMetrics(stageDocs)
          })),
          collapsed: false
        };
      })
    };
  }
}

/**
 * Calculate flow links for collapsed view
 * When groups are collapsed, we aggregate flows between meta-groups
 * 
 * @param {Object} visualizationData - Data from transformForSemanticZoom
 * @returns {Array} - Array of flow links { source, target, value }
 */
export function calculateCollapsedFlows(visualizationData) {
  if (visualizationData.type !== 'collapsed') {
    return [];
  }
  
  // In collapsed view, we only have one transition: active → inactive
  const activeGroup = visualizationData.groups.find(g => g.id === 'active');
  const inactiveGroup = visualizationData.groups.find(g => g.id === 'inactive');
  
  if (!activeGroup || !inactiveGroup) {
    return [];
  }
  
  // Count documents that transitioned from active to inactive
  // (completed or error documents that passed through active stages)
  const transitionedDocs = inactiveGroup.documents.filter(doc => 
    doc.processing_stage && GROUP_HIERARCHY.active.stages.includes(doc.processing_stage)
  );
  
  return [{
    source: 'active',
    target: 'inactive',
    value: transitionedDocs.length,
    metrics: aggregateGroupMetrics(transitionedDocs)
  }];
}

/**
 * Calculate vertical position for a group in collapsed view
 * Distributes groups evenly in available space
 * 
 * @param {number} groupIndex - Index of the group
 * @param {number} totalGroups - Total number of groups
 * @param {number} availableHeight - Available vertical space
 * @returns {number} - Y position
 */
export function calculateGroupPosition(groupIndex, totalGroups, availableHeight) {
  const spacing = availableHeight / (totalGroups + 1);
  return (groupIndex + 1) * spacing;
}

/**
 * Calculate stroke width for collapsed flow
 * Based on aggregated metrics of the group
 * 
 * @param {Object} metrics - Aggregated metrics
 * @param {string} metric - Which metric to use ('count', 'totalSize', etc)
 * @param {number} maxValue - Maximum value for normalization
 * @returns {number} - Stroke width in pixels
 */
export function calculateCollapsedStrokeWidth(metrics, metric = 'count', maxValue = 100) {
  const MIN_WIDTH = 2;
  const MAX_WIDTH = 50;
  
  const value = metrics[metric] || 0;
  const normalized = Math.min(value / maxValue, 1);
  
  return MIN_WIDTH + (MAX_WIDTH - MIN_WIDTH) * normalized;
}

/**
 * Generate tooltip HTML for collapsed group
 * 
 * @param {Object} group - Group data
 * @returns {string} - HTML string for tooltip
 */
export function generateCollapsedTooltipHTML(group) {
  const { label, description, metrics } = group;
  
  return `
    <div class="sankey-tooltip-collapsed">
      <div class="tooltip-header">
        <strong>${label}</strong>
        <span class="tooltip-badge">${metrics.count} docs</span>
      </div>
      <div class="tooltip-body">
        <p class="tooltip-description">${description}</p>
        <div class="tooltip-metrics">
          <div class="metric-row">
            <span class="metric-label">📄 Total:</span>
            <span class="metric-value">${metrics.count}</span>
          </div>
          <div class="metric-row">
            <span class="metric-label">💾 Tamaño:</span>
            <span class="metric-value">${(metrics.totalSize / (1024 * 1024)).toFixed(1)} MB</span>
          </div>
          <div class="metric-row">
            <span class="metric-label">📰 Noticias:</span>
            <span class="metric-value">${metrics.totalNews}</span>
          </div>
          <div class="metric-row">
            <span class="metric-label">🧩 Chunks:</span>
            <span class="metric-value">${metrics.totalChunks}</span>
          </div>
          ${metrics.processing > 0 ? `
            <div class="metric-row active">
              <span class="metric-label">🟢 Procesando:</span>
              <span class="metric-value">${metrics.processing}</span>
            </div>
          ` : ''}
          ${metrics.completed > 0 ? `
            <div class="metric-row">
              <span class="metric-label">✅ Completados:</span>
              <span class="metric-value">${metrics.completed}</span>
            </div>
          ` : ''}
          ${metrics.error > 0 ? `
            <div class="metric-row error">
              <span class="metric-label">❌ Errores:</span>
              <span class="metric-value">${metrics.error}</span>
            </div>
          ` : ''}
        </div>
        <p class="tooltip-hint">💡 Click para expandir y ver detalle por estado</p>
      </div>
    </div>
  `;
}

/**
 * Calculate optimal collapsed state based on document count
 * Auto-collapse when there are many documents
 * 
 * @param {number} documentCount - Number of documents
 * @param {number} threshold - Threshold for auto-collapse (default: 100)
 * @returns {boolean} - Whether to collapse
 */
export function shouldAutoCollapse(documentCount, threshold = 100) {
  return documentCount > threshold;
}

/**
 * Toggle collapse state for a group
 * Used for interactive expand/collapse
 * 
 * @param {Object} currentState - Current visualization state
 * @param {string} groupId - ID of group to toggle
 * @returns {Object} - New visualization state
 */
export function toggleGroupCollapse(currentState, groupId) {
  if (currentState.type === 'collapsed') {
    // Expanding: show all stages
    return { 
      ...currentState, 
      type: 'expanded',
      expandedGroup: groupId 
    };
  } else {
    // Collapsing: hide stages
    return { 
      ...currentState, 
      type: 'collapsed',
      expandedGroup: null 
    };
  }
}

export default {
  GROUP_HIERARCHY,
  getMetaGroup,
  groupDocumentsByMetaGroup,
  aggregateGroupMetrics,
  transformForSemanticZoom,
  calculateCollapsedFlows,
  calculateGroupPosition,
  calculateCollapsedStrokeWidth,
  generateCollapsedTooltipHTML,
  shouldAutoCollapse,
  toggleGroupCollapse
};
