/**
 * PipelineStatusTable Component
 * 
 * Compact table view of pipeline stages
 * Replaces large stage cards to save vertical space (~800px reduction)
 */

import React from 'react';
import { 
  CheckCircleIcon, 
  ExclamationTriangleIcon,
  PlayIcon,
  PauseIcon,
  ClockIcon 
} from '@heroicons/react/24/outline';
import './PipelineStatusTable.css';

const STAGE_COLORS = {
  upload: '#ff9800',
  ocr: '#2196f3',
  chunking: '#a78bfa',
  indexing: '#ec4899',
  insights: '#4caf50',
  'indexing insights': '#4dd0e1',
};

export function PipelineStatusTable({ 
  stages, 
  isAdmin = false, 
  onPauseToggle,
  saving = false 
}) {
  
  const getRowClass = (stage) => {
    const classes = ['pipeline-table-row'];
    
    // Highlight bottlenecks
    if (stage.pending_tasks > 20 || stage.processing_tasks > 10) {
      classes.push('has-bottleneck');
    }
    
    // Highlight errors
    if (stage.error_tasks && stage.error_tasks > 0) {
      classes.push('has-errors');
    }
    
    return classes.join(' ');
  };

  const getStatusBadge = (stage) => {
    const { pending_tasks, processing_tasks, error_tasks } = stage;
    
    if (error_tasks > 0) {
      return (
        <span className="status-badge status-badge--error">
          <ExclamationTriangleIcon className="status-icon" />
          {error_tasks} errores
        </span>
      );
    }
    
    if (processing_tasks > 0) {
      return (
        <span className="status-badge status-badge--processing">
          <ClockIcon className="status-icon" />
          Procesando
        </span>
      );
    }
    
    if (pending_tasks > 0) {
      return (
        <span className="status-badge status-badge--pending">
          <ClockIcon className="status-icon" />
          En cola
        </span>
      );
    }
    
    return (
      <span className="status-badge status-badge--ok">
        <CheckCircleIcon className="status-icon" />
        OK
      </span>
    );
  };

  const formatNumber = (num) => {
    if (num >= 1000) return `${(num / 1000).toFixed(1)}k`;
    return num;
  };

  return (
    <div className="pipeline-status-table-container">
      <table className="pipeline-table">
        <thead>
          <tr>
            <th className="col-stage">Stage</th>
            <th className="col-stat">⏳ Pendiente</th>
            <th className="col-stat">🔄 Procesando</th>
            <th className="col-stat">✓ Completado</th>
            <th className="col-stat">❌ Errores</th>
            <th className="col-status">Estado</th>
            {isAdmin && <th className="col-actions">Control</th>}
          </tr>
        </thead>
        <tbody>
          {stages.map((stage) => {
            const colorKey = stage.name.toLowerCase();
            const stageColor = STAGE_COLORS[colorKey] || '#6b7280';
            
            return (
              <tr key={stage.name} className={getRowClass(stage)}>
                <td className="stage-name-cell">
                  <div className="stage-name-wrapper">
                    <span 
                      className="stage-icon" 
                      style={{ backgroundColor: stageColor }}
                      aria-hidden="true"
                    >
                      {stage.name.charAt(0)}
                    </span>
                    <span className="stage-name">{stage.name}</span>
                  </div>
                </td>
                <td className="stat-cell stat-cell--pending">
                  {formatNumber(stage.pending_tasks || 0)}
                </td>
                <td className="stat-cell stat-cell--processing">
                  {formatNumber(stage.processing_tasks || 0)}
                </td>
                <td className="stat-cell stat-cell--done">
                  {formatNumber(stage.completed_tasks || 0)}
                </td>
                <td className="stat-cell stat-cell--error">
                  {formatNumber(stage.error_tasks || 0)}
                </td>
                <td className="status-cell">
                  {getStatusBadge(stage)}
                </td>
                {isAdmin && (
                  <td className="actions-cell">
                    {stage.pauseKey ? (
                      <button
                        className={`pause-toggle ${stage.paused ? 'is-paused' : 'is-running'}`}
                        onClick={() => onPauseToggle(stage.pauseKey, stage.paused)}
                        disabled={saving}
                        title={stage.paused ? 'Reanudar' : 'Pausar'}
                      >
                        {stage.paused ? (
                          <PlayIcon className="toggle-icon" />
                        ) : (
                          <PauseIcon className="toggle-icon" />
                        )}
                      </button>
                    ) : (
                      <span className="no-control">—</span>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default PipelineStatusTable;
