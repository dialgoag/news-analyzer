/**
 * DatabaseStatusPanel Component
 * 
 * Shows status of processing_queue and worker_tasks tables.
 * Detects inconsistencies and orphaned tasks.
 * Collapsible panel for advanced database monitoring.
 */

import React, { useEffect, useState } from 'react';
import axios from 'axios';
import './DatabaseStatusPanel.css';

export function DatabaseStatusPanel({ API_URL, token, refreshTrigger }) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [collapsed, setCollapsed] = useState(true); // Collapsed by default

  useEffect(() => {
    const fetchAnalysis = async () => {
      if (!token) return;
      try {
        setLoading(true);
        const response = await axios.get(`${API_URL}/api/dashboard/analysis`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: 20000
        });
        setAnalysis(response.data);
        setError(null);
      } catch (err) {
        console.error('Error fetching database status:', err);
        setError(err.message || 'Error de conexión');
      } finally {
        setLoading(false);
      }
    };

    fetchAnalysis();
    const interval = setInterval(fetchAnalysis, 30000);
    return () => clearInterval(interval);
  }, [API_URL, token, refreshTrigger]);

  if (loading && !analysis) {
    return null; // Don't show loading, panel is collapsible
  }

  if (!analysis || !analysis.database) {
    return null;
  }

  const { processing_queue, worker_tasks, inconsistencies } = analysis.database;
  const hasIssues = (processing_queue?.orphaned_tasks || 0) > 0 || 
                    (inconsistencies && inconsistencies.length > 0);

  return (
    <div className="database-status-panel">
      <div 
        className="panel-header collapsible"
        onClick={() => setCollapsed(!collapsed)}
      >
        <div className="header-content">
          <h3>💾 Estado de Base de Datos</h3>
          {hasIssues && (
            <span className="issues-badge">
              ⚠️ {processing_queue?.orphaned_tasks || 0} tareas huérfanas
              {inconsistencies && inconsistencies.length > 0 && ` • ${inconsistencies.length} inconsistencias`}
            </span>
          )}
        </div>
        <button className="collapse-button">
          {collapsed ? '▼' : '▲'}
        </button>
      </div>

      {!collapsed && (
        <div className="panel-content">
          {/* Processing Queue Status */}
          <div className="status-section">
            <h4>Processing Queue</h4>
            {processing_queue?.by_type ? (
              <div className="queue-table">
                <table>
                  <thead>
                    <tr>
                      <th>Tipo</th>
                      <th>Pending</th>
                      <th>Processing</th>
                      <th>Completed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(processing_queue.by_type).map(([taskType, statuses]) => (
                      <tr key={taskType}>
                        <td className="task-type">{taskType.toUpperCase()}</td>
                        <td className="stat-pending">{statuses.pending || 0}</td>
                        <td className="stat-processing">{statuses.processing || 0}</td>
                        <td className="stat-completed">{statuses.completed || 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="no-data">Sin datos disponibles</div>
            )}

            {processing_queue?.orphaned_tasks > 0 && (
              <div className="orphaned-warning">
                ⚠️ {processing_queue.orphaned_tasks} tarea{processing_queue.orphaned_tasks > 1 ? 's' : ''} huérfana{processing_queue.orphaned_tasks > 1 ? 's' : ''} 
                (status='processing' sin worker activo)
              </div>
            )}
          </div>

          {/* Worker Tasks Status */}
          <div className="status-section">
            <h4>Worker Tasks</h4>
            {worker_tasks ? (
              <div className="worker-tasks-summary">
                {Object.entries(worker_tasks).map(([status, count]) => (
                  <div key={status} className="status-badge">
                    <span className="status-label">{status}:</span>
                    <span className="status-count">{count}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="no-data">Sin datos disponibles</div>
            )}
          </div>

          {/* Inconsistencies */}
          {inconsistencies && inconsistencies.length > 0 && (
            <div className="status-section">
              <h4>Inconsistencias Detectadas</h4>
              <div className="inconsistencies-list">
                {inconsistencies.map((inc, idx) => (
                  <div key={idx} className={`inconsistency-item severity-${inc.severity || 'low'}`}>
                    <div className="inc-type">
                      <strong>{inc.type}</strong>
                      <span className="inc-count">({inc.count})</span>
                    </div>
                    <div className="inc-description">{inc.description}</div>
                    {inc.can_auto_fix && (
                      <div className="inc-note">
                        ℹ️ Puede corregirse automáticamente
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {!hasIssues && (
            <div className="all-clear">
              ✅ Base de datos en estado correcto
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default DatabaseStatusPanel;
