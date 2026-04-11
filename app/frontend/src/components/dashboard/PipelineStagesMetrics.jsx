/**
 * Pipeline Stages Metrics Component
 * 
 * Muestra métricas de performance por stage del pipeline
 * Success rate, duración promedio, total de tareas, errores
 * Usa datos del endpoint /api/orchestrator/pipeline-metrics
 */

import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { 
  ChartBarIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline';
import { 
  fetchPipelineMetrics,
  transformMetricsForDashboard,
  getStageColor
} from '../../services/orchestratorService';
import './PipelineStagesMetrics.css';

export function PipelineStagesMetrics({ API_URL, token, refreshInterval = 30000 }) {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch metrics
  const loadMetrics = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await fetchPipelineMetrics(token);
      const transformed = transformMetricsForDashboard(data);
      setMetrics({ ...data, stages: transformed });
    } catch (err) {
      console.error('[PipelineStagesMetrics] Error fetching metrics:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    loadMetrics();
  }, [token]);

  // Auto-refresh
  useEffect(() => {
    if (refreshInterval <= 0) return;

    const interval = setInterval(loadMetrics, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshInterval, token]);

  // Render loading state
  if (loading && !metrics) {
    return (
      <div className="metrics-panel loading">
        <ArrowPathIcon className="icon-spin" />
        <span>Cargando métricas...</span>
      </div>
    );
  }

  // Render error state
  if (error && !metrics) {
    return (
      <div className="metrics-panel error">
        <XCircleIcon className="icon-error" />
        <span>Error: {error}</span>
      </div>
    );
  }

  // Render empty state
  if (!metrics || !metrics.stages || metrics.stages.length === 0) {
    return (
      <div className="metrics-panel empty">
        <ChartBarIcon className="icon-warning" />
        <span>No hay métricas disponibles</span>
      </div>
    );
  }

  return (
    <div className="metrics-panel">
      {/* Header */}
      <div className="metrics-header">
        <h3 className="metrics-title">
          <ChartBarIcon className="icon-title" />
          Pipeline Performance Metrics
        </h3>
        <button 
          className="refresh-button" 
          onClick={loadMetrics} 
          disabled={loading}
        >
          <ArrowPathIcon className={loading ? 'icon-spin' : ''} />
          {loading ? 'Actualizando...' : 'Actualizar'}
        </button>
      </div>

      {/* Global stats */}
      {metrics.global && (
        <div className="metrics-global-stats">
          <StatCard 
            label="Total Tareas"
            value={metrics.global.total_tasks || 0}
            icon={<ChartBarIcon />}
            color="#3b82f6"
          />
          <StatCard 
            label="Éxitos"
            value={metrics.global.total_completed || 0}
            icon={<CheckCircleIcon />}
            color="#10b981"
          />
          <StatCard 
            label="Errores"
            value={metrics.global.total_errors || 0}
            icon={<XCircleIcon />}
            color="#ef4444"
            highlight={metrics.global.total_errors > 0}
          />
          <StatCard 
            label="Tiempo Promedio"
            value={formatDuration(metrics.global.avg_duration_sec)}
            icon={<ClockIcon />}
            color="#8b5cf6"
          />
        </div>
      )}

      {/* Stages list */}
      <div className="metrics-stages">
        {metrics.stages.map((stage, index) => (
          <StageMetricCard key={index} stage={stage} />
        ))}
      </div>
    </div>
  );
}

PipelineStagesMetrics.propTypes = {
  API_URL: PropTypes.string,
  token: PropTypes.string.isRequired,
  refreshInterval: PropTypes.number,
};

/**
 * Stat Card (global stats)
 */
function StatCard({ label, value, icon, color, highlight }) {
  return (
    <div className={`stat-card ${highlight ? 'highlight' : ''}`}>
      <div className="stat-icon" style={{ color }}>
        {icon}
      </div>
      <div className="stat-content">
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
      </div>
    </div>
  );
}

StatCard.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  icon: PropTypes.element.isRequired,
  color: PropTypes.string.isRequired,
  highlight: PropTypes.bool,
};

/**
 * Stage Metric Card (individual stage)
 */
function StageMetricCard({ stage }) {
  const stageColor = getStageColor(stage.stage);
  const hasErrors = stage.has_errors;

  return (
    <div className={`stage-card ${hasErrors ? 'has-errors' : ''}`}>
      {/* Stage header */}
      <div className="stage-header">
        <div className="stage-name-wrapper">
          <div 
            className="stage-indicator" 
            style={{ backgroundColor: stageColor }}
          />
          <h4 className="stage-name">{stage.stage}</h4>
        </div>
        
        {/* Success rate badge */}
        <div className={`success-rate ${getSuccessRateClass(stage.success_rate_percent)}`}>
          {stage.success_rate_percent}% éxito
        </div>
      </div>

      {/* Stage metrics */}
      <div className="stage-metrics">
        <MetricRow 
          label="Total"
          value={stage.total_tasks}
          color="#94a3b8"
        />
        <MetricRow 
          label="Completadas"
          value={stage.total_completed}
          color="#10b981"
        />
        <MetricRow 
          label="Errores"
          value={stage.total_errors}
          color="#ef4444"
          highlight={stage.total_errors > 0}
        />
        <MetricRow 
          label="Duración Prom."
          value={stage.avg_duration_formatted}
          color="#8b5cf6"
        />
      </div>

      {/* Success rate progress bar */}
      <div className="progress-bar-wrapper">
        <div className="progress-bar-track">
          <div 
            className="progress-bar-fill"
            style={{ 
              width: `${stage.success_rate_percent}%`,
              backgroundColor: getProgressBarColor(stage.success_rate_percent)
            }}
          />
        </div>
        <span className="progress-label">
          {stage.total_completed} / {stage.total_tasks}
        </span>
      </div>
    </div>
  );
}

StageMetricCard.propTypes = {
  stage: PropTypes.shape({
    stage: PropTypes.string.isRequired,
    total_tasks: PropTypes.number.isRequired,
    total_completed: PropTypes.number.isRequired,
    total_errors: PropTypes.number.isRequired,
    success_rate_percent: PropTypes.number.isRequired,
    avg_duration_formatted: PropTypes.string.isRequired,
    has_errors: PropTypes.bool,
  }).isRequired,
};

/**
 * Metric Row (inside stage card)
 */
function MetricRow({ label, value, color, highlight }) {
  return (
    <div className={`metric-row ${highlight ? 'highlight' : ''}`}>
      <span className="metric-label">{label}</span>
      <span className="metric-value" style={{ color }}>
        {value}
      </span>
    </div>
  );
}

MetricRow.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  color: PropTypes.string.isRequired,
  highlight: PropTypes.bool,
};

/**
 * Helper: Get success rate CSS class
 */
function getSuccessRateClass(percent) {
  if (percent >= 95) return 'rate-excellent';
  if (percent >= 80) return 'rate-good';
  if (percent >= 50) return 'rate-warning';
  return 'rate-critical';
}

/**
 * Helper: Get progress bar color
 */
function getProgressBarColor(percent) {
  if (percent >= 95) return '#10b981'; // Green
  if (percent >= 80) return '#3b82f6'; // Blue
  if (percent >= 50) return '#fbbf24'; // Yellow
  return '#ef4444'; // Red
}

/**
 * Helper: Format duration
 */
function formatDuration(seconds) {
  if (!seconds || seconds === 'N/A') return 'N/A';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${Math.round(seconds / 3600)}h`;
}

export default PipelineStagesMetrics;
