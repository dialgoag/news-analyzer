/**
 * Worker Data Transformation Service
 * 
 * Responsabilidad: Transformar datos de workers del API en datos listos para bullet charts y visualizaciones
 * Sigue el mismo patrón que documentDataService.js
 */

/**
 * Worker type definitions with their default limits
 */
const WORKER_TYPES = {
  ocr: { label: 'OCR', color: '#3b82f6', defaultLimit: 2 },
  chunking: { label: 'Chunking', color: '#8b5cf6', defaultLimit: 4 },
  indexing: { label: 'Indexing', color: '#ec4899', defaultLimit: 8 },
  insights: { label: 'Insights', color: '#10b981', defaultLimit: 3 },
  indexing_insights: { label: 'Index Insights', color: '#f59e0b', defaultLimit: 4 }
};

/**
 * Capacity range thresholds for bullet charts
 */
const CAPACITY_RANGES = {
  good: 0.60,      // 0-60% utilization = good
  warning: 0.90,   // 61-90% = warning
  critical: 1.0    // 91-100% = critical
};

/**
 * Extract worker counts by type from worker status data
 * @param {Array} workers - Array of worker objects from API
 * @param {Object} limits - Limits object from API (e.g., {ocr: 2, indexing: 8})
 * @returns {Object} - Worker counts by type with metadata
 */
export const getWorkerCapacityByType = (workers = [], limits = {}) => {
  if (!Array.isArray(workers)) {
    console.warn('getWorkerCapacityByType: expected array, got', typeof workers);
    return {};
  }

  const capacity = {};
  
  // Initialize all worker types
  Object.entries(WORKER_TYPES).forEach(([type, meta]) => {
    capacity[type] = {
      type,
      label: meta.label,
      color: meta.color,
      active: 0,
      idle: 0,
      max: limits[type] || meta.defaultLimit,
      utilization: 0
    };
  });

  // Count active and idle workers by type
  workers.forEach(worker => {
    const taskType = worker.task_type;
    if (!taskType || !capacity[taskType]) return;
    
    if (worker.status === 'active') {
      capacity[taskType].active++;
    } else if (worker.status === 'idle') {
      capacity[taskType].idle++;
    }
  });

  // Calculate utilization percentage
  Object.values(capacity).forEach(workerType => {
    if (workerType.max > 0) {
      workerType.utilization = workerType.active / workerType.max;
    }
  });

  return capacity;
};

/**
 * Transform worker data to bullet chart format
 * Each bullet chart shows: [good range | warning range | critical range] + actual bar + target marker
 * 
 * @param {Object} capacityByType - Output from getWorkerCapacityByType
 * @returns {Array} - Array of bullet chart data objects
 */
export const transformForBulletCharts = (capacityByType) => {
  if (!capacityByType || typeof capacityByType !== 'object') {
    return [];
  }

  return Object.values(capacityByType).map(worker => ({
    type: worker.type,
    label: worker.label,
    color: worker.color,
    current: worker.active,
    max: worker.max,
    utilization: worker.utilization,
    
    // Bullet chart ranges (absolute values)
    ranges: {
      good: Math.ceil(worker.max * CAPACITY_RANGES.good),
      warning: Math.ceil(worker.max * CAPACITY_RANGES.warning),
      critical: worker.max
    },
    
    // Status classification
    status: getCapacityStatus(worker.utilization),
    
    // Metadata for tooltips
    meta: {
      active: worker.active,
      idle: worker.idle,
      total: worker.active + worker.idle,
      utilizationPercent: Math.round(worker.utilization * 100),
      availableSlots: Math.max(0, worker.max - worker.active)
    }
  }));
};

/**
 * Determine capacity status based on utilization
 * @param {number} utilization - Utilization ratio (0-1)
 * @returns {string} - 'good' | 'warning' | 'critical'
 */
export const getCapacityStatus = (utilization) => {
  if (utilization >= CAPACITY_RANGES.warning) return 'critical';
  if (utilization >= CAPACITY_RANGES.good) return 'warning';
  return 'good';
};

/**
 * Calculate overall system utilization
 * @param {Object} capacityByType - Output from getWorkerCapacityByType
 * @returns {Object} - Overall metrics
 */
