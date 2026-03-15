import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { DashboardProvider } from './hooks/useDashboardFilters.jsx';
import DashboardFilters from './dashboard/DashboardFilters';
import PipelineSankeyChartWithZoom from './dashboard/PipelineSankeyChartWithZoom'; // NEW: With semantic zoom
import ErrorAnalysisPanel from './dashboard/ErrorAnalysisPanel'; // NEW: Error analysis panel
import PipelineAnalysisPanel from './dashboard/PipelineAnalysisPanel'; // NEW: Pipeline analysis panel
import StuckWorkersPanel from './dashboard/StuckWorkersPanel'; // NEW: Stuck workers panel
import DatabaseStatusPanel from './dashboard/DatabaseStatusPanel'; // NEW: Database status panel
import WorkersTable from './dashboard/WorkersTable';
import DocumentsTableWithGrouping from './dashboard/DocumentsTableWithGrouping'; // NEW: With grouping
import './PipelineDashboard.css';

// Stage colors (constant shared across components)
const stageColors = {
  upload: '#f59e0b',
  ocr: '#3b82f6',
  chunking: '#8b5cf6',
  indexing: '#ec4899',
  insights: '#10b981',
  completed: '#6b7280'
};

export function PipelineDashboard({ API_URL, token, refreshTrigger }) {
  const [data, setData] = useState(null);
  const [documents, setDocuments] = useState([]); // NEW: Lista de documentos individuales
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch pipeline data + documents list
  useEffect(() => {
    const fetchPipelineData = async () => {
      if (!token) return;
      try {
        // Fetch summary
        const summaryResponse = await axios.get(`${API_URL}/api/dashboard/summary`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: 5000
        });
        setData(summaryResponse.data);
        
        // Fetch documents list for individual document tracking
        try {
          const docsResponse = await axios.get(`${API_URL}/api/documents`, {
            headers: { Authorization: `Bearer ${token}` },
            timeout: 5000
          });
          setDocuments(docsResponse.data?.documents || []);
        } catch (docErr) {
          console.warn('Could not fetch documents list:', docErr);
        }
        
        setError(null);
      } catch (err) {
        console.error('Error fetching pipeline data:', err);
        setError(err.message || 'Error de conexión');
        // Keep existing data (don't clear on error)
      } finally {
        setLoading(false);
      }
    };

    fetchPipelineData();
    const interval = setInterval(fetchPipelineData, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, [API_URL, token, refreshTrigger]);

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
          margin: '20px'
        }}>
          ⚠️ Error cargando dashboard: {error}
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
        <div className="pipeline-header">
          <h2>📊 Dashboard Interactivo del Pipeline</h2>
          <p className="pipeline-subtitle">Visualizaciones coordinadas con filtros en tiempo real</p>
          
          {error && (
            <div className="error-banner" style={{
              background: '#fff3cd',
              border: '1px solid #ffc107',
              color: '#856404',
              padding: '8px 12px',
              borderRadius: '4px',
              fontSize: '12px',
              marginTop: '8px'
            }}>
              ⚠️ {error} - Mostrando últimos datos disponibles
            </div>
          )}
        </div>

        {/* Global Filters */}
        <DashboardFilters />

        {/* Error Analysis Panel - NEW */}
        <ErrorAnalysisPanel API_URL={API_URL} token={token} refreshTrigger={refreshTrigger} />

        {/* Pipeline Analysis Panel - NEW */}
        <PipelineAnalysisPanel API_URL={API_URL} token={token} refreshTrigger={refreshTrigger} />

        {/* Stuck Workers Panel - NEW (only shows if there are stuck workers) */}
        <StuckWorkersPanel API_URL={API_URL} token={token} refreshTrigger={refreshTrigger} />

        {/* Database Status Panel - NEW (collapsible) */}
        <DatabaseStatusPanel API_URL={API_URL} token={token} refreshTrigger={refreshTrigger} />

        {/* Coordinated Visualizations */}
        <div className="visualizations-grid">
          {/* Sankey Flow Diagram with Semantic Zoom - Individual document lines (LEFT) */}
          <PipelineSankeyChartWithZoom data={data} documents={documents} />

          {/* Interactive Tables (RIGHT) */}
          <div className="tables-grid">
            <WorkersTable API_URL={API_URL} token={token} refreshTrigger={refreshTrigger} />
            <DocumentsTableWithGrouping API_URL={API_URL} token={token} refreshTrigger={refreshTrigger} />
          </div>
        </div>
      </div>
    </DashboardProvider>
  );
}

export default PipelineDashboard;
