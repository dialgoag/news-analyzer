import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import axios from 'axios';
import { ArrowPathIcon } from '@heroicons/react/24/outline';
import { API_TIMEOUT_MS } from '../../config/apiConfig';
import './WorkerLoadCard.css';

const STATUS_LABELS = {
  active: 'Activos',
  idle: 'Idle',
  error: 'Errores'
};

// Using design tokens colors
const STATUS_COLORS = {
  active: '#4caf50',   // --color-active
  idle: '#ff9800',     // --color-pending
  error: '#f44336'     // --color-error
};

function normalizeWorkerList(payload) {
  if (!payload) return [];
  if (Array.isArray(payload.workers)) return payload.workers;
  if (Array.isArray(payload)) return payload;
  return [];
}

export default function WorkerLoadCard({ API_URL, token, refreshTrigger }) {
  const [workers, setWorkers] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const chartRef = useRef(null);
  const mountedRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const fetchSnapshot = useCallback(async () => {
    if (!token) return;
    try {
      const workersResponse = await axios.get(`${API_URL}/api/workers/status`, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: API_TIMEOUT_MS
      });

      if (!mountedRef.current) return;

      const workerList = normalizeWorkerList(workersResponse.data);
      setWorkers(workerList);
      setError(null);

      setLastUpdated(new Date().toISOString());
    } catch (err) {
      if (!mountedRef.current) return;
      console.error('WorkerLoadCard fetch failed', err);
      setError(err.message || 'Error de conexión');
    } finally {
      if (mountedRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [API_URL, token]);

  useEffect(() => {
    if (!token) {
      setWorkers([]);
      setLoading(false);
      return;
    }

    let interval;
    const run = async () => {
      await fetchSnapshot();
    };
    run();
    interval = setInterval(run, 15000);
    return () => {
      clearInterval(interval);
    };
  }, [fetchSnapshot, token, refreshTrigger]);

  const workersByType = useMemo(() => {
    const grouped = {};
    workers.forEach((worker) => {
      const type = worker.type || worker.worker_type || 'Desconocido';
      if (!grouped[type]) {
        grouped[type] = { total: 0, active: 0, idle: 0, error: 0 };
      }
      grouped[type].total += 1;
      if (worker.status === 'active' || worker.status === 'started') {
        grouped[type].active += 1;
      } else if (worker.status === 'idle' || worker.status === 'assigned') {
        grouped[type].idle += 1;
      } else if (worker.status === 'error') {
        grouped[type].error += 1;
      }
    });
    return grouped;
  }, [workers]);

  const summary = useMemo(() => {
    const total = workers.length;
    const active = workers.filter((w) => w.status === 'active' || w.status === 'started').length;
    const idle = workers.filter((w) => w.status === 'idle' || w.status === 'assigned').length;
    const errorCount = workers.filter((w) => w.status === 'error').length;
    const stuck = workers.filter((w) => w.is_stuck).length;
    const insightsActive = workers.filter(
      (w) => w.task_type === 'insights' && (w.status === 'active' || w.status === 'started')
    ).length;
    return { total, active, idle, errorCount, stuck, insightsActive };
  }, [workers]);

  useEffect(() => {
    if (!chartRef.current) return;
    const data = Object.entries(workersByType).map(([type, stats]) => ({
      type,
      active: stats.active,
      idle: stats.idle,
      error: stats.error,
      total: stats.total
    }));

    const width = Math.max(260, data.length * 60 + 60);
    const height = 140;
    const margin = { top: 10, right: 8, bottom: 30, left: 40 };

    const svg = d3.select(chartRef.current);
    svg.selectAll('*').remove();
    svg.attr('width', width).attr('height', height);

    if (!data.length) {
      svg.append('text')
        .attr('x', width / 2)
        .attr('y', height / 2)
        .attr('text-anchor', 'middle')
        .attr('fill', '#94a3b8')
        .text('Sin datos de workers');
      return;
    }

    const xScale = d3.scaleBand()
      .domain(data.map((d) => d.type))
      .range([margin.left, width - margin.right])
      .padding(0.25);

    const maxTotal = d3.max(data, (d) => d.total) || 1;
    const yScale = d3.scaleLinear()
      .domain([0, maxTotal])
      .range([height - margin.bottom, margin.top]);

    const stack = d3.stack().keys(['active', 'idle', 'error']);
    const series = stack(data);

    svg.selectAll('.bar-group')
      .data(series)
      .join('g')
      .attr('class', 'bar-group')
      .attr('fill', (d) => STATUS_COLORS[d.key] || '#cbd5e1')
      .selectAll('rect')
      .data((d) => d)
      .join('rect')
      .attr('x', (d) => xScale(d.data.type))
      .attr('y', (d) => yScale(d[1]))
      .attr('height', (d) => Math.max(0, yScale(d[0]) - yScale(d[1])))
      .attr('width', xScale.bandwidth());

    svg.append('g')
      .attr('transform', `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(xScale))
      .selectAll('text')
      .attr('fill', '#e2e8f0')
      .attr('font-size', '11px')
      .attr('transform', 'rotate(-12)')
      .style('text-anchor', 'end');

    svg.append('g')
      .attr('transform', `translate(${margin.left},0)`)
      .call(d3.axisLeft(yScale).ticks(4))
      .selectAll('text')
      .attr('fill', '#cbd5e1')
      .attr('font-size', '10px');
  }, [workersByType]);

  const handleManualRefresh = async () => {
    setRefreshing(true);
    await fetchSnapshot();
  };

  const lastUpdatedLabel = lastUpdated
    ? new Date(lastUpdated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '—';

  if (loading) {
    return (
      <div className="worker-load-card">
        <p className="worker-load-card__placeholder">Cargando estado de workers…</p>
      </div>
    );
  }

  return (
    <div className="worker-load-card">
      <div className="worker-load-card__header">
        <div>
          <h4>Carga de Workers</h4>
          <p>Distribución activa por tipo y estado</p>
        </div>
        <div className="worker-load-card__actions">
          <span className="timestamp">Actualizado: {lastUpdatedLabel}</span>
          <button 
            type="button" 
            onClick={handleManualRefresh} 
            disabled={refreshing}
            className="refresh-button"
            aria-label="Actualizar datos"
          >
            <ArrowPathIcon className={`refresh-icon ${refreshing ? 'spinning' : ''}`} />
            {refreshing ? 'Actualizando...' : 'Actualizar'}
          </button>
        </div>
      </div>

      {error && (
        <div className="worker-load-card__error" role="alert">
          ⚠️ {error}
        </div>
      )}

      <div className="worker-load-card__chart">
        <svg ref={chartRef} aria-label="Gráfico de carga de workers por tipo" role="img" />
        <div className="worker-load-card__legend" role="list">
          {Object.entries(STATUS_LABELS).map(([key, label]) => (
            <span key={key} role="listitem">
              <i style={{ backgroundColor: STATUS_COLORS[key] }} aria-hidden="true" />
              {label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