export const calculateOverallUtilization = (capacityByType) => {
  const workers = Object.values(capacityByType);
  
  const totalActive = workers.reduce((sum, w) => sum + w.active, 0);
  const totalMax = workers.reduce((sum, w) => sum + w.max, 0);
  const totalIdle = workers.reduce((sum, w) => sum + w.idle, 0);
  
  return {
    active: totalActive,
    idle: totalIdle,
    max: totalMax,
    utilization: totalMax > 0 ? totalActive / totalMax : 0,
    utilizationPercent: totalMax > 0 ? Math.round((totalActive / totalMax) * 100) : 0,
    availableSlots: Math.max(0, totalMax - totalActive),
    status: getCapacityStatus(totalMax > 0 ? totalActive / totalMax : 0)
  };
};

/**
 * Prepare worker activity timeline data
 * Groups worker events by time bucket (e.g., 5-minute intervals)
 * 
 * @param {Array} workers - Array of workers with started_at timestamps
 * @param {number} hours - How many hours of history to show
 * @param {number} intervalMinutes - Bucket size in minutes
 * @returns {Array} - Timeline data [{timestamp, active, idle, total}]
 */
export const prepareWorkerTimeline = (workers = [], hours = 1, intervalMinutes = 5) => {
  const now = new Date();
  const startTime = new Date(now.getTime() - hours * 60 * 60 * 1000);
  const buckets = [];
  
  // Create time buckets
  const numBuckets = Math.ceil((hours * 60) / intervalMinutes);
  for (let i = 0; i < numBuckets; i++) {
    const timestamp = new Date(startTime.getTime() + i * intervalMinutes * 60 * 1000);
    buckets.push({
      timestamp,
      active: 0,
      idle: 0,
      total: 0
    });
  }
  
  // Fill buckets with worker data
  workers.forEach(worker => {
    if (!worker.started_at) return;
    
    const workerTime = new Date(worker.started_at);
    if (workerTime < startTime || workerTime > now) return;
    
    const bucketIndex = Math.floor((workerTime - startTime) / (intervalMinutes * 60 * 1000));
    if (bucketIndex >= 0 && bucketIndex < buckets.length) {
      buckets[bucketIndex].total++;
      if (worker.status === 'active') {
        buckets[bucketIndex].active++;
      } else if (worker.status === 'idle') {
        buckets[bucketIndex].idle++;
      }
    }
  });
  
  return buckets;
};

/**
 * Generate tooltip HTML for worker bullet chart
 * @param {Object} workerData - Bullet chart data object
 * @returns {string} - HTML string
 */
export const generateWorkerTooltipHTML = (workerData) => {
  const statusEmoji = {
    good: '✅',
    warning: '⚠️',
    critical: '🔴'
  };
  
  return `
    <div style="font-family: system-ui; font-size: 12px;">
      <strong style="font-size: 14px;">${workerData.label} Workers</strong><br/>
      <hr style="margin: 4px 0; border-color: #334155; opacity: 0.3;">
      ${statusEmoji[workerData.status]} Utilización: <strong>${workerData.meta.utilizationPercent}%</strong><br/>
      <br/>
      🟢 Activos: ${workerData.meta.active}<br/>
      ⚪ Idle: ${workerData.meta.idle}<br/>
      🎯 Límite: ${workerData.max}<br/>
      📊 Disponibles: ${workerData.meta.availableSlots}<br/>
      <br/>
      <small style="color: #94a3b8;">
        Good: 0-${workerData.ranges.good} | 
        Warning: ${workerData.ranges.good + 1}-${workerData.ranges.warning} | 
        Critical: ${workerData.ranges.warning + 1}+
      </small>
    </div>
  `;
};

/**
 * Sort workers by priority for display
 * Priority: Critical first, then Warning, then Good
 * 
 * @param {Array} bulletChartData - Array from transformForBulletCharts
 * @returns {Array} - Sorted array
 */
export const sortWorkersByPriority = (bulletChartData) => {
  const priorityOrder = { critical: 0, warning: 1, good: 2 };
  
  return [...bulletChartData].sort((a, b) => {
    const priorityDiff = priorityOrder[a.status] - priorityOrder[b.status];
    if (priorityDiff !== 0) return priorityDiff;
    
    // If same priority, sort by utilization (highest first)
    return b.utilization - a.utilization;
  });
};
