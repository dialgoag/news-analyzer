/**
 * DocumentsTable Component - WITH SEMANTIC GROUPING
 * 
 * Interactive table with hierarchical grouping:
 * - GROUP ROWS: Show aggregated metrics for active/inactive groups
 * - INDIVIDUAL ROWS: Show detailed document info (expandable)
 * 
 * Features:
 * - Click group header to expand/collapse
 * - Auto-collapse when >20 documents
 * - Coordinated filtering with visualizations
 * - Progress bars and status badges
 */

import React, { useEffect, useState, useMemo } from 'react';
import axios from 'axios';
import { useDashboardFilters } from '../hooks/useDashboardFilters.jsx';
import {
  groupDocumentsByMetaGroup,
  aggregateGroupMetrics,
  shouldAutoCollapse,
  GROUP_HIERARCHY
} from '../../services/semanticZoomService';
import './DocumentsTable.css';
import './DocumentsTableGrouping.css'; // NEW: Grouping styles

// Extract stage from new status format: {stage}_{state} or terminal (completed/error/paused)
function mapStatusToStage(status) {
  if (!status) return 'upload';
  if (status === 'completed' || status === 'error' || status === 'paused') return status;
  const parts = status.split('_');
  return parts[0]; // upload, ocr, chunking, indexing, insights
}

