/**
 * ExpiredInsightsPanel Component
 * 
 * Shows insights that exceeded max retries with FULL journey details.
 * Features:
 * - Expandable rows showing complete insight journey
 * - Original news text
 * - OCR corrections (if any)
 * - Retry history
 * - Generated insights (if any)
 * - Pipeline stage status
 */

import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { 
  ExclamationTriangleIcon,
  ClockIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  DocumentTextIcon,
  CheckCircleIcon,
  XCircleIcon
} from '@heroicons/react/24/outline';
import { API_TIMEOUT_MS } from '../../config/apiConfig';
import './ExpiredInsightsPanel.css';

export function ExpiredInsightsPanel({ API_URL, token, refreshTrigger }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedRows, setExpandedRows] = useState(new Set());
  const [detailsCache, setDetailsCache] = useState({});
  const [loadingDetails, setLoadingDetails] = useState({});

  useEffect(() => {
    const fetchExpiredInsights = async () => {
      if (!token) return;

      try {
        setLoading(true);
        const response = await axios.get(`${API_URL}/api/dashboard/expired-insights`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_MS,
          params: { max_retries: 3 }
        });
        setData(response.data);
        setError(null);
      } catch (err) {
        console.error('Error fetching expired insights:', err);
        setError(err.message || 'Error de conexión');
      } finally {
        setLoading(false);
      }
    };

    fetchExpiredInsights();
  }, [API_URL, token, refreshTrigger]);

  const fetchInsightDetails = async (newsItemId) => {
    if (detailsCache[newsItemId]) {
      return; // Already loaded
    }

    setLoadingDetails(prev => ({ ...prev, [newsItemId]: true }));

    try {
      const response = await axios.get(
        `${API_URL}/api/dashboard/insight-detail/${newsItemId}`,
        {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_MS
        }
      );
      setDetailsCache(prev => ({ ...prev, [newsItemId]: response.data }));
    } catch (err) {
      console.error(`Error fetching details for ${newsItemId}:`, err);
      setDetailsCache(prev => ({ 
        ...prev, 
        [newsItemId]: { error: err.message || 'Error loading details' }
      }));
    } finally {
      setLoadingDetails(prev => ({ ...prev, [newsItemId]: false }));
    }
  };

  const toggleRow = async (newsItemId) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(newsItemId)) {
      newExpanded.delete(newsItemId);
    } else {
      newExpanded.add(newsItemId);
      // Fetch details if not already loaded
      if (!detailsCache[newsItemId]) {
        await fetchInsightDetails(newsItemId);
      }
    }
    setExpandedRows(newExpanded);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    const date = new Date(dateStr);
    return date.toLocaleString('es-ES', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const truncate = (str, maxLength = 60) => {
    if (!str) return '—';
    return str.length > maxLength ? `${str.substring(0, maxLength)}...` : str;
  };

  if (loading && !data) {
    return (
      <div className="expired-insights-panel">
        <div className="panel-loading">Cargando insights expirados...</div>
      </div>
    );
  }

  if (!data && error) {
    return (
      <div className="expired-insights-panel">
        <div className="panel-error">
          ⚠️ Error cargando datos: {error}
        </div>
      </div>
    );
  }

  if (!data || data.total === 0) {
    return (
      <div className="expired-insights-panel">
        <div className="no-expired-message">
          ✅ No hay insights expirados (todos dentro del límite de {data?.max_retries || 3} reintentos)
        </div>
      </div>
    );
  }

  return (
    <div className="expired-insights-panel">
      <div className="panel-header">
        <div className="header-info">
          <ExclamationTriangleIcon className="header-icon" />
          <span className="header-title">
            {data.total} insight{data.total !== 1 ? 's' : ''} excedieron el límite de {data.max_retries} reintentos
          </span>
        </div>
      </div>

      <div className="expired-table-container">
        <table className="expired-table">
          <thead>
            <tr>
              <th style={{ width: '40px' }}></th>
              <th>Documento</th>
              <th>Item</th>
              <th>Razón del Error</th>
              <th>Reintentos</th>
              <th>Última Actualización</th>
            </tr>
          </thead>
          <tbody>
            {data.insights.map((insight, index) => {
              const newsItemId = insight.news_item_id;
              const isExpanded = expandedRows.has(newsItemId);
              const details = detailsCache[newsItemId];
              const isLoadingDetails = loadingDetails[newsItemId];

              return (
                <React.Fragment key={newsItemId || index}>
                  {/* Main Row */}
                  <tr 
                    className={`expired-row ${isExpanded ? 'expanded' : ''}`}
                    onClick={() => toggleRow(newsItemId)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td className="expand-cell">
                      {isExpanded ? (
                        <ChevronDownIcon style={{ width: 16, height: 16 }} />
                      ) : (
                        <ChevronRightIcon style={{ width: 16, height: 16 }} />
                      )}
                    </td>
                    <td className="filename-cell" title={insight.filename || insight.document_id}>
                      {truncate(insight.filename || insight.document_id, 40)}
                    </td>
                    <td className="item-index-cell">
                      #{insight.item_index}
                    </td>
                    <td className="error-message-cell" title={insight.error_message}>
                      <span className="error-message-text">
                        {truncate(insight.error_message, 80)}
                      </span>
                    </td>
                    <td className="retry-count-cell">
                      <span className="retry-badge">
                        <ClockIcon className="retry-icon" />
                        {insight.retry_count}
                      </span>
                    </td>
                    <td className="updated-at-cell">
                      {formatDate(insight.updated_at)}
                    </td>
                  </tr>

                  {/* Expanded Details Row */}
                  {isExpanded && (
                    <tr className="details-row">
                      <td colSpan="6">
                        <div className="details-container">
                          {isLoadingDetails ? (
                            <div className="details-loading">
                              Cargando detalles...
                            </div>
                          ) : details?.error ? (
                            <div className="details-error">
                              ⚠️ Error cargando detalles: {details.error}
                            </div>
                          ) : details ? (
                            <div className="details-content">
                              {/* Status Summary */}
                              <div className="detail-section detail-summary">
                                <h4>📊 Resumen del Insight</h4>
                                <div className="summary-grid">
                                  <div className="summary-item">
                                    <span className="summary-label">Estado:</span>
                                    <span className={`status-badge status-${details.insight?.status || 'unknown'}`}>
                                      {details.insight?.status || 'unknown'}
                                    </span>
                                  </div>
                                  <div className="summary-item">
                                    <span className="summary-label">Longitud Contenido:</span>
                                    <span className={details.is_short_content ? 'text-warning' : ''}>
                                      {details.content_length} chars
                                      {details.is_short_content && ' (⚠️ corto)'}
                                    </span>
                                  </div>
                                  <div className="summary-item">
                                    <span className="summary-label">Reintentos:</span>
                                    <span>{details.insight?.retry_count || 0} / {data.max_retries}</span>
                                  </div>
                                  <div className="summary-item">
                                    <span className="summary-label">Creado:</span>
                                    <span>{formatDate(details.created_at)}</span>
                                  </div>
                                </div>
                              </div>

                              {/* OCR Validation Status */}
                              {details.ocr_validation?.validated !== undefined && (
                                <div className="detail-section detail-ocr">
                                  <h4>
                                    {details.ocr_validation.validated ? (
                                      <><CheckCircleIcon style={{ width: 16, height: 16, color: '#22c55e' }} /> Validación OCR</>
                                    ) : (
                                      <><XCircleIcon style={{ width: 16, height: 16, color: '#ef4444' }} /> Validación OCR Fallida</>
                                    )}
                                  </h4>
                                  {details.ocr_validation.reason && (
                                    <div className="ocr-reason">
                                      <strong>Razón:</strong> {details.ocr_validation.reason}
                                    </div>
                                  )}
                                  {details.insight?.error_message && details.insight.error_message.includes('OCR validation') && (
                                    <div className="ocr-error">
                                      <strong>Error:</strong> {details.insight.error_message}
                                    </div>
                                  )}
                                </div>
                              )}

                              {/* Original Text */}
                              <div className="detail-section detail-text">
                                <h4>
                                  <DocumentTextIcon style={{ width: 16, height: 16 }} /> Texto Original
                                </h4>
                                <div className="detail-title">
                                  <strong>Título:</strong> {details.title}
                                </div>
                                {details.content ? (
                                  <div className="text-content">
                                    <pre>{details.content}</pre>
                                  </div>
                                ) : (
                                  <div className="text-empty">
                                    ⚠️ Sin contenido disponible (no se recuperaron chunks de Qdrant)
                                  </div>
                                )}
                              </div>

                              {/* Error History */}
                              {details.insight?.error_message && (
                                <div className="detail-section detail-errors">
                                  <h4>❌ Historial de Errores</h4>
                                  <div className="error-history">
                                    <div className="error-item">
                                      <span className="error-timestamp">{formatDate(details.insight.updated_at)}</span>
                                      <span className="error-text">{details.insight.error_message}</span>
                                    </div>
                                  </div>
                                </div>
                              )}

                              {/* Generated Insights (if any) */}
                              {details.insight?.content && (
                                <div className="detail-section detail-insights">
                                  <h4>💡 Insights Generados</h4>
                                  <div className="insight-metadata">
                                    <span className="insight-source">
                                      <strong>Fuente LLM:</strong> {details.insight.llm_source || 'N/A'}
                                    </span>
                                    <span className="insight-date">
                                      <strong>Generado:</strong> {formatDate(details.insight.created_at)}
                                    </span>
                                  </div>
                                  <div className="insight-content">
                                    <pre>{details.insight.content}</pre>
                                  </div>
                                </div>
                              )}

                              {/* Pipeline Stage Info */}
                              <div className="detail-section detail-pipeline">
                                <h4>🔄 Estado del Pipeline</h4>
                                <div className="pipeline-info">
                                  <div className="pipeline-item">
                                    <span>Etapa actual:</span>
                                    <span className="badge">{details.pipeline_stage}</span>
                                  </div>
                                  <div className="pipeline-item">
                                    <span>Document ID:</span>
                                    <span className="mono-text">{truncate(details.document_id, 50)}</span>
                                  </div>
                                  <div className="pipeline-item">
                                    <span>News Item ID:</span>
                                    <span className="mono-text">{truncate(details.news_item_id, 50)}</span>
                                  </div>
                                </div>
                              </div>
                            </div>
                          ) : (
                            <div className="details-loading">
                              Cargando detalles...
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="panel-footer">
        <span className="footer-note">
          💡 Click en cualquier fila para ver el journey completo del insight (texto original, errores, correcciones OCR, etc.)
        </span>
      </div>
    </div>
  );
}

export default ExpiredInsightsPanel;
