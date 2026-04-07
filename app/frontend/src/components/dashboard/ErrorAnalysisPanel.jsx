/**
 * ErrorAnalysisPanel Component
 * 
 * Displays grouped error analysis with ability to clean and retry errors.
 * Shows real errors vs shutdown errors, error causes, and auto-fix capabilities.
 * Updated with Design System + Heroicons
 */

import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import { 
  ExclamationTriangleIcon, 
  XCircleIcon, 
  InformationCircleIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline';
import { API_TIMEOUT_MS, API_TIMEOUT_ACTION_MS } from '../../config/apiConfig';
import './ErrorAnalysisPanel.css';

export function ErrorAnalysisPanel({ API_URL, token, refreshTrigger }) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [cleaning, setCleaning] = useState(false);
  const lastFetchRef = useRef(0);
  const CACHE_DURATION = 5000; // Cache for 5 seconds to reduce backend load

  // Fetch analysis data with caching
  useEffect(() => {
    const fetchAnalysis = async () => {
      if (!token) return;
      
      // Check cache
      const now = Date.now();
      if (analysis && (now - lastFetchRef.current) < CACHE_DURATION) {
        return; // Use cached data
      }

      try {
        setLoading(true);
        const response = await axios.get(`${API_URL}/api/dashboard/analysis`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_MS
        });
        setAnalysis(response.data);
        setError(null);
        lastFetchRef.current = now;
      } catch (err) {
        console.error('Error fetching analysis:', err);
        setError(err.message || 'Error de conexión');
        // Keep existing analysis on error (don't clear)
      } finally {
        setLoading(false);
      }
    };

    fetchAnalysis();
    const interval = setInterval(fetchAnalysis, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [API_URL, token, refreshTrigger, analysis]);

  const handleRetryAll = async () => {
    if (!confirm(`¿Reintentar todos los ${errors.total_errors} documento(s) con error?`)) {
      return;
    }
    await doRetry();
  };

  const handleRetryGroup = async (errorGroup) => {
    if (!confirm(`¿Reintentar ${errorGroup.count} documento(s) con error "${errorGroup.error_message}"?`)) {
      return;
    }
    await doRetry(errorGroup.document_ids);
  };

  const doRetry = async (documentIds = null) => {
    setCleaning(true);
    try {
      const body = (documentIds && Array.isArray(documentIds) && documentIds.length > 0)
        ? { document_ids: documentIds } : {};
      const response = await axios.post(
        `${API_URL}/api/workers/retry-errors`,
        body,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          timeout: API_TIMEOUT_ACTION_MS
        }
      );
      alert(`✅ ${response.data.message}\nReintentados: ${response.data.retried_count}`);
      setTimeout(() => window.location.reload(), 1000);
    } catch (err) {
      console.error('Error retrying:', err);
      alert(`❌ Error al reintentar: ${err.response?.data?.detail || err.message}`);
    } finally {
      setCleaning(false);
    }
  };

  if (loading && !analysis) {
    return (
      <div className="error-analysis-panel">
        <div className="panel-loading">Cargando análisis de errores...</div>
      </div>
    );
  }

  if (!analysis && error) {
    return (
      <div className="error-analysis-panel">
        <div className="panel-error">
          ⚠️ Error cargando análisis: {error}
        </div>
      </div>
    );
  }

  if (!analysis || !analysis.errors) {
    return null;
  }

  const { errors } = analysis;
  const hasErrors = errors.total_errors > 0;

  return (
    <div className="error-analysis-panel">
      <div className="panel-header">
        <div className="error-summary">
          <span className={`summary-badge ${errors.real_errors > 0 ? 'real-error' : 'no-error'}`}>
            <XCircleIcon className="badge-icon" />
            Errores Reales: {errors.real_errors}
          </span>
          <span className={`summary-badge ${errors.shutdown_errors > 0 ? 'shutdown-error' : 'no-error'}`}>
            <InformationCircleIcon className="badge-icon" />
            Shutdown: {errors.shutdown_errors}
          </span>
          <span className={`summary-badge total`}>
            Total: {errors.total_errors}
          </span>
        </div>
      </div>

      {!hasErrors ? (
        <div className="no-errors-message">
          ✅ No hay errores en el sistema
        </div>
      ) : (
        <>
        <div className="error-actions-retry-all">
          <button
            onClick={handleRetryAll}
            disabled={cleaning}
            className="clean-button retry-all-button"
          >
            <ArrowPathIcon className="button-icon" />
            {cleaning ? 'Reintentando...' : 'Reintentar todos los errores'}
          </button>
        </div>
        <div className="error-groups">
          {errors.groups.map((errorGroup, index) => {
            const isShutdownError = errorGroup.error_message.includes('Shutdown ordenado');
            const severity = isShutdownError ? 'low' : errorGroup.can_auto_fix ? 'medium' : 'high';
            
            const SeverityIcon = isShutdownError 
              ? InformationCircleIcon 
              : errorGroup.can_auto_fix 
                ? ExclamationTriangleIcon 
                : XCircleIcon;

            return (
              <div key={index} className={`error-card severity-${severity}`}>
                <div className="error-card-header">
                  <div className="error-title">
                    <SeverityIcon className="error-icon" />
                    <div>
                      <div className="error-message">{errorGroup.error_message}</div>
                      <div className="error-meta">
                        Stage: <strong>{errorGroup.stage}</strong> • 
                        Cantidad: <strong>{errorGroup.count}</strong>
                      </div>
                    </div>
                  </div>
                  <div className="error-count-badge">{errorGroup.count}</div>
                </div>

                <div className="error-cause">
                  <strong>Causa:</strong> {errorGroup.cause}
                </div>

                {errorGroup.document_ids && errorGroup.document_ids.length > 0 && (
                  <div className="error-documents">
                    <details>
                      <summary>Ver documentos afectados ({errorGroup.document_ids.length})</summary>
                      <ul>
                        {(errorGroup.filenames || []).slice(0, 10).map((filename, idx) => (
                          <li key={idx} title={errorGroup.document_ids[idx]}>
                            {filename || errorGroup.document_ids[idx]}
                          </li>
                        ))}
                        {errorGroup.document_ids.length > 10 && (
                          <li className="more-documents">
                            ... y {errorGroup.document_ids.length - 10} más
                          </li>
                        )}
                      </ul>
                    </details>
                  </div>
                )}

                {(errorGroup.can_auto_fix || !isShutdownError) && (
                  <div className="error-actions">
                    <button
                      onClick={() => handleRetryGroup(errorGroup)}
                      disabled={cleaning}
                      className="clean-button"
                    >
                      <ArrowPathIcon className="button-icon" />
                      {cleaning ? 'Reintentando...' : 'Reintentar este grupo'}
                    </button>
                  </div>
                )}

                {isShutdownError && (
                  <div className="error-note">
                    <InformationCircleIcon className="note-icon" />
                    Este error es esperado después de un shutdown ordenado. No requiere acción.
                  </div>
                )}
              </div>
            );
          })}
        </div>
        </>
      )}
    </div>
  );
}

export default ErrorAnalysisPanel;
