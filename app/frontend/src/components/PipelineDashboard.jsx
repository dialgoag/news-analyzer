import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { DashboardProvider } from './hooks/useDashboardFilters.jsx';
import { API_TIMEOUT_MS } from '../config/apiConfig';
import PipelineSankeyChartWithZoom from './dashboard/PipelineSankeyChartWithZoom';
import { CollapsibleSection } from './dashboard/CollapsibleSection';
import ErrorAnalysisPanel from './dashboard/ErrorAnalysisPanel';
import PipelineAnalysisPanel from './dashboard/PipelineAnalysisPanel';
import StuckWorkersPanel from './dashboard/StuckWorkersPanel';
import DatabaseStatusPanel from './dashboard/DatabaseStatusPanel';
import WorkersTable from './dashboard/WorkersTable';
import DocumentsTableWithGrouping from './dashboard/DocumentsTableWithGrouping';
import './PipelineDashboard.css';

export function PipelineDashboard({ API_URL, token, refreshTrigger }) {
  const [data, setData] = useState(null);
  const [documents, setDocuments] = useState([]); // NEW: Lista de documentos individuales
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
      try {
        const docsResponse = await axios.get(`${API_URL}/api/documents`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_MS
        });
        setDocuments(docsResponse.data?.documents || []);
      } catch (docErr) {
        console.warn('Could not fetch documents list:', docErr);
      }
      setError(null);
    } catch (err) {
      console.error('Error fetching pipeline data:', err);
      setError(err.message || 'Error de conexión');
    } finally {
      setLoading(false);
    }
  }, [API_URL, token]);

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

  return (
    <DashboardProvider>
      <div className="pipeline-container">
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

        <div className="pipeline-dashboard-aux">
          <CollapsibleSection title="Errores" icon="⚠️" defaultCollapsed={false}>
            <ErrorAnalysisPanel API_URL={API_URL} token={token} refreshTrigger={refreshTrigger} />
          </CollapsibleSection>

          <CollapsibleSection title="Análisis de Pipeline" icon="🔄" defaultCollapsed={false}>
            <PipelineAnalysisPanel API_URL={API_URL} token={token} refreshTrigger={refreshTrigger} />
          </CollapsibleSection>

          <CollapsibleSection title="Workers Stuck" icon="⏱️" defaultCollapsed>
            <StuckWorkersPanel API_URL={API_URL} token={token} refreshTrigger={refreshTrigger} />
          </CollapsibleSection>

          <CollapsibleSection title="Estado de Base de Datos" icon="💾" defaultCollapsed>
            <DatabaseStatusPanel API_URL={API_URL} token={token} refreshTrigger={refreshTrigger} embedded />
          </CollapsibleSection>
        </div>

        <div className="visualizations-grid">
          <CollapsibleSection title="Flujo (Sankey)" icon="📊" defaultCollapsed>
            <PipelineSankeyChartWithZoom data={data} documents={documents} />
          </CollapsibleSection>
          <div className="tables-grid-collapsible">
            <CollapsibleSection title="Workers" icon="👷" defaultCollapsed={false}>
              <WorkersTable API_URL={API_URL} token={token} refreshTrigger={refreshTrigger} />
            </CollapsibleSection>
            <CollapsibleSection title="Documentos" icon="📄" defaultCollapsed={false}>
              <DocumentsTableWithGrouping API_URL={API_URL} token={token} refreshTrigger={refreshTrigger} />
            </CollapsibleSection>
          </div>
        </div>
      </div>
    </DashboardProvider>
  );
}

export default PipelineDashboard;
