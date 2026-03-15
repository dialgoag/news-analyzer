/**
 * PipelineAnalysisPanel Component
 * 
 * Shows detailed status of each pipeline stage, detects blockers,
 * and identifies documents ready for next stage.
 */

import React, { useEffect, useState } from 'react';
import axios from 'axios';
import './PipelineAnalysisPanel.css';

const stageColors = {
  ocr: '#3b82f6',
  chunking: '#8b5cf6',
  indexing: '#ec4899',
  insights: '#10b981'
};

export function PipelineAnalysisPanel({ API_URL, token, refreshTrigger }) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAnalysis = async () => {
      if (!token) return;
      try {
        setLoading(true);
        const response = await axios.get(`${API_URL}/api/dashboard/analysis`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: 10000
        });
        setAnalysis(response.data);
        setError(null);
      } catch (err) {
        console.error('Error fetching pipeline analysis:', err);
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
    return (
      <div className="pipeline-analysis-panel">
        <div className="panel-loading">Cargando análisis de pipeline...</div>
      </div>
    );
  }

  if (!analysis && error) {
    return (
      <div className="pipeline-analysis-panel">
        <div className="panel-error">⚠️ Error: {error}</div>
      </div>
    );
  }

  if (!analysis || !analysis.pipeline) {
    return null;
  }

  const { stages, total_blockers } = analysis.pipeline;

  return (
    <div className="pipeline-analysis-panel">
      <div className="panel-header">
        <h3>🔄 Análisis de Pipeline</h3>
        {total_blockers > 0 && (
          <span className="blockers-badge">
            ⚠️ {total_blockers} Bloqueo{total_blockers > 1 ? 's' : ''} Detectado{total_blockers > 1 ? 's' : ''}
          </span>
        )}
      </div>

      <div className="pipeline-stages">
        {stages.map((stage, index) => {
          const isBlocked = stage.blockers && stage.blockers.length > 0;
          const hasReady = stage.ready_for_next > 0;
          const totalTasks = stage.pending_tasks + stage.processing_tasks + stage.completed_tasks;
          const completionPercent = totalTasks > 0 
            ? Math.round((stage.completed_tasks / totalTasks) * 100) 
            : 0;

          return (
            <div key={stage.name} className={`stage-card ${isBlocked ? 'blocked' : ''}`}>
              <div className="stage-header">
                <div className="stage-title">
                  <span 
                    className="stage-icon" 
                    style={{ backgroundColor: stageColors[stage.name.toLowerCase()] || '#6b7280' }}
                  >
                    {stage.name.charAt(0)}
                  </span>
                  <div>
                    <div className="stage-name">{stage.name.toUpperCase()}</div>
                    <div className="stage-progress">
                      <div className="progress-bar">
                        <div 
                          className="progress-fill" 
                          style={{ 
                            width: `${completionPercent}%`,
                            backgroundColor: stageColors[stage.name.toLowerCase()] || '#6b7280'
                          }}
                        />
                      </div>
                      <span className="progress-text">{completionPercent}%</span>
                    </div>
                  </div>
                </div>
                <div className="stage-stats">
                  <div className="stat-item">
                    <span className="stat-label">Pendientes</span>
                    <span className="stat-value pending">{stage.pending_tasks}</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Procesando</span>
                    <span className="stat-value processing">{stage.processing_tasks}</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Completados</span>
                    <span className="stat-value completed">{stage.completed_tasks}</span>
                  </div>
                </div>
              </div>

              {hasReady && (
                <div className="ready-indicator">
                  ✅ {stage.ready_for_next} documento{stage.ready_for_next > 1 ? 's' : ''} listo{stage.ready_for_next > 1 ? 's' : ''} para siguiente etapa
                </div>
              )}

              {isBlocked && (
                <div className="blockers-section">
                  <div className="blockers-title">⚠️ Bloqueos detectados:</div>
                  {stage.blockers.map((blocker, idx) => (
                    <div key={idx} className="blocker-item">
                      <div className="blocker-reason">
                        <strong>Razón:</strong> {blocker.reason}
                        {blocker.count > 0 && <span className="blocker-count"> ({blocker.count})</span>}
                      </div>
                      <div className="blocker-solution">
                        <strong>Solución:</strong> {blocker.solution}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {!isBlocked && !hasReady && stage.pending_tasks === 0 && stage.processing_tasks === 0 && (
                <div className="stage-status-message">
                  ✅ Stage funcionando normalmente
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default PipelineAnalysisPanel;