export function DocumentsTable({ API_URL, token, refreshTrigger }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { filters, updateFilter, clearFilter } = useDashboardFilters();
  
  // Grouping state: which groups are expanded
  const [expandedGroups, setExpandedGroups] = useState({
    active: false,   // Start collapsed
    inactive: false  // Start collapsed
  });
  
  // Auto-collapse based on document count
  const shouldCollapse = useMemo(() => 
    shouldAutoCollapse(documents.length, 20),
    [documents.length]
  );

  // Fetch documents data
  useEffect(() => {
    const fetchDocuments = async () => {
      try {
        const response = await axios.get(
          `${API_URL}/api/documents/status`,
          {
            headers: { Authorization: `Bearer ${token}` },
            timeout: 5000
          }
        );
        setDocuments(response.data || []);
        setError(null);
      } catch (err) {
        console.error('Error fetching documents:', err);
        setError(err.response?.status === 404 
          ? 'Endpoint no disponible' 
          : err.message || 'Error de conexión');
      } finally {
        setLoading(false);
      }
    };

    fetchDocuments();
    const interval = setInterval(fetchDocuments, 5000);
    return () => clearInterval(interval);
  }, [API_URL, token, refreshTrigger]);

  // Filter documents based on global filters
  const filteredDocuments = useMemo(() => {
    if (!Array.isArray(documents)) return [];
    let result = [...documents];

    if (filters.stage) {
      const stageStatusMap = {
        'upload': ['upload_pending', 'upload_processing', 'upload_done'],
        'ocr': ['ocr_pending', 'ocr_processing', 'ocr_done'],
        'chunking': ['chunking_pending', 'chunking_processing', 'chunking_done'],
        'indexing': ['indexing_pending', 'indexing_processing', 'indexing_done'],
        'insights': ['insights_pending', 'insights_processing', 'insights_done'],
        'completed': ['completed'],
        'error': ['error'],
        'paused': ['paused']
      };
      
      const validStatuses = stageStatusMap[filters.stage] || [filters.stage];
      result = result.filter(d => validStatuses.includes(d.status));
    }

    if (filters.status) {
      result = result.filter(d => d.status === filters.status);
    }

    if (filters.timeRange) {
      const [start, end] = filters.timeRange;
      result = result.filter(d => {
        const date = new Date(d.uploaded_at || d.created_at);
        return date >= start && date <= end;
      });
    }

    if (filters.documentId) {
      result = result.filter(d => d.document_id === filters.documentId);
    }

    return result;
  }, [documents, filters]);

  // Group documents by meta-group (active/inactive)
  const groupedDocuments = useMemo(() => 
    groupDocumentsByMetaGroup(filteredDocuments, (doc) => mapStatusToStage(doc.status)),
    [filteredDocuments]
  );

  // Toggle group expansion
  const toggleGroup = (groupId) => {
    setExpandedGroups(prev => ({
      ...prev,
      [groupId]: !prev[groupId]
    }));
  };

  // Handle row click
  const handleRowClick = (doc) => {
    const stage = mapStatusToStage(doc.status);
    
    if (filters.stage === stage && filters.documentId === doc.document_id) {
      clearFilter('stage');
      clearFilter('documentId');
    } else {
      updateFilter('stage', stage);
      updateFilter('documentId', doc.document_id);
    }
  };

  // Handle group click
  const handleGroupClick = (groupId) => {
    // Filter by all stages in that group
    const groupStages = GROUP_HIERARCHY[groupId].stages;
    updateFilter('stage', groupStages[0]); // Use first stage as representative
  };

  const getStatusClass = (status) => {
    const stage = mapStatusToStage(status);
    const stageToClass = {
      upload: 'status-upload',
      ocr: 'status-ocr',
      chunking: 'status-chunking',
      indexing: 'status-indexing',
      insights: 'status-insights',
      completed: 'status-completed',
      error: 'status-error',
      paused: 'status-paused'
    };
    return stageToClass[stage] || 'status-unknown';
  };

  const calculateProgress = (doc) => {
    const stages = ['upload', 'ocr', 'chunking', 'indexing', 'insights', 'completed'];
    const stage = mapStatusToStage(doc.status);
    const currentIndex = stages.indexOf(stage);
    if (currentIndex === -1) return 0;
    return ((currentIndex + 1) / stages.length) * 100;
  };

  if (loading && documents.length === 0) {
    return <div className="documents-table-loading">Cargando documentos...</div>;
  }

  return (
    <div className="documents-table-container">
      <div className="documents-table-header">
        <h3>📄 Documentos en Proceso (Vista Agrupada)</h3>
        <p className="documents-hint">
          💡 Click en grupo para expandir/colapsar • Click en documento para filtrar
        </p>
        
        {error && (
          <div className="error-banner">
            ⚠️ {error}
            {documents.length > 0 && ' - Mostrando últimos datos disponibles'}
          </div>
        )}
      </div>

      <div className="documents-table-wrapper">
        <table className="documents-table documents-table-grouped">
          <thead>
            <tr>
              <th style={{ width: '40px' }}></th>
              <th>Archivo / Grupo</th>
              <th>Estado</th>
              <th>Progreso</th>
              <th>Noticias</th>
              <th>Insights</th>
              <th>Fecha</th>
            </tr>
          </thead>
          <tbody>
            {['active', 'inactive'].map(groupId => {
              const groupDocs = groupedDocuments[groupId] || [];
              if (groupDocs.length === 0) return null;
              
              const groupInfo = GROUP_HIERARCHY[groupId];
              const metrics = aggregateGroupMetrics(groupDocs);
              const isExpanded = expandedGroups[groupId];
              
              return (
                <React.Fragment key={groupId}>
                  {/* GROUP HEADER ROW */}
                  <tr 
                    className={`group-row ${isExpanded ? 'expanded' : 'collapsed'}`}
                    onClick={() => toggleGroup(groupId)}
                  >
                    <td className="expand-icon">
                      {isExpanded ? '▼' : '▶'}
                    </td>
                    <td className="group-name">
                      <strong style={{ color: groupInfo.color }}>
                        {groupInfo.label}
                      </strong>
                      <span className="group-count">({metrics.count} docs)</span>
                    </td>
                    <td>
                      <div className="group-status-summary">
                        {metrics.processing > 0 && (
                          <span className="status-badge status-ocr">
                            🟢 {metrics.processing}
                          </span>
                        )}
                        {metrics.completed > 0 && (
                          <span className="status-badge status-completed">
                            ✅ {metrics.completed}
                          </span>
                        )}
                        {metrics.error > 0 && (
                          <span className="status-badge status-error">
                            ❌ {metrics.error}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="centered">
                      <strong>Total</strong>
                    </td>
                    <td className="centered">
                      <strong>{metrics.totalNews}</strong>
                    </td>
                    <td className="centered">
                      <strong>{metrics.totalInsights}</strong>
                    </td>
                    <td className="centered">
                      <span className="group-size-badge">
                        {(metrics.totalSize / 1024).toFixed(1)} MB
                      </span>
                    </td>
                  </tr>
                  
                  {/* INDIVIDUAL DOCUMENT ROWS (if expanded) */}
                  {isExpanded && groupDocs.slice(0, 50).map((doc, idx) => (
                    <tr
                      key={doc.document_id || idx}
                      className={`document-row indent ${
                        filters.documentId === doc.document_id ? 'selected' : ''
                      }`}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRowClick(doc);
                      }}
                    >
                      <td></td>
                      <td className="filename">
                        <span title={doc.filename}>
                          {doc.filename?.substring(0, 35)}
                          {doc.filename?.length > 35 ? '...' : ''}
                        </span>
                      </td>
                      <td>
                        <span className={`status-badge ${getStatusClass(doc.status)}`}>
                          {doc.status}
                        </span>
                      </td>
                      <td className="progress-cell">
                        <div className="progress-bar-container">
                          <div 
                            className="progress-bar-fill"
                            style={{
                              width: `${calculateProgress(doc)}%`,
                              background: getStatusClass(doc.status).includes('completed') 
                                ? '#10b981' 
                                : getStatusClass(doc.status).includes('error')
                                ? '#f44336'
                                : '#4dd0e1'
                            }}
                          ></div>
                        </div>
                        <span className="progress-text">
                          {Math.round(calculateProgress(doc))}%
                        </span>
                      </td>
                      <td className="centered">
                        {doc.news_items_count || 0}
                      </td>
                      <td className="centered">
                        <span className={doc.insights_done > 0 ? 'has-insights' : 'no-insights'}>
                          {doc.insights_done || 0}/{doc.insights_total || 0}
                        </span>
                      </td>
                      <td className="timestamp">
                        {doc.uploaded_at 
                          ? new Date(doc.uploaded_at).toLocaleString('es-ES', {
                              day: '2-digit',
                              month: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit'
                            })
                          : '-'
                        }
                      </td>
                    </tr>
                  ))}
                  
                  {/* Show "X more..." if group has more than 50 docs */}
                  {isExpanded && groupDocs.length > 50 && (
                    <tr className="more-docs-row">
                      <td></td>
                      <td colSpan="6" className="centered" style={{ color: '#94a3b8', fontStyle: 'italic' }}>
                        ... y {groupDocs.length - 50} documentos más. Aplica filtros para ver específicos.
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
            
            {filteredDocuments.length === 0 && (
              <tr>
                <td colSpan="7" style={{ textAlign: 'center', color: '#94a3b8' }}>
                  Sin documentos que coincidan con los filtros
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      
      {/* Summary Footer */}
      <div className="documents-table-footer">
        <span>
          Total: {filteredDocuments.length} documentos 
          ({groupedDocuments.active?.length || 0} activos, {groupedDocuments.inactive?.length || 0} finalizados)
        </span>
      </div>
    </div>
  );
}

export default DocumentsTable;
