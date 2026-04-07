import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { 
  ExclamationTriangleIcon,
  ArrowPathIcon,
  ClockIcon,
  CircleStackIcon,
  MapIcon,
  ChartBarIcon,
  UsersIcon
} from '@heroicons/react/24/outline';
import { DashboardProvider } from './hooks/useDashboardFilters.jsx';
import { API_TIMEOUT_MS } from '../config/apiConfig';
import ParallelPipelineCoordinates from './dashboard/ParallelPipelineCoordinates';
import { CollapsibleSection } from './dashboard/CollapsibleSection';
import ErrorAnalysisPanel from './dashboard/ErrorAnalysisPanel';
import PipelineAnalysisPanel from './dashboard/PipelineAnalysisPanel';
import StuckWorkersPanel from './dashboard/StuckWorkersPanel';
import DatabaseStatusPanel from './dashboard/DatabaseStatusPanel';
import WorkerLoadCard from './dashboard/WorkerLoadCard';
import PipelineSummaryCard from './dashboard/PipelineSummaryCard';
import KPIsInline from './dashboard/KPIsInline';
import PipelineStatusTable from './dashboard/PipelineStatusTable';
import './PipelineDashboard.css';

export function PipelineDashboard({ API_URL, token, refreshTrigger, isAdmin = false }) {
  const [data, setData] = useState(null);
  const [documents, setDocuments] = useState([]); // NEW: Lista de documentos individuales
  const [parallelData, setParallelData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // New states for compact components
  const [analysisData, setAnalysisData] = useState(null);
  const [workerStats, setWorkerStats] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchPipelineData = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      setError(null);
      const summaryResponse = await axios.get(`${API_URL}/api/dashboard/summary`, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: API_TIMEOUT_MS
      });
      setData(summaryResponse.data);

      const [docsResponse, parallelResponse, analysisResponse, workersResponse] = await Promise.allSettled([
        axios.get(`${API_URL}/api/documents`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_MS
        }),
        axios.get(`${API_URL}/api/dashboard/parallel-data`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_MS
        }),
        axios.get(`${API_URL}/api/dashboard/analysis`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_MS
        }),
        axios.get(`${API_URL}/api/workers/status`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_MS
        })
      ]);

      if (docsResponse.status === 'fulfilled') {
        setDocuments(docsResponse.value.data?.documents || []);
      } else {
        console.warn('Could not fetch documents list:', docsResponse.reason);
      }

      if (parallelResponse.status === 'fulfilled') {
        setParallelData(parallelResponse.value.data || null);
      } else {
        console.warn('Could not fetch parallel data:', parallelResponse.reason);
      }
      
      if (analysisResponse.status === 'fulfilled') {
        setAnalysisData(analysisResponse.value.data || null);
      } else {
        console.warn('Could not fetch analysis data:', analysisResponse.reason);
      }
      
      if (workersResponse.status === 'fulfilled') {
        const workers = workersResponse.value.data?.workers || [];
        const active = workers.filter(w => w.status === 'active').length;
        const idle = workers.filter(w => w.status === 'idle').length;
        setWorkerStats({ active, idle, workers });
      } else {
        console.warn('Could not fetch workers data:', workersResponse.reason);
      }
      
      setError(null);
    } catch (err) {
      console.error('Error fetching pipeline data:', err);
      setError(err.message || 'Error de conexión');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [API_URL, token]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    fetchPipelineData();
  }, [fetchPipelineData]);

  useEffect(() => {
    fetchPipelineData();
    const interval = setInterval(fetchPipelineData, 20000);
    return () => clearInterval(interval);
  }, [fetchPipelineData, refreshTrigger]);

  if (loading && !data) {
    return <div className="pipeline-container"><p>Loading pipeline data...</p></div>;
  }

  if (!data && error) {
    return (
      <div className="pipeline-container">
        <div className="error-banner" style={{
          background: '#fff3cd',
          border: '1px solid #ffc107',
          color: '#856404',
          padding: '12px 16px',
          borderRadius: '4px',
          margin: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px'
        }}>
          <div>⚠️ Error cargando dashboard: {error}</div>
          <div style={{ fontSize: '12px', color: '#666' }}>
            Para entornos lentos, aumenta VITE_API_TIMEOUT_MS (ej. 120000).
          </div>
          <button
            onClick={() => fetchPipelineData()}
            style={{
              alignSelf: 'flex-start',
              padding: '8px 16px',
              background: '#f59e0b',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: '600'
            }}
          >
            🔄 Reintentar
          </button>
        </div>
      </div>
    );
  }

  if (!data) {
    return <div className="pipeline-container"><p>No data available</p></div>;
  }

  // Safe access with defaults to prevent "missing: 0" errors
  const files = data.files || { total: 0, completed: 0, processing: 0, errors: 0, percentage_done: 0 };
  const newsItems = data.news_items || { total: 0, done: 0, pending: 0, errors: 0, percentage_done: 0 };
  const chunks = data.chunks || { total: 0, done: 0, pending: 0, errors: 0, percentage_done: 0 };
  const ocrData = data.ocr || { total: 0, successful: 0, errors: 0, percentage_success: 0 };
  const chunkingData = data.chunking || { total_chunks: 0, indexed: 0, pending: 0, errors: 0, percentage_indexed: 0 };
  const indexingData = data.indexing || { total: 0, active: 0, pending: 0, errors: 0, percentage_indexed: 0 };
  const insightsData = data.insights || { total: 0, done: 0, pending: 0, errors: 0, percentage_done: 0, eta_seconds: 0, parallel_workers: 0 };
  
  // Prepare data for compact components
  const kpiStats = {
    total_docs: files.total || 0,
    total_news: newsItems.total || 0,
    total_insights: insightsData.total || 0,
    total_errors: (files.errors || 0) + (newsItems.errors || 0) + (insightsData.errors || 0)
  };
  
  const errorGroups = analysisData?.errors?.groups || [];

  return (
    <DashboardProvider>
      <div className="pipeline-container pipeline-container--compact">
        {error && (
          <div
            className="error-banner pipeline-dashboard-error-banner"
            style={{
              background: '#fff3cd',
              border: '1px solid #ffc107',
              color: '#856404',
              padding: '6px 10px',
              borderRadius: '4px',
              fontSize: '11px',
              flexShrink: 0
            }}
          >
            ⚠️ {error} — mostrando últimos datos (refresh 20s)
          </div>
        )}
        
        {/* NEW: Compact KPIs at top */}
        <KPIsInline stats={kpiStats} />
        
        {/* NEW: Compact Pipeline Table */}
        {analysisData?.pipeline?.stages && (
          <PipelineStatusTable 
            stages={analysisData.pipeline.stages}
            isAdmin={isAdmin}
            onPauseToggle={(stageKey, paused) => {
              console.log('Pause toggle:', stageKey, paused);
              // TODO: Implement pause toggle API call
            }}
          />
        )}
        
        {/* NEW: Workers Status */}
        <div className="workers-inline-container">
          <div className="mini-widget workers-widget">
            <div className="mini-widget-header">
              <UsersIcon className="widget-icon" aria-hidden="true" />
              <h4>Workers</h4>
              <button
                className={`refresh-button ${refreshing ? 'refreshing' : ''}`}
                onClick={handleRefresh}
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
                  {workerStats?.active || 0} activos
                </div>
                <div className="worker-badge worker-badge--idle">
                  <span className="badge-dot"></span>
                  {workerStats?.idle || 0} idle
                </div>
              </div>
              <div className="utilization-bar">
                <div className="utilization-bar-track">
                  <div 
                    className="utilization-bar-fill"
                    style={{ width: `${workerStats ? Math.round((workerStats.active / (workerStats.active + workerStats.idle)) * 100) : 0}%` }}
                  />
                </div>
                <span className="utilization-label">
                  {workerStats ? Math.round((workerStats.active / (workerStats.active + workerStats.idle)) * 100) : 0}% utilización
                </span>
              </div>
            </div>
          </div>
        </div>
        
        {/* Full Error Panel (always visible but collapsible) */}
        <CollapsibleSection 
          title="Análisis Detallado de Errores" 
          icon={ExclamationTriangleIcon} 
          priority="high"
          defaultCollapsed={false}
        >
          <ErrorAnalysisPanel API_URL={API_URL} token={token} refreshTrigger={refreshTrigger} />
        </CollapsibleSection>
        
        {/* Coordenadas Paralelas (improved) */}
        <ParallelPipelineCoordinates data={parallelData} documents={documents} />
        
        {/* OLD panels as collapsible fallback */}
        <div className="pipeline-dashboard-aux pipeline-dashboard-aux--collapsed">
          <CollapsibleSection 
            title="Workers Stuck" 
            icon={ClockIcon}
            priority="normal"
            defaultCollapsed
          >
            <StuckWorkersPanel API_URL={API_URL} token={token} refreshTrigger={refreshTrigger} />
          </CollapsibleSection>

          <CollapsibleSection 
            title="Estado de Base de Datos" 
            icon={CircleStackIcon}
            priority="low"
            defaultCollapsed
          >
            <DatabaseStatusPanel API_URL={API_URL} token={token} refreshTrigger={refreshTrigger} embedded />
          </CollapsibleSection>
        </div>
      </div>
    </DashboardProvider>
  );
}

export default PipelineDashboard;
