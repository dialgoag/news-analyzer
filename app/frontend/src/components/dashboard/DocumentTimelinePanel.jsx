/**
 * Document Timeline Panel
 * 
 * Muestra el timeline completo de eventos del pipeline para un documento específico
 * Usa los datos del endpoint /api/orchestrator/document-timeline/{id}
 */

import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { 
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  PlayIcon
} from '@heroicons/react/24/outline';
import { 
  fetchDocumentTimeline,
  transformTimelineForUI,
  getStageColor,
  getStatusIcon,
  fetchStageResult
} from '../../services/orchestratorService';
import './DocumentTimelinePanel.css';

export function DocumentTimelinePanel({ documentId, API_URL, token }) {
  const [timeline, setTimeline] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedStages, setExpandedStages] = useState({}); // {stage: {loading, data, error}}
  const [stageResults, setStageResults] = useState({}); // {stage: result}

  // Fetch timeline on mount or when documentId changes
  useEffect(() => {
    if (!documentId) return;

    const loadTimeline = async () => {
      setLoading(true);
      setError(null);

      try {
        const data = await fetchDocumentTimeline(documentId, token);
        const transformed = transformTimelineForUI(data);
        setTimeline({ ...data, events: transformed });
      } catch (err) {
        console.error('[DocumentTimelinePanel] Error fetching timeline:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    loadTimeline();
  }, [documentId, token]);

  // Render loading state
  if (loading) {
    return (
      <div className="timeline-panel loading">
        <ArrowPathIcon className="icon-spin" />
        <span>Cargando timeline...</span>
      </div>
    );
  }

  // Render error state
  if (error) {
    return (
      <div className="timeline-panel error">
        <XCircleIcon className="icon-error" />
        <span>Error: {error}</span>
      </div>
    );
  }

  // Render empty state
  if (!timeline || !timeline.events || timeline.events.length === 0) {
    return (
      <div className="timeline-panel empty">
        <ExclamationCircleIcon className="icon-warning" />
        <span>No hay eventos de pipeline para este documento</span>
      </div>
    );
  }

  return (
    <div className="timeline-panel">
      {/* Header */}
      <div className="timeline-header">
        <h3 className="timeline-title">
          <ClockIcon className="icon-title" />
          Pipeline Timeline
        </h3>
        <div className="timeline-meta">
          <span className="document-id">{timeline.document_id}</span>
          <span className="event-count">{timeline.total_events} eventos</span>
        </div>
      </div>

      {/* Events list */}
      <div className="timeline-events">
        {timeline.events.map((event, index) => (
          <TimelineEvent 
            key={index} 
            event={event} 
            isLast={index === timeline.events.length - 1}
          />
        ))}
      </div>
    </div>
  );
}

DocumentTimelinePanel.propTypes = {
  documentId: PropTypes.string.isRequired,
  API_URL: PropTypes.string,
  token: PropTypes.string.isRequired,
};

/**
 * Individual Timeline Event Component
 */
function TimelineEvent({ event, isLast }) {
  const [expanded, setExpanded] = useState(false);
  
  const stageColor = getStageColor(event.stage);
  const statusIcon = getStatusIcon(event.status);
  
  // Status badge color
  const statusClass = {
    completed: 'status-success',
    error: 'status-error',
    in_progress: 'status-in-progress',
    started: 'status-started',
    skipped: 'status-skipped',
  }[event.status] || 'status-unknown';

  return (
    <div className={`timeline-event ${isLast ? 'last' : ''}`}>
      {/* Timeline connector line */}
      {!isLast && <div className="timeline-line" />}
      
      {/* Stage indicator dot */}
      <div 
        className="timeline-dot" 
        style={{ backgroundColor: stageColor }}
      />

      {/* Event content */}
      <div className="event-content">
        {/* Event header */}
        <div className="event-header" onClick={() => setExpanded(!expanded)}>
          <div className="event-title">
            <span className="stage-name">{event.stage}</span>
            <span className={`status-badge ${statusClass}`}>
              {statusIcon} {event.status}
            </span>
          </div>
          
          <div className="event-meta">
            <span className="event-duration">{event.duration_formatted}</span>
            <span className="event-timestamp">
              {event.timestamp.toLocaleTimeString('es-ES', { 
                hour: '2-digit', 
                minute: '2-digit', 
                second: '2-digit' 
              })}
            </span>
          </div>
        </div>

        {/* Event details (expandable) */}
        {expanded && (
          <div className="event-details">
            {/* Metadata summary */}
            {event.metadata_summary && (
              <div className="detail-row">
                <span className="detail-label">Metadata:</span>
                <span className="detail-value">{event.metadata_summary}</span>
              </div>
            )}

            {/* Error details */}
            {event.has_error && event.error_message && (
              <div className="detail-row error">
                <span className="detail-label">Error:</span>
                <span className="detail-value error-text">{event.error_message}</span>
              </div>
            )}

            {/* Result reference */}
            {event.result_ref && (
              <div className="detail-row">
                <span className="detail-label">Result:</span>
                <span className="detail-value result-ref">{event.result_ref}</span>
              </div>
            )}

            {/* Full metadata (JSON) */}
            {event.metadata && Object.keys(event.metadata).length > 0 && (
              <details className="metadata-details">
                <summary>Ver metadata completo</summary>
                <pre className="metadata-json">
                  {JSON.stringify(event.metadata, null, 2)}
                </pre>
              </details>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

TimelineEvent.propTypes = {
  event: PropTypes.shape({
    stage: PropTypes.string.isRequired,
    status: PropTypes.string.isRequired,
    timestamp: PropTypes.instanceOf(Date).isRequired,
    duration_sec: PropTypes.number,
    duration_formatted: PropTypes.string,
    metadata_summary: PropTypes.string,
    has_error: PropTypes.bool,
    error_message: PropTypes.string,
    result_ref: PropTypes.string,
    metadata: PropTypes.object,
  }).isRequired,
  isLast: PropTypes.bool,
};

export default DocumentTimelinePanel;
