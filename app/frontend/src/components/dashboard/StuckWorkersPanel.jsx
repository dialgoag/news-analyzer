/**
 * StuckWorkersPanel Component
 * 
 * Displays workers that have been running for more than 20 minutes.
 * Shows progress bars, time remaining, and allows canceling/reprocessing stuck workers.
 */

import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API_TIMEOUT_MS, API_TIMEOUT_ACTION_MS } from '../../config/apiConfig';
import './StuckWorkersPanel.css';

export function StuckWorkersPanel({ API_URL, token, refreshTrigger }) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [canceling, setCanceling] = useState(new Set());

  useEffect(() => {
    const fetchAnalysis = async () => {
      if (!token) return;
      try {
        setLoading(true);
        const response = await axios.get(`${API_URL}/api/dashboard/analysis`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_MS
        });
        setAnalysis(response.data);
        setError(null);
      } catch (err) {
        console.error('Error fetching stuck workers:', err);
        setError(err.message || 'Error de conexión');
      } finally {
        setLoading(false);
      }
    };

    fetchAnalysis();
    const interval = setInterval(fetchAnalysis, 30000);
    return () => clearInterval(interval);
  }, [API_URL, token, refreshTrigger]);

  const handleCancelWorker = async (worker) => {
    if (!confirm(`¿Cancelar y reprocesar worker ${worker.worker_id}?\nDocumento: ${worker.filename || worker.document_id}`)) {
      return;
    }

    setCanceling(prev => new Set(prev).add(worker.worker_id));

    try {
      // Use requeue endpoint to cancel and reprocess
      const response = await axios.post(
        `${API_URL}/api/documents/${worker.document_id}/requeue`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_ACTION_MS
        }
      );

      alert(`✅ ${response.data.message || 'Worker cancelado y documento marcado para reprocesamiento'}`);
      
      // Refresh after a delay
      setTimeout(() => {
        window.location.reload();
      }, 1000);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.join('; ') : JSON.stringify(detail ?? err.message);
      console.error('Error canceling worker:', err);
      alert(`❌ Error al cancelar worker: ${msg}`);
    } finally {
      setCanceling(prev => {
        const next = new Set(prev);
        next.delete(worker.worker_id);
        return next;
      });
    }
  };

  if (loading && !analysis) {
    return null; // Don't show loading, just hide panel
  }

  if (!analysis || !analysis.workers) {
    return null;
  }

  const stuckWorkers = analysis.workers.stuck_list || [];
  const totalStuck = stuckWorkers.length;

  // Don't render if no stuck workers
  if (totalStuck === 0) {
    return null;
  }

  return (
    <div className="stuck-workers-panel">
      <div className="panel-header">
        <h3>⚠️ Workers Stuck ({totalStuck})</h3>
        <span className="alert-badge">
          {totalStuck} worker{totalStuck > 1 ? 's' : ''} ejecutándose más de 20 minutos
        </span>
      </div>

      <div className="stuck-workers-list">
        {stuckWorkers.map((worker, index) => {
          const timeRemaining = worker.timeout_limit - worker.execution_time_minutes;
          const isNearTimeout = timeRemaining < 5;
          const progressColor = isNearTimeout 
            ? '#ef4444' 
            : worker.progress_percent > 60 
              ? '#f59e0b' 
              : '#10b981';

          return (
            <div key={worker.worker_id || index} className="stuck-worker-card">
              <div className="worker-info">
                <div className="worker-header">
                  <div className="worker-id-section">
                    <span className="worker-id">{worker.worker_id}</span>
                    <span className="worker-type-badge">{worker.task_type?.toUpperCase() || 'UNKNOWN'}</span>
                  </div>
                  <div className="worker-time">
                    <span className="time-running">
                      ⏱️ {worker.execution_time_minutes.toFixed(1)} min
                    </span>
                    <span className="time-limit">
                      / {worker.timeout_limit} min
                    </span>
                  </div>
                </div>

                <div className="worker-document">
                  <strong>Documento:</strong> {worker.filename || worker.document_id}
                </div>

                <div className="progress-section">
                  <div className="progress-header">
                    <span>Progreso</span>
                    <span className={`time-remaining ${isNearTimeout ? 'near-timeout' : ''}`}>
                      {timeRemaining > 0 
                        ? `${timeRemaining.toFixed(1)} min restantes`
                        : '⏰ TIMEOUT'}
                    </span>
                  </div>
                  <div className="progress-bar-container">
                    <div 
                      className="progress-bar-fill"
                      style={{
                        width: `${Math.min(100, worker.progress_percent)}%`,
                        backgroundColor: progressColor
                      }}
                    />
                    <div className="progress-bar-bg" />
                  </div>
                  <div className="progress-percent">
                    {worker.progress_percent.toFixed(1)}% completado
                  </div>
                </div>
              </div>

              <div className="worker-actions">
                <button
                  onClick={() => handleCancelWorker(worker)}
                  disabled={canceling.has(worker.worker_id)}
                  className="cancel-button"
                >
                  {canceling.has(worker.worker_id) ? '⏳ Cancelando...' : '🛑 Cancelar y Reprocesar'}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default StuckWorkersPanel;
