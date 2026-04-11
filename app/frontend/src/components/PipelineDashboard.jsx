/**
 * PipelineDashboard Component
 * 
 * Redesigned dashboard using visual analytics framework
 * Integrates all new components: KPIs, Workers, Errors, Flow
 * 
 * Architecture: 7-section operational dashboard pattern
 */

import React, { useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import { 
  ArrowPathIcon,
  ClockIcon,
  ChartBarIcon,
  UsersIcon,
  ExclamationTriangleIcon,
  MapIcon,
  CircleStackIcon,
  PlayIcon,
  PauseIcon
} from '@heroicons/react/24/outline';
import axios from 'axios';
import { DashboardProvider } from './hooks/useDashboardFilters.jsx';
import { useDashboardData } from '../hooks/useDashboardData.jsx';
import { CollapsibleSection } from './dashboard/CollapsibleSection';
import KPIRow from './dashboard/kpis/KPIRow';
import WorkerStatusPanel from './dashboard/workers/WorkerStatusPanel';
import ErrorAnalysisPanelV2 from './dashboard/errors/ErrorAnalysisPanelV2';
import PipelineFlowPanel from './dashboard/flow/PipelineFlowPanel';
import PipelineStatusTable from './dashboard/PipelineStatusTable';
import ExpiredInsightsPanel from './dashboard/ExpiredInsightsPanel';
import DatabaseStatusPanel from './dashboard/DatabaseStatusPanel';
import DocumentTimelinePanel from './dashboard/DocumentTimelinePanel';
import PipelineStagesMetrics from './dashboard/PipelineStagesMetrics';
import { API_TIMEOUT_MS } from '../config/apiConfig';
import './PipelineDashboard.css';

const REFRESH_INTERVALS = [
  { value: 0, label: 'Pausado' },
  { value: 5000, label: '5s' },
  { value: 10000, label: '10s' },
  { value: 20000, label: '20s' },
  { value: 60000, label: '1min' },
  { value: 300000, label: '5min' }
];

const getStoredRefreshInterval = () => {
  try {
    const stored = localStorage.getItem('dashboardRefreshInterval');
    return stored ? parseInt(stored, 10) : 20000;
  } catch {
    return 20000;
  }
};

export function PipelineDashboard({ API_URL, token, refreshTrigger, isAdmin = false }) {
  const [refreshInterval, setRefreshInterval] = useState(getStoredRefreshInterval);
  const [selectedDocumentId, setSelectedDocumentId] = useState(null);
  const [documentSearchQuery, setDocumentSearchQuery] = useState('');

  // Use centralized data hook
  const { data, loading, error, refreshing, refetch } = useDashboardData(
    API_URL,
    token,
    refreshInterval,
    refreshTrigger
  );

  // Handle pause/resume for individual stage
  const handlePauseToggle = useCallback(async (stageKey, currentlyPaused) => {
    if (!token) {
      alert('Error: No estás autenticado. Por favor, inicia sesión nuevamente.');
      return;
    }
    
    const newState = !currentlyPaused;
    console.log(`[PauseToggle] ${stageKey}: ${currentlyPaused} → ${newState}`);
    
    // Backend expects: { "pause_steps": { "ocr": true, ... } }
    const payload = {
      pause_steps: {
        [stageKey]: newState
      }
    };
    
    try {
      console.log('[PauseToggle] Sending request:', payload);
      const response = await axios.put(
        `${API_URL}/api/admin/insights-pipeline`,
        payload,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          timeout: API_TIMEOUT_MS
        }
      );
      console.log('[PauseToggle] Success:', response.data);
      
      // Force immediate refresh
      console.log('[PauseToggle] Forcing refresh...');
      await refetch();
      
      // Show success feedback
      console.log('[PauseToggle] Refresh complete');
    } catch (err) {
      console.error('[PauseToggle] Error:', err);
      const errorMsg = err.response?.data?.detail || err.message;
      alert(`Error al pausar/reanudar: ${errorMsg}`);
    }
  }, [API_URL, token, refetch]);

  // Handle pause ALL stages
  const handlePauseAll = useCallback(async () => {
    if (!token) {
      alert('Error: No estás autenticado. Por favor, inicia sesión nuevamente.');
      return;
    }
    
    if (!data?.pipeline?.stages) return;
    
    console.log('[PauseAll] Pausing all stages');
    
    // Backend expects: { "pause_all": true }
    const payload = { pause_all: true };
    
    try {
      console.log('[PauseAll] Sending request:', payload);
      const response = await axios.put(
        `${API_URL}/api/admin/insights-pipeline`,
        payload,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          timeout: API_TIMEOUT_MS
        }
      );
      console.log('[PauseAll] Success:', response.data);
      
      // Force immediate refresh
      await refetch();
    } catch (err) {
      console.error('[PauseAll] Error:', err);
      const errorMsg = err.response?.data?.detail || err.message;
      alert(`Error al pausar todo: ${errorMsg}`);
    }
  }, [API_URL, token, data, refetch]);

  // Handle resume ALL stages
  const handleResumeAll = useCallback(async () => {
    if (!token) {
      alert('Error: No estás autenticado. Por favor, inicia sesión nuevamente.');
      return;
    }
    
    if (!data?.pipeline?.stages) return;
    
    console.log('[ResumeAll] Resuming all stages');
    
    // Backend expects: { "resume_all": true }
    const payload = { resume_all: true };
    
    try {
      console.log('[ResumeAll] Sending request:', payload);
      const response = await axios.put(
        `${API_URL}/api/admin/insights-pipeline`,
        payload,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          timeout: API_TIMEOUT_MS
        }
      );
      console.log('[ResumeAll] Success:', response.data);
      
      // Force immediate refresh
      await refetch();
    } catch (err) {
      console.error('[ResumeAll] Error:', err);
      const errorMsg = err.response?.data?.detail || err.message;
      alert(`Error al reanudar todo: ${errorMsg}`);
    }
  }, [API_URL, token, data, refetch]);

  const handleRefreshIntervalChange = (e) => {
    const newInterval = parseInt(e.target.value, 10);
    setRefreshInterval(newInterval);
    try {
      localStorage.setItem('dashboardRefreshInterval', newInterval.toString());
    } catch (err) {
      console.warn('Could not save refresh interval:', err);
    }
  };

  // Loading state
  if (loading && !data) {
    return (
      <div className="pipeline-dashboard-v2">
        <div className="dashboard-loading">
          <p>⏳ Loading dashboard data...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (!data && error) {
    return (
      <div className="pipeline-dashboard-v2">
        <div className="dashboard-error">
          <h3>⚠️ Error loading dashboard</h3>
          <p>{error}</p>
          <button className="retry-button" onClick={refetch}>
            🔄 Retry
          </button>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="pipeline-dashboard-v2">
        <div className="dashboard-empty">
          <p>No data available</p>
        </div>
      </div>
    );
  }

  return (
    <DashboardProvider>
      <div className="pipeline-dashboard" data-section="dashboard-root">
        {/* [1. HEADER] - Title + Refresh Control */}
        <div className="dashboard-header" data-section="hero-title-auto-refresh">
          <div className="dashboard-header__title">
            <h2>📊 Pipeline Dashboard</h2>
            <span className="dashboard-header__subtitle">
              Real-time operational monitoring
            </span>
          </div>

          <div className="dashboard-header__controls">
            <div className="refresh-control">
              <ClockIcon className="refresh-control__icon" />
              <select
                value={refreshInterval}
                onChange={handleRefreshIntervalChange}
                className="refresh-control__select"
                aria-label="Auto-refresh interval"
              >
                {REFRESH_INTERVALS.map(interval => (
                  <option key={interval.value} value={interval.value}>
                    {interval.label}
                  </option>
                ))}
              </select>
              <button
                onClick={refetch}
                disabled={refreshing}
                className="refresh-control__button"
                aria-label="Refresh now"
              >
                <ArrowPathIcon className={`refresh-icon ${refreshing ? 'spinning' : ''}`} />
                Refresh
              </button>
            </div>
          </div>
        </div>

        {/* Error banner (if refresh error but has cached data) */}
        {error && data && (
          <div className="dashboard-banner dashboard-banner--warning">
            ⚠️ {error} — Showing last cached data
          </div>
        )}

        {/* [2. KPI ROW] - 4 cards with sparklines */}
        <section
          className="dashboard-section dashboard-section--kpis"
          data-section="kpi-overview"
        >
          <KPIRow
            kpis={data.kpis}
            historicalData={[]} // TODO: Add historical data endpoint
          />
        </section>

        {/* [2.5. PIPELINE STAGES] - Status table with pause controls */}
        {data.pipeline?.stages && (
          <section
            className="dashboard-section dashboard-section--stages"
            data-section="pipeline-stages-status"
          >
            <CollapsibleSection
              title="Pipeline Stages"
              icon={ChartBarIcon}
              priority="high"
              defaultCollapsed={false}
              headerAction={
                data.pipeline.stages.some(s => s.pauseKey) ? (
                  <div className="pause-all-controls">
                    <button
                      onClick={handlePauseAll}
                      className="pause-all-button pause-all-button--pause"
                      disabled={!isAdmin}
                      title={!isAdmin ? "Requiere permisos de administrador" : "Pausar todas las etapas"}
                    >
                      <PauseIcon style={{ width: 14, height: 14 }} />
                      <span>Pausar TODO</span>
                    </button>
                    <button
                      onClick={handleResumeAll}
                      className="pause-all-button pause-all-button--resume"
                      disabled={!isAdmin}
                      title={!isAdmin ? "Requiere permisos de administrador" : "Reanudar todas las etapas"}
                    >
                      <PlayIcon style={{ width: 14, height: 14 }} />
                      <span>Reanudar TODO</span>
                    </button>
                  </div>
                ) : null
              }
            >
              <PipelineStatusTable
                stages={data.pipeline.stages}
                isAdmin={isAdmin}
                onPauseToggle={handlePauseToggle}
              />
            </CollapsibleSection>
          </section>
        )}

        {/* [2.6. EXPIRED INSIGHTS] - Insights that hit max retries (Admin only) */}
        {isAdmin && (
          <section
            className="dashboard-section dashboard-section--expired"
            data-section="expired-insights"
          >
            <CollapsibleSection
              title="Expired Insights (Max Retries)"
              icon={ExclamationTriangleIcon}
              priority="medium"
              defaultCollapsed={true}
            >
              <ExpiredInsightsPanel
                API_URL={API_URL}
                token={token}
                refreshTrigger={refreshTrigger}
              />
            </CollapsibleSection>
          </section>
        )}

        {/* [3. MAIN ANALYSIS ROW] - Flow + Workers */}
        <section
          className="dashboard-section dashboard-section--main"
          data-section="analysis-row"
        >
          <div className="main-analysis-grid">
            {/* Pipeline Flow (60%) */}
            <div
              className="main-analysis-grid__flow"
              data-section="flow-explorer"
            >
              <CollapsibleSection
                title="Pipeline Flow"
                icon={MapIcon}
                priority="high"
                defaultCollapsed={false}
              >
                <PipelineFlowPanel
                  analysisData={data.pipeline}
                  parallelData={data.parallelData}
                  documents={data.documents}
                  width={720}
                />
              </CollapsibleSection>
            </div>

            {/* Workers (40%) */}
            <div
              className="main-analysis-grid__workers"
              data-section="worker-status"
            >
              <CollapsibleSection
                title="Workers Status"
                icon={UsersIcon}
                priority="high"
                defaultCollapsed={false}
              >
                <WorkerStatusPanel
                  workerCapacity={data.workers.capacity}
                />
              </CollapsibleSection>
            </div>
          </div>
        </section>

        {/* [4. DIAGNOSTIC ROW] - Errors */}
        <section
          className="dashboard-section dashboard-section--diagnostic"
          data-section="error-analysis"
        >
          <CollapsibleSection
            title="Error Analysis"
            icon={ExclamationTriangleIcon}
            priority="high"
            defaultCollapsed={false}
          >
            <ErrorAnalysisPanelV2
              errorGroups={data.errors.groups}
              API_URL={API_URL}
              token={token}
              onRefresh={refetch}
            />
          </CollapsibleSection>
        </section>

        {/* [5. DETAIL ROW] - Auxiliary panels */}
        <section
          className="dashboard-section dashboard-section--details"
          data-section="database-health"
        >
          <CollapsibleSection
            title="Database Status"
            icon={CircleStackIcon}
            priority="low"
            defaultCollapsed={true}
          >
            <DatabaseStatusPanel
              API_URL={API_URL}
              token={token}
              refreshTrigger={refreshTrigger}
              embedded
            />
          </CollapsibleSection>
        </section>

        {/* [6. ORCHESTRATOR METRICS] - Pipeline performance metrics from Orchestrator Agent */}
        <section
          className="dashboard-section dashboard-section--orchestrator"
          data-section="orchestrator-metrics"
        >
          <CollapsibleSection
            title="Orchestrator Metrics (v2)"
            icon={ChartBarIcon}
            priority="medium"
            defaultCollapsed={false}
          >
            <PipelineStagesMetrics
              API_URL={API_URL}
              token={token}
              refreshInterval={refreshInterval}
            />
          </CollapsibleSection>
        </section>

        {/* [7. DOCUMENT TIMELINE] - Timeline of events for a specific document */}
        {data.documents && data.documents.length > 0 && (
          <section
            className="dashboard-section dashboard-section--timeline"
            data-section="document-timeline"
          >
            <CollapsibleSection
              title="Document Timeline (Orchestrator v2)"
              icon={ClockIcon}
              priority="low"
              defaultCollapsed={!selectedDocumentId}
              headerAction={
                <div className="document-selector" style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                  <label htmlFor="document-search" style={{ marginRight: '8px', color: '#94a3b8', fontSize: '14px' }}>
                    Buscar documento:
                  </label>
                  <input
                    id="document-search"
                    type="text"
                    placeholder="Buscar por nombre, fecha o periódico..."
                    value={documentSearchQuery}
                    onChange={(e) => setDocumentSearchQuery(e.target.value)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid #334155',
                      background: '#1e293b',
                      color: '#f8fafc',
                      fontSize: '13px',
                      minWidth: '300px'
                    }}
                  />
                  <select
                    id="document-select"
                    value={selectedDocumentId || ''}
                    onChange={(e) => setSelectedDocumentId(e.target.value || null)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid #334155',
                      background: '#1e293b',
                      color: '#f8fafc',
                      fontSize: '13px',
                      cursor: 'pointer',
                      minWidth: '400px',
                      maxWidth: '600px'
                    }}
                  >
                    <option value="">-- Seleccionar documento --</option>
                    {data.documents
                      .filter(doc => {
                        if (!documentSearchQuery) return true;
                        const query = documentSearchQuery.toLowerCase();
                        const filename = (doc.filename || '').toLowerCase();
                        const docId = (doc.document_id || '').toLowerCase();
                        return filename.includes(query) || docId.includes(query);
                      })
                      .slice(0, 50)
                      .map(doc => (
                        <option key={doc.document_id} value={doc.document_id}>
                          {doc.filename || doc.document_id} {doc.file_size_mb ? `(${doc.file_size_mb.toFixed(1)} MB)` : ''}
                        </option>
                      ))}
                  </select>
                  {documentSearchQuery && (
                    <span style={{ fontSize: '12px', color: '#64748b' }}>
                      {data.documents.filter(doc => {
                        const query = documentSearchQuery.toLowerCase();
                        const filename = (doc.filename || '').toLowerCase();
                        const docId = (doc.document_id || '').toLowerCase();
                        return filename.includes(query) || docId.includes(query);
                      }).length} resultados
                    </span>
                  )}
                </div>
              }
            >
              {selectedDocumentId ? (
                <DocumentTimelinePanel
                  documentId={selectedDocumentId}
                  API_URL={API_URL}
                  token={token}
                />
              ) : (
                <div style={{ 
                  padding: '40px', 
                  textAlign: 'center', 
                  color: '#64748b',
                  background: '#0f172a',
                  borderRadius: '8px'
                }}>
                  <p style={{ margin: 0, marginBottom: '8px' }}>
                    Selecciona un documento arriba para ver su timeline de procesamiento
                  </p>
                  <p style={{ margin: 0, fontSize: '12px', color: '#475569' }}>
                    💡 Tip: Usa el campo de búsqueda para filtrar por nombre, fecha o periódico
                  </p>
                </div>
              )}
            </CollapsibleSection>
          </section>
        )}

        {/* Footer info */}
        <div className="dashboard-footer" data-section="footer-version">
          <span className="dashboard-footer__version">
            Dashboard v5.0.0-alpha
          </span>
          <span className="dashboard-footer__updated">
            Last updated: {new Date().toLocaleTimeString()}
          </span>
        </div>
      </div>
    </DashboardProvider>
  );
}

PipelineDashboard.propTypes = {
  API_URL: PropTypes.string.isRequired,
  token: PropTypes.string.isRequired,
  refreshTrigger: PropTypes.number,
  isAdmin: PropTypes.bool
};

export default PipelineDashboard;
