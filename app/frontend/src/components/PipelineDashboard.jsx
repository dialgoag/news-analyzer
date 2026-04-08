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

  // Handle pause/resume ALL stages
  const handlePauseAll = useCallback(async () => {
    if (!token) {
      alert('Error: No estás autenticado. Por favor, inicia sesión nuevamente.');
      return;
    }
    
    if (!data?.pipeline?.stages) return;
    
    // Check if all are paused
    const allPaused = data.pipeline.stages
      .filter(s => s.pauseKey)
      .every(s => s.paused);
    
    const newState = !allPaused;
    console.log(`[PauseAll] Current: all paused = ${allPaused}, New state: ${newState ? 'pause all' : 'resume all'}`);
    
    // Backend expects: { "pause_all": true } or { "resume_all": true }
    const payload = newState ? { pause_all: true } : { resume_all: true };
    
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
      console.log('[PauseAll] Forcing refresh...');
      await refetch();
      
      console.log('[PauseAll] Refresh complete');
    } catch (err) {
      console.error('[PauseAll] Error:', err);
      const errorMsg = err.response?.data?.detail || err.message;
      alert(`Error al pausar/reanudar todo: ${errorMsg}`);
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
      <div className="pipeline-dashboard">
        {/* [1. HEADER] - Title + Refresh Control */}
        <div className="dashboard-header">
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
        <section className="dashboard-section dashboard-section--kpis">
          <KPIRow
            kpis={data.kpis}
            historicalData={[]} // TODO: Add historical data endpoint
          />
        </section>

        {/* [2.5. PIPELINE STAGES] - Status table with pause controls */}
        {data.pipeline?.stages && (
          <section className="dashboard-section dashboard-section--stages">
            <CollapsibleSection
              title="Pipeline Stages"
              icon={ChartBarIcon}
              priority="high"
              defaultCollapsed={false}
            >
              {/* Global Pause Control (Admin only) */}
              {isAdmin && (
                <div className="pipeline-global-control">
                  <button
                    onClick={handlePauseAll}
                    className="pause-all-button"
                    title={
                      data.pipeline.stages.filter(s => s.pauseKey).every(s => s.paused)
                        ? "Reanudar todas las etapas"
                        : "Pausar todas las etapas"
                    }
                  >
                    {data.pipeline.stages.filter(s => s.pauseKey).every(s => s.paused) ? (
                      <>
                        <PlayIcon style={{ width: 16, height: 16 }} />
                        <span>Reanudar TODO</span>
                      </>
                    ) : (
                      <>
                        <PauseIcon style={{ width: 16, height: 16 }} />
                        <span>Pausar TODO</span>
                      </>
                    )}
                  </button>
                </div>
              )}
              
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
          <section className="dashboard-section dashboard-section--expired">
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
        <section className="dashboard-section dashboard-section--main">
          <div className="main-analysis-grid">
            {/* Pipeline Flow (60%) */}
            <div className="main-analysis-grid__flow">
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
            <div className="main-analysis-grid__workers">
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
        <section className="dashboard-section dashboard-section--diagnostic">
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
        <section className="dashboard-section dashboard-section--details">
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

        {/* Footer info */}
        <div className="dashboard-footer">
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
