/**
 * WorkersErrorsInline Component
 * 
 * Compact side-by-side mini widgets for Workers and Errors
 * Replaces large WorkerLoadCard and standalone ErrorAnalysisPanel
 */

import React from 'react';
import { 
  UsersIcon, 
  ExclamationTriangleIcon,
  ArrowPathIcon 
} from '@heroicons/react/24/outline';
import './WorkersErrorsInline.css';

export function WorkersErrorsInline({ 
  workerStats, 
  errorGroups = [],
  onRefresh,
  onExpandErrors,
  refreshing = false 
}) {
  
  const activeWorkers = workerStats?.active || 0;
  const idleWorkers = workerStats?.idle || 0;
  const totalWorkers = activeWorkers + idleWorkers;
  const errorCount = errorGroups.length;
  
  const utilizationPercent = totalWorkers > 0 
    ? Math.round((activeWorkers / totalWorkers) * 100)
    : 0;

  return (
    <div className="workers-errors-inline">
      {/* Workers Mini Widget */}
      <div className="mini-widget workers-widget">
        <div className="mini-widget-header">
          <UsersIcon className="widget-icon" aria-hidden="true" />
          <h4>Workers</h4>
          <button
            className={`refresh-button ${refreshing ? 'refreshing' : ''}`}
            onClick={onRefresh}
            disabled={refreshing}
            aria-label="Refresh workers"
          >
            <ArrowPathIcon className="refresh-icon" />
          </button>
        </div>
        <div className="mini-widget-content">
          <div className="worker-summary">
            <div className="worker-badge worker-badge--active">
              <span className="badge-dot"></span>
              {activeWorkers} activos
            </div>
            <div className="worker-badge worker-badge--idle">
              <span className="badge-dot"></span>
              {idleWorkers} idle
            </div>
          </div>
          <div className="utilization-bar">
            <div className="utilization-bar-track">
              <div 
                className="utilization-bar-fill"
                style={{ width: `${utilizationPercent}%` }}
              />
            </div>
            <span className="utilization-label">{utilizationPercent}% utilización</span>
          </div>
        </div>
      </div>

      {/* Errors Mini Widget */}
      <div className="mini-widget errors-widget">
        <div className="mini-widget-header">
          <ExclamationTriangleIcon className="widget-icon" aria-hidden="true" />
          <h4>Errores</h4>
          {errorCount > 0 && (
            <span className="error-count-badge">{errorCount}</span>
          )}
        </div>
        <div className="mini-widget-content">
          {errorCount === 0 ? (
            <div className="no-errors">
              <svg className="checkmark" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Sin errores detectados
            </div>
          ) : (
            <div className="error-summary">
              {errorGroups.slice(0, 2).map((group, idx) => (
                <div key={idx} className="error-item-mini">
                  <span className="error-item-count">{group.count}</span>
                  <span className="error-item-message">{group.error_message}</span>
                </div>
              ))}
              {errorGroups.length > 2 && (
                <div className="more-errors-hint">
                  +{errorGroups.length - 2} más (ver panel abajo)
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default WorkersErrorsInline;
