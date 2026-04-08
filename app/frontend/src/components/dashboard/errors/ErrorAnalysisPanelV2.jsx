/**
 * ErrorAnalysisPanelV2 Component
 * 
 * Integrated error analysis with bar chart, timeline, and retry actions
 * Replaces/enhances the original ErrorAnalysisPanel
 */

import React, { useState, useMemo } from 'react';
import PropTypes from 'prop-types';
import axios from 'axios';
import ErrorBarChart from './ErrorBarChart';
import ErrorTimeline from './ErrorTimeline';
import { 
  sortErrorsByPriority,
  prepareErrorTimeline,
  prepareBatchRetryPayload,
  calculateErrorStats
} from '../../../services/errorDataService';
import './ErrorAnalysisPanelV2.css';

export function ErrorAnalysisPanelV2({ 
  errorGroups = [], 
  API_URL, 
  token,
  onRefresh
}) {
  const [selectedErrors, setSelectedErrors] = useState([]);
  const [retrying, setRetrying] = useState(false);
  const [retryStatus, setRetryStatus] = useState(null);

  // Sort errors by priority
  const sortedErrors = useMemo(() => 
    sortErrorsByPriority(errorGroups),
    [errorGroups]
  );

  // Prepare timeline data (flatten all errors)
  const timelineData = useMemo(() => {
    const allErrors = errorGroups.flatMap(group => 
      Array(group.count).fill({
        error_message: group.error_message,
        created_at: group.last_seen, // Use last_seen as proxy
        severity: group.severity
      })
    );
    return prepareErrorTimeline(allErrors, 24, 60); // 24h, 1h buckets
  }, [errorGroups]);

  // Calculate statistics
  const stats = useMemo(() => 
    calculateErrorStats(errorGroups),
    [errorGroups]
  );

  const handleBarClick = (error) => {
    setSelectedErrors(prev => {
      if (prev.includes(error.error_message)) {
        return prev.filter(msg => msg !== error.error_message);
      }
      return [...prev, error.error_message];
    });
  };

  const handleRetryClick = async (errorsToRetry) => {
    if (!API_URL || !token) {
      setRetryStatus({ type: 'error', message: 'No API configuration' });
      return;
    }

    setRetrying(true);
    setRetryStatus(null);

    try {
      const payload = prepareBatchRetryPayload(errorsToRetry);
      
      const response = await axios.post(
        `${API_URL}/api/workers/retry-errors`,
        payload,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );

      setRetryStatus({
        type: 'success',
        message: `✅ Retry initiated for ${payload.total_affected} items`
      });

      // Clear selection
      setSelectedErrors([]);

      // Refresh dashboard after 2s
      setTimeout(() => {
        onRefresh && onRefresh();
      }, 2000);
    } catch (err) {
      console.error('Retry failed:', err);
      setRetryStatus({
        type: 'error',
        message: `❌ Retry failed: ${err.response?.data?.detail || err.message}`
      });
    } finally {
      setRetrying(false);
    }
  };

  const handleRetrySelected = () => {
    const selected = sortedErrors.filter(e => 
      selectedErrors.includes(e.error_message)
    );
    handleRetryClick(selected);
  };

  const handleRetryAll = () => {
    const retriable = sortedErrors.filter(e => e.canRetry);
    if (retriable.length === 0) {
      setRetryStatus({ type: 'warning', message: '⚠️ No retriable errors found' });
      return;
    }
    handleRetryClick(retriable);
  };

  if (sortedErrors.length === 0) {
    return (
      <div className="error-analysis-panel-v2 error-analysis-panel-v2--empty">
        <p>✅ No errors detected - System operating normally</p>
      </div>
    );
  }

  return (
    <div className="error-analysis-panel-v2">
      {/* Statistics Header */}
      <div className="error-analysis-panel-v2__stats">
        <div className="stat-card">
          <span className="stat-card__label">Total Errors</span>
          <span className="stat-card__value stat-card__value--total">{stats.total}</span>
        </div>
        <div className="stat-card">
          <span className="stat-card__label">Unique Types</span>
          <span className="stat-card__value">{stats.uniqueTypes}</span>
        </div>
        <div className="stat-card">
          <span className="stat-card__label">Retriable</span>
          <span className="stat-card__value stat-card__value--retriable">
            {stats.retriable} ({stats.retriablePercent}%)
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-card__label">Critical</span>
          <span className="stat-card__value stat-card__value--critical">{stats.critical}</span>
        </div>
      </div>

      {/* Action Bar */}
      <div className="error-analysis-panel-v2__actions">
        <button
          className="action-button action-button--primary"
          onClick={handleRetryAll}
          disabled={retrying || stats.retriable === 0}
        >
          {retrying ? '⏳ Retrying...' : `🔄 Retry All Retriable (${stats.retriable})`}
        </button>
        
        {selectedErrors.length > 0 && (
          <button
            className="action-button action-button--secondary"
            onClick={handleRetrySelected}
            disabled={retrying}
          >
            Retry Selected ({selectedErrors.length})
          </button>
        )}

        <button
          className="action-button action-button--tertiary"
          onClick={() => setSelectedErrors([])}
          disabled={selectedErrors.length === 0}
        >
          Clear Selection
        </button>
      </div>

      {/* Retry Status */}
      {retryStatus && (
        <div className={`error-analysis-panel-v2__status error-analysis-panel-v2__status--${retryStatus.type}`}>
          {retryStatus.message}
        </div>
      )}

      {/* Timeline */}
      <div className="error-analysis-panel-v2__section">
        <h4 className="section-title">Error Frequency (Last 24h)</h4>
        <ErrorTimeline
          data={timelineData}
          width={720}
          height={120}
          hours={24}
        />
      </div>

      {/* Bar Chart */}
      <div className="error-analysis-panel-v2__section">
        <h4 className="section-title">
          Errors by Type 
          <span className="section-subtitle">(sorted by severity & count)</span>
        </h4>
        <ErrorBarChart
          data={sortedErrors}
          width={720}
          height={Math.min(600, sortedErrors.length * 40 + 80)}
          onBarClick={handleBarClick}
          onRetryClick={handleRetryClick}
          selectedErrors={selectedErrors}
        />
      </div>

      {/* Help Text */}
      <details className="error-analysis-panel-v2__help">
        <summary>💡 How to use error analysis</summary>
        <div className="help-content">
          <p><strong>Click bars</strong> to select/deselect error types</p>
          <p><strong>Retry buttons</strong> requeue failed items for reprocessing</p>
          <p><strong>Color coding</strong>: 🔴 Critical | 🟠 High | 🟡 Medium | ⚪ Low</p>
          <p><strong>Timeline</strong> shows temporal patterns (spikes indicate systemic issues)</p>
          <br />
          <p><em>Errors are automatically classified by severity and retry capability based on message patterns.</em></p>
        </div>
      </details>
    </div>
  );
}

ErrorAnalysisPanelV2.propTypes = {
  errorGroups: PropTypes.array.isRequired,
  API_URL: PropTypes.string.isRequired,
  token: PropTypes.string.isRequired,
  onRefresh: PropTypes.func
};

export default ErrorAnalysisPanelV2;
