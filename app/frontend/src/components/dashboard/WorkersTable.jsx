/**
 * WorkersTable Component
 * 
 * Interactive table showing worker status with D3.js visualization and coordinated filtering.
 * Click on rows to filter other visualizations by worker.
 */

import React, { useEffect, useState, useMemo, useRef } from 'react';
import * as d3 from 'd3';
import axios from 'axios';
import { useDashboardFilters } from '../hooks/useDashboardFilters.jsx';
import { API_TIMEOUT_MS, API_TIMEOUT_ACTION_MS } from '../../config/apiConfig';
import './WorkersTable.css';

export function WorkersTable({ API_URL, token, refreshTrigger }) {
  const [workers, setWorkers] = useState([]);
  const [analysis, setAnalysis] = useState(null); // NEW: Analysis data for enhanced info
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retrying, setRetrying] = useState(new Set()); // Track which workers are being retried
  const [errorFilter, setErrorFilter] = useState('all'); // NEW: Filter by error type
  const { filters, updateFilter, clearFilter } = useDashboardFilters();
  const chartRef = useRef();

  // Fetch workers data - resilient error handling with smart polling
  useEffect(() => {
    let consecutiveErrors = 0;
    let interval;

    const fetchWorkersStatus = async () => {
      try {
        // Fetch both workers status and analysis data
        const [workersResponse, analysisResponse] = await Promise.allSettled([
          axios.get(`${API_URL}/api/workers/status`, {
            headers: { Authorization: `Bearer ${token}` },
            timeout: API_TIMEOUT_MS
          }),
          axios.get(`${API_URL}/api/dashboard/analysis`, {
            headers: { Authorization: `Bearer ${token}` },
            timeout: API_TIMEOUT_MS
          })
        ]);

        if (workersResponse.status === 'fulfilled') {
          setWorkers(workersResponse.value.data?.workers || []);
        }

        if (analysisResponse.status === 'fulfilled') {
          setAnalysis(analysisResponse.value.data);
        }

        setError(null);
        consecutiveErrors = 0;
      } catch (err) {
        consecutiveErrors++;
        
        if (consecutiveErrors === 1) {
          console.warn('⚠️ WorkersTable: Error fetching workers status');
        }
        
        setError(err.message || 'Error de conexión');
        
        if (consecutiveErrors >= 3 && interval) {
          console.info('🛑 WorkersTable: Auto-refresh disabled due to persistent errors');
          clearInterval(interval);
          interval = null;
        }
      } finally {
        setLoading(false);
      }
    };

    fetchWorkersStatus();
    interval = setInterval(fetchWorkersStatus, 15000);
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [API_URL, token, refreshTrigger]);

  // Enhance workers with analysis data (execution time, stuck status)
  const enhancedWorkers = useMemo(() => {
    if (!Array.isArray(workers)) return [];
    
    if (!analysis || !analysis.workers) return workers;

    // Create a map of worker_id -> analysis data
    const analysisMap = new Map();
    if (analysis.workers.active_list) {
      analysis.workers.active_list.forEach(w => {
        analysisMap.set(w.worker_id, w);
      });
    }
    if (analysis.workers.stuck_list) {
      analysis.workers.stuck_list.forEach(w => {
        analysisMap.set(w.worker_id, { ...w, is_stuck: true });
      });
    }

    // Enhance workers with analysis data
    return workers.map(worker => {
      const analysisData = analysisMap.get(worker.worker_id);
      if (analysisData) {
        return {
          ...worker,
          execution_time_minutes: analysisData.execution_time_minutes,
          is_stuck: analysisData.is_stuck || false,
          timeout_limit: analysisData.timeout_limit,
          progress_percent: analysisData.progress_percent
        };
      }
      return worker;
    });
  }, [workers, analysis]);

  // Filter workers based on global filters and error filter
  const filteredWorkers = useMemo(() => {
    if (!Array.isArray(enhancedWorkers)) return [];
    let result = [...enhancedWorkers];

    if (filters.stage) {
      result = result.filter(w => 
        w.type?.toLowerCase() === filters.stage?.toLowerCase() ||
        w.task_type?.toLowerCase() === filters.stage?.toLowerCase()
      );
    }

    if (filters.status) {
      result = result.filter(w => w.status === filters.status);
    }

    if (filters.workerId) {
      result = result.filter(w => w.worker_id === filters.workerId);
    }

    // NEW: Filter by error type
    if (errorFilter === 'real-errors') {
      result = result.filter(w => 
        w.status === 'error' && 
        w.error_message && 
        !w.error_message.includes('Shutdown ordenado')
      );
    } else if (errorFilter === 'shutdown-errors') {
      result = result.filter(w => 
        w.status === 'error' && 
        w.error_message && 
        w.error_message.includes('Shutdown ordenado')
      );
    } else if (errorFilter === 'stuck') {
      result = result.filter(w => w.is_stuck === true);
    } else if (errorFilter === 'active') {
      result = result.filter(w => w.status === 'active' || w.status === 'started');
    }

    return result;
  }, [enhancedWorkers, filters, errorFilter]);

  // Sort workers: active → idle → others
  const sortedWorkers = useMemo(() => {
    if (!Array.isArray(filteredWorkers)) return [];
    return [...filteredWorkers].sort((a, b) => {
      const statusOrder = { 
        'active': 0, 
        'started': 0, 
        'idle': 1, 
        'assigned': 1,
        'completed': 2,
        'error': 3
      };
      const aOrder = statusOrder[a.status] ?? 4;
      const bOrder = statusOrder[b.status] ?? 4;
      
      if (aOrder !== bOrder) {
        return aOrder - bOrder;
      }
      return (a.worker_number || 0) - (b.worker_number || 0);
    });
  }, [filteredWorkers]);

  // Group by type for mini chart
  const workersByType = useMemo(() => {
    const grouped = {};
    sortedWorkers.forEach(w => {
      const type = w.type || 'Unknown';
      if (!grouped[type]) {
        grouped[type] = { total: 0, active: 0, idle: 0, error: 0 };
      }
      grouped[type].total++;
      if (w.status === 'active' || w.status === 'started') grouped[type].active++;
      else if (w.status === 'idle' || w.status === 'assigned') grouped[type].idle++;
      else if (w.status === 'error') grouped[type].error++;
    });
    return grouped;
  }, [sortedWorkers]);

  // D3 mini bar chart - with safe data handling
  useEffect(() => {
    if (!chartRef.current || Object.keys(workersByType).length === 0) return;

    const width = 300;
    const height = 150;
    const margin = { top: 10, right: 10, bottom: 30, left: 60 };

    d3.select(chartRef.current).selectAll("*").remove();

    const svg = d3.select(chartRef.current)
      .attr('width', width)
      .attr('height', height);

    const data = Object.entries(workersByType).map(([type, stats]) => ({
      type,
      active: stats.active || 0,
      idle: stats.idle || 0,
      error: stats.error || 0,
      total: stats.total || 0
    }));

    // Safety check: ensure all data points have valid numbers
    if (data.length === 0 || data.every(d => d.total === 0)) {
      return; // Skip rendering if no valid data
    }

    const xScale = d3.scaleBand()
      .domain(data.map(d => d.type))
      .range([margin.left, width - margin.right])
      .padding(0.2);

    const maxTotal = d3.max(data, d => d.total) || 1; // Prevent 0 max
    const yScale = d3.scaleLinear()
      .domain([0, maxTotal])
      .range([height - margin.bottom, margin.top]);

    // Stacked bars
    const stack = d3.stack()
      .keys(['active', 'idle', 'error']);

    const series = stack(data);

    const colorScale = {
      active: '#4caf50',
      idle: '#ff9800',
      error: '#f44336'
    };

    svg.selectAll('.bar-group')
      .data(series)
      .join('g')
      .attr('class', 'bar-group')
      .attr('fill', d => colorScale[d.key])
      .selectAll('rect')
      .data(d => d.filter(point => point && point.data)) // Filter out invalid points
      .join('rect')
      .attr('x', d => xScale(d.data.type))
      .attr('y', d => {
        const val = d[1];
        return val !== undefined && !isNaN(val) ? yScale(val) : 0;
      })
      .attr('height', d => {
        const val0 = d[0];
        const val1 = d[1];
        if (val0 === undefined || val1 === undefined || isNaN(val0) || isNaN(val1)) {
          return 0;
        }
        return Math.max(0, yScale(val0) - yScale(val1));
      })
      .attr('width', xScale.bandwidth());

    // X axis
    svg.append('g')
      .attr('transform', `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(xScale))
      .selectAll('text')
      .attr('fill', '#cbd5e1')
      .attr('font-size', '10px')
      .attr('transform', 'rotate(-15)')
      .style('text-anchor', 'end');

    // Y axis
    svg.append('g')
      .attr('transform', `translate(${margin.left},0)`)
      .call(d3.axisLeft(yScale).ticks(5))
      .selectAll('text')
      .attr('fill', '#cbd5e1')
      .attr('font-size', '10px');

  }, [workersByType]);

  const handleRowClick = (worker) => {
    if (filters.workerId === worker.worker_id) {
      clearFilter('workerId');
    } else {
      updateFilter('workerId', worker.worker_id);
    }
  };

  const handleRetryWorker = async (worker, e) => {
    e.stopPropagation(); // Prevent row click
    
    if (!worker.document_id) {
      alert('No se puede reintentar: documento no disponible');
      return;
    }

    setRetrying(prev => new Set(prev).add(worker.worker_id));

    try {
      const response = await axios.post(
        `${API_URL}/api/documents/${worker.document_id}/requeue`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_ACTION_MS
        }
      );

      alert(`✅ ${response.data.message || 'Documento reintentado correctamente'}`);
      
      // Refresh workers list after a short delay
      setTimeout(() => {
        window.location.reload(); // Simple refresh to update the list
      }, 1000);
      
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.join('; ') : JSON.stringify(detail ?? err.message);
      console.error('Error retrying worker:', err);
      alert(`❌ Error al reintentar: ${msg}`);
    } finally {
      setRetrying(prev => {
        const next = new Set(prev);
        next.delete(worker.worker_id);
        return next;
      });
    }
  };

  const handleRetryAllErrors = async (e) => {
    e.stopPropagation();
    
    const errorWorkers = workers.filter(w => w.status === 'error' && w.document_id);
    
    if (errorWorkers.length === 0) {
      alert('No hay workers con errores para reintentar');
      return;
    }

    if (!confirm(`¿Reintentar ${errorWorkers.length} documento(s) con errores?`)) {
      return;
    }

    setRetrying(new Set(errorWorkers.map(w => w.worker_id)));

    try {
      const response = await axios.post(
        `${API_URL}/api/workers/retry-errors`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_ACTION_MS
        }
      );

      alert(`✅ ${response.data.message}\nReintentados: ${response.data.retried_count}`);
      
      if (response.data.errors && response.data.errors.length > 0) {
        console.warn('Algunos documentos tuvieron errores:', response.data.errors);
      }
      
      // Refresh workers list after a short delay
      setTimeout(() => {
        window.location.reload();
      }, 1000);
      
    } catch (err) {
      console.error('Error retrying all errors:', err);
      alert(`❌ Error al reintentar: ${err.response?.data?.detail || err.message}`);
    } finally {
      setRetrying(new Set());
    }
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'active':
      case 'started':
        return 'status-active';
      case 'idle':
      case 'assigned':
        return 'status-idle';
      case 'completed':
        return 'status-completed';
      case 'error':
        return 'status-error';
      default:
        return 'status-unknown';
    }
  };

  if (loading && workers.length === 0) {
    return <div className="workers-table-loading">Cargando workers...</div>;
  }

  return (
    <div className="workers-table-container">
      <div className="workers-table-header">
        <div>
          <h3>🔧 Workers Status</h3>
          <p className="workers-hint">💡 Click en fila para filtrar visualizaciones</p>
          
          {error && (
            <div style={{
              background: '#fff3cd',
              border: '1px solid #ffc107',
              color: '#856404',
              padding: '6px 12px',
              borderRadius: '4px',
              fontSize: '11px',
              marginTop: '6px'
            }}>
              ⚠️ {error}
              {workers.length > 0 && ' - Mostrando últimos datos disponibles'}
            </div>
          )}

          {/* NEW: Error filter dropdown */}
          <div style={{ marginTop: '8px', display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <label style={{ fontSize: '11px', color: '#94a3b8' }}>Filtro:</label>
            <select
              value={errorFilter}
              onChange={(e) => setErrorFilter(e.target.value)}
              style={{
                padding: '4px 8px',
                background: '#1e293b',
                border: '1px solid #334155',
                borderRadius: '4px',
                color: '#f1f5f9',
                fontSize: '11px',
                cursor: 'pointer'
              }}
            >
              <option value="all">Todos</option>
              <option value="active">Activos</option>
              <option value="stuck">Stuck ({'>'}20min)</option>
              <option value="real-errors">Errores Reales</option>
              <option value="shutdown-errors">Errores Shutdown</option>
            </select>
          </div>

          {workers.filter(w => w.status === 'error' && w.document_id).length > 0 && (
            <button
              onClick={handleRetryAllErrors}
              disabled={retrying.size > 0}
              style={{
                marginTop: '8px',
                padding: '6px 12px',
                background: retrying.size > 0 ? '#6b7280' : '#4caf50',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: retrying.size > 0 ? 'not-allowed' : 'pointer',
                fontSize: '11px',
                fontWeight: '600'
              }}
            >
              {retrying.size > 0 ? '⏳ Reintentando...' : `🔄 Reintentar todos los errores (${workers.filter(w => w.status === 'error' && w.document_id).length})`}
            </button>
          )}
        </div>
        <div className="workers-summary-chart">
          <svg ref={chartRef}></svg>
        </div>
      </div>

      <div className="workers-table-wrapper">
        <table className="workers-table">
          <thead>
            <tr>
              <th>Worker ID</th>
              <th>Type</th>
              <th>Status</th>
              <th>Document</th>
              <th>Started</th>
              <th>Duration</th>
              <th>Error</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {!Array.isArray(sortedWorkers) || sortedWorkers.length === 0 ? (
              <tr>
                <td colSpan="8" style={{ textAlign: 'center', color: '#94a3b8' }}>
                  Sin workers activos
                </td>
              </tr>
            ) : (
              sortedWorkers.map((worker, idx) => (
                <tr
                  key={worker.worker_id || idx}
                  className={`worker-row ${filters.workerId === worker.worker_id ? 'selected' : ''} ${worker.status === 'error' ? 'worker-row-error' : ''}`}
                  onClick={() => handleRowClick(worker)}
                >
                  <td className="worker-id">
                    {worker.worker_id?.substring(0, 12)}...
                  </td>
                  <td>
                    <span className={`type-badge type-${worker.type?.toLowerCase()}`}>
                      {worker.type}
                    </span>
                  </td>
                  <td>
                    <span className={`status-badge ${getStatusBadgeClass(worker.status)}`}>
                      {worker.status}
                    </span>
                  </td>
                  <td className="document-name">
                    {worker.document_id ? (
                      <span title={worker.filename}>
                        {worker.filename?.substring(0, 30)}...
                      </span>
                    ) : (
                      <span style={{ color: '#64748b' }}>-</span>
                    )}
                  </td>
                  <td className="timestamp">
                    {worker.started_at ? new Date(worker.started_at).toLocaleTimeString() : '-'}
                  </td>
                  <td className="duration">
                    {worker.execution_time_minutes !== undefined ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span>
                          {Math.floor(worker.execution_time_minutes)}.{Math.floor((worker.execution_time_minutes % 1) * 10)}m
                        </span>
                        {worker.is_stuck && (
                          <span 
                            className="stuck-badge"
                            style={{
                              background: '#ef4444',
                              color: 'white',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              fontSize: '9px',
                              fontWeight: '700'
                            }}
                            title={`Worker stuck: ${worker.execution_time_minutes.toFixed(1)} minutos ejecutándose`}
                          >
                            STUCK
                          </span>
                        )}
                        {worker.progress_percent !== undefined && worker.timeout_limit && (
                          <div 
                            style={{
                              width: '40px',
                              height: '4px',
                              background: '#334155',
                              borderRadius: '2px',
                              overflow: 'hidden',
                              marginLeft: '4px'
                            }}
                            title={`Progreso: ${worker.progress_percent.toFixed(1)}% (timeout: ${worker.timeout_limit}min)`}
                          >
                            <div 
                              style={{
                                width: `${Math.min(100, worker.progress_percent)}%`,
                                height: '100%',
                                background: worker.progress_percent > 80 ? '#ef4444' : worker.progress_percent > 60 ? '#f59e0b' : '#10b981',
                                transition: 'width 0.3s'
                              }}
                            />
                          </div>
                        )}
                      </div>
                    ) : worker.duration ? (
                      `${Math.floor(worker.duration / 60)}m ${worker.duration % 60}s`
                    ) : (
                      '-'
                    )}
                  </td>
                  <td className="error-message">
                    {worker.status === 'error' && worker.error_message ? (
                      <div 
                        className="error-message-container"
                        title={worker.error_message}
                      >
                        <span 
                          className={`error-text ${worker.error_message.includes('Shutdown ordenado') ? 'shutdown-error' : 'real-error'}`}
                        >
                          {worker.error_message.includes('Shutdown ordenado') ? 'ℹ️' : '❌'} {worker.error_message.substring(0, 40)}...
                        </span>
                      </div>
                    ) : (
                      <span style={{ color: '#64748b' }}>-</span>
                    )}
                  </td>
                  <td className="worker-actions">
                    {worker.status === 'error' && worker.document_id ? (
                      <button
                        onClick={(e) => handleRetryWorker(worker, e)}
                        disabled={retrying.has(worker.worker_id)}
                        style={{
                          padding: '4px 8px',
                          background: retrying.has(worker.worker_id) ? '#6b7280' : '#4caf50',
                          color: 'white',
                          border: 'none',
                          borderRadius: '4px',
                          cursor: retrying.has(worker.worker_id) ? 'not-allowed' : 'pointer',
                          fontSize: '10px',
                          fontWeight: '600'
                        }}
                        title="Reintentar este documento"
                      >
                        {retrying.has(worker.worker_id) ? '⏳' : '🔄'}
                      </button>
                    ) : (
                      <span style={{ color: '#64748b' }}>-</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="workers-stats-footer">
        <div className="stat">
          <span className="stat-label">Total:</span>
          <span className="stat-value">{sortedWorkers.length}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Activos:</span>
          <span className="stat-value active">
            {sortedWorkers.filter(w => w.status === 'active' || w.status === 'started').length}
          </span>
        </div>
        <div className="stat">
          <span className="stat-label">Inactivos:</span>
          <span className="stat-value idle">
            {sortedWorkers.filter(w => w.status === 'idle' || w.status === 'assigned').length}
          </span>
        </div>
        <div className="stat">
          <span className="stat-label">Errores:</span>
          <span className="stat-value error">
            {sortedWorkers.filter(w => w.status === 'error').length}
          </span>
        </div>
      </div>
    </div>
  );
}

export default WorkersTable;
