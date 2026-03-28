/**
 * PipelineSankeyChart Component - WITH SEMANTIC GROUPING + 3-LEVEL DRILL-DOWN
 * 
 * Zoom levels (REQ-014.4):
 * - Level 0 (Overview): All docs, Active/Inactive groups. Click stage header → Level 1
 * - Level 1 (By Stage): Docs in selected stage. Click doc line → Level 2
 * - Level 2 (By Document): Single doc flow through pipeline
 * 
 * Layout:
 * - Breadcrumb: Overview > [Stage] > [Doc] — click to navigate back
 * - Left: Group tags (Level 0) or stage list (Level 1)
 * - Center: Pipeline columns (always visible)
 * - Flows: Aggregated or individual lines
 */

import React, { useEffect, useRef, useMemo, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { useDashboardFilters } from '../hooks/useDashboardFilters.jsx';
import { 
  transformDocumentsForVisualization,
  generateTooltipHTML,
  groupDocumentsByStage 
} from '../../services/documentDataService';
import {
  groupDocumentsByMetaGroup,
  aggregateGroupMetrics,
  GROUP_HIERARCHY,
  calculateCollapsedStrokeWidth
} from '../../services/semanticZoomService';
import './PipelineSankeyChart.css';
import './SemanticZoom.css';

// Stage colors (stage names: upload, ocr, chunking, indexing, insights, indexing insights, completed)
const stageColors = {
  upload: '#f59e0b',
  ocr: '#3b82f6',
  chunking: '#8b5cf6',
  indexing: '#ec4899',
  insights: '#10b981',
  'indexing insights': '#06b6d4',
  completed: '#6b7280',
  error: '#ef4444'
};

// Extract stage from new status format: {stage}_{state} or terminal (completed/error/paused)
function getStageFromStatus(status) {
  if (!status) return 'upload';
  if (status === 'completed' || status === 'error' || status === 'paused') return status;
  const parts = status.split('_');
  return parts[0]; // upload, ocr, chunking, indexing, insights
}

const mapStageToColumn = (doc) => {
  const status = doc.status || 'upload_pending';
  return getStageFromStatus(status);
};

const ZOOM_LEVEL = { OVERVIEW: 0, BY_STAGE: 1, BY_DOCUMENT: 2 };

const ZOOM_CONFIG = [
  { level: ZOOM_LEVEL.OVERVIEW, label: 'Overview', hint: 'Activos vs No activos' },
  { level: ZOOM_LEVEL.BY_STAGE, label: 'Etapa', hint: 'Docs por etapa' },
  { level: ZOOM_LEVEL.BY_DOCUMENT, label: 'Documento', hint: 'Flujo individual' }
];

const METRIC_OPTIONS = {
  documents: {
    label: 'Documentos',
    aggregateKey: 'count',
    docValue: () => 1,
    legend: 'Número de documentos',
    maxHint: 'docs'
  },
  news: {
    label: 'Noticias',
    aggregateKey: 'totalNews',
    docValue: (doc) => doc.news_count || 0,
    legend: 'Noticias extraídas',
    maxHint: 'news'
  },
  chunks: {
    label: 'Chunks',
    aggregateKey: 'totalChunks',
    docValue: (doc) => doc.chunks_count || 0,
    legend: 'Chunks generados',
    maxHint: 'chunks'
  },
  insights: {
    label: 'Insights',
    aggregateKey: 'totalInsights',
    docValue: (doc) => doc.insights_count || 0,
    legend: 'Insights generados',
    maxHint: 'insights'
  }
};

export function PipelineSankeyChart({ data, documents = [] }) {
  const svgRef = useRef();
  const containerRef = useRef();
  const { filters, updateFilter, clearFilter } = useDashboardFilters();
  const [hoveredDoc, setHoveredDoc] = useState(null);
  
  // Drill-down state (REQ-014.4)
  const [zoomLevel, setZoomLevel] = useState(ZOOM_LEVEL.OVERVIEW);
  const [selectedStage, setSelectedStage] = useState(null);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [metricMode, setMetricMode] = useState('documents');
  const [userAdjustedCollapse, setUserAdjustedCollapse] = useState(false);
  const [inspectMode, setInspectMode] = useState(false);
  
  // Track which groups are collapsed (Set of group IDs: 'active', 'inactive')
  const [collapsedGroups, setCollapsedGroups] = useState(new Set());
  
  // Transform documents
  const normalizedDocuments = useMemo(() => 
    transformDocumentsForVisualization(documents),
    [documents]
  );

  useEffect(() => {
    if (userAdjustedCollapse) return;
    if (normalizedDocuments.length > 100) {
      setCollapsedGroups(new Set(['active', 'inactive']));
    } else if (collapsedGroups.size > 0) {
      setCollapsedGroups(new Set());
    }
  }, [normalizedDocuments.length, userAdjustedCollapse, collapsedGroups]);
  
  // Group documents by current stage (always from full set for stage counts)
  const documentsByStage = useMemo(() => 
    groupDocumentsByStage(normalizedDocuments, mapStageToColumn),
    [normalizedDocuments]
  );

  const defaultStage = useMemo(() => {
    const entries = Object.entries(documentsByStage || {});
    if (!entries.length) return null;
    const sorted = [...entries].sort((a, b) => (b[1]?.length || 0) - (a[1]?.length || 0));
    return sorted[0]?.[0] || null;
  }, [documentsByStage]);

  // Documents to display based on zoom level
  const displayedDocuments = useMemo(() => {
    if (zoomLevel === ZOOM_LEVEL.OVERVIEW) return normalizedDocuments;
    if (zoomLevel === ZOOM_LEVEL.BY_STAGE && selectedStage) {
      return documentsByStage[selectedStage] || [];
    }
    if (zoomLevel === ZOOM_LEVEL.BY_DOCUMENT && selectedDoc) {
      return [selectedDoc];
    }
    return normalizedDocuments;
  }, [zoomLevel, selectedStage, selectedDoc, normalizedDocuments, documentsByStage]);
  
  // Group displayed documents by meta-group (for Level 0)
  const groupedDocuments = useMemo(() => 
    groupDocumentsByMetaGroup(displayedDocuments, mapStageToColumn),
    [displayedDocuments]
  );

  const groupedMetrics = useMemo(() => {
    const result = {};
    Object.entries(groupedDocuments).forEach(([groupId, docs]) => {
      result[groupId] = {
        docs,
        metrics: aggregateGroupMetrics(docs)
      };
    });
    return result;
  }, [groupedDocuments]);
  
  const metricConfig = METRIC_OPTIONS[metricMode] || METRIC_OPTIONS.documents;

  const docMetricMax = useMemo(() => {
    if (!metricConfig?.docValue) return 1;
    const values = normalizedDocuments
      .map(metricConfig.docValue)
      .filter((value) => typeof value === 'number' && value > 0);
    return values.length ? Math.max(...values) : 1;
  }, [normalizedDocuments, metricConfig]);

  const aggregateMetricMax = useMemo(() => {
    if (!metricConfig?.aggregateKey) return 1;
    const metricsList = Object.values(groupedMetrics || {});
    const values = metricsList.map(
      (entry) => entry.metrics[metricConfig.aggregateKey] || 0
    );
    const maxValue = values.length ? Math.max(...values) : 1;
    return maxValue || 1;
  }, [groupedMetrics, metricConfig]);
  
  const [dimensions, setDimensions] = useState({ width: 900, height: 1200 });

  const handleDocumentSelect = useCallback((doc) => {
    if (!doc) return;
    updateFilter('documentId', doc.document_id);
    updateFilter('stage', mapStageToColumn(doc));
  }, [updateFilter]);

  const handleStageZoom = useCallback((stage) => {
    if (!stage) return;
    setZoomLevel(ZOOM_LEVEL.BY_STAGE);
    setSelectedStage(stage);
    setSelectedDoc(null);
    updateFilter('stage', stage);
    clearFilter('documentId');
  }, [updateFilter, clearFilter]);

  const handleGroupToggle = useCallback(() => {
    setUserAdjustedCollapse(true);
    setCollapsedGroups((prev) => {
      const isCollapsed = prev.has('active') && prev.has('inactive');
      return isCollapsed ? new Set() : new Set(['active', 'inactive']);
    });
  }, []);

  const cleanupTooltips = useCallback(() => {
    d3.selectAll('.sankey-tooltip').remove();
  }, []);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Shift') {
        setInspectMode(true);
      }
    };
    const handleKeyUp = (event) => {
      if (event.key === 'Shift') {
        setInspectMode(false);
        cleanupTooltips();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [cleanupTooltips]);

  const handleZoomControl = (level) => {
    if (level === ZOOM_LEVEL.OVERVIEW) {
      setZoomLevel(ZOOM_LEVEL.OVERVIEW);
      setSelectedStage(null);
      setSelectedDoc(null);
      clearFilter('stage');
      clearFilter('documentId');
      return;
    }
    if (level === ZOOM_LEVEL.BY_STAGE) {
      if (selectedStage) {
        setZoomLevel(ZOOM_LEVEL.BY_STAGE);
        setSelectedDoc(null);
        clearFilter('documentId');
      } else if (defaultStage) {
        handleStageZoom(defaultStage);
      }
      return;
    }
    if (level === ZOOM_LEVEL.BY_DOCUMENT && selectedDoc) {
      setZoomLevel(ZOOM_LEVEL.BY_DOCUMENT);
    }
  };

  useEffect(() => {
    if (!filters.stage) {
      if (zoomLevel === ZOOM_LEVEL.BY_STAGE && !selectedDoc) {
        setZoomLevel(ZOOM_LEVEL.OVERVIEW);
        setSelectedStage(null);
      }
      return;
    }
    if (filters.stage && zoomLevel === ZOOM_LEVEL.OVERVIEW) {
      setZoomLevel(ZOOM_LEVEL.BY_STAGE);
      setSelectedStage(filters.stage);
    }
  }, [filters.stage, zoomLevel, selectedDoc]);

  useEffect(() => {
    if (!filters.documentId) {
      if (zoomLevel === ZOOM_LEVEL.BY_DOCUMENT) {
        setZoomLevel(selectedStage ? ZOOM_LEVEL.BY_STAGE : ZOOM_LEVEL.OVERVIEW);
        setSelectedDoc(null);
      }
      return;
    }
    const docMatch = normalizedDocuments.find((doc) => doc.document_id === filters.documentId);
    if (docMatch) {
      setSelectedDoc(docMatch);
      setSelectedStage(mapStageToColumn(docMatch));
      setZoomLevel(ZOOM_LEVEL.BY_DOCUMENT);
    }
  }, [filters.documentId, normalizedDocuments, zoomLevel, selectedStage]);

  // Update dimensions on resize
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const { width } = containerRef.current.getBoundingClientRect();
        setDimensions({
          width: Math.max(600, width - 40),
          height: 1200
        });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, [documents.length]);

  // Main render effect
  useEffect(() => {
    if (!data || !svgRef.current || normalizedDocuments.length === 0) return;
    if (zoomLevel > ZOOM_LEVEL.OVERVIEW && displayedDocuments.length === 0) return;

    const { width, height } = dimensions;
    const margin = { top: 80, right: 20, bottom: 40, left: 150 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    d3.select(svgRef.current).selectAll("*").remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Info text (varies by zoom level)
    let infoText;
    if (zoomLevel === ZOOM_LEVEL.BY_DOCUMENT && selectedDoc) {
      infoText = `💡 Click en "Overview" o nombre de etapa para volver`;
    } else if (zoomLevel === ZOOM_LEVEL.BY_STAGE && selectedStage) {
      infoText = `💡 Click en documento para ver su flujo • Mantén Shift para tooltips • Click en "Overview" para volver`;
    } else {
      const collapsedCount = collapsedGroups.size;
      infoText = collapsedCount === 0
        ? `${normalizedDocuments.length} docs • Click en etapa para filtrar • Mantén Shift para ver detalles • Doble click en tags para colapsar`
        : collapsedCount === 2
          ? `${normalizedDocuments.length} docs colapsados • Mantén Shift para ver detalles • Doble click en tags para expandir`
          : `Vista mixta • Click en etapa para drill-down • Shift+hover muestra tooltips`;
    }
    
    g.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', -50)
      .attr('text-anchor', 'middle')
      .attr('font-size', '12px')
      .attr('fill', '#94a3b8')
      .text(infoText);

    const renderOptions = {
      metricConfig,
      docMetricMax,
      aggregateMetricMax,
      onDocumentSelect: handleDocumentSelect,
      onStageSelected: handleStageZoom,
      setUserAdjustedCollapse,
      cleanupTooltips,
      inspectMode,
    };

    renderGroupedSankey(
      g, 
      groupedDocuments,
      groupedMetrics,
      displayedDocuments,
      documentsByStage,
      innerWidth, 
      innerHeight, 
      collapsedGroups,
      setCollapsedGroups,
      hoveredDoc,
      setHoveredDoc,
      zoomLevel,
      selectedStage,
      selectedDoc,
      setZoomLevel,
      setSelectedStage,
      setSelectedDoc,
      renderOptions
    );

  }, [
    data,
    normalizedDocuments,
    displayedDocuments,
    dimensions,
    hoveredDoc,
    collapsedGroups,
    groupedDocuments,
    groupedMetrics,
    documentsByStage,
    zoomLevel,
    selectedStage,
    selectedDoc,
    metricConfig,
    docMetricMax,
    aggregateMetricMax,
    handleDocumentSelect,
    handleStageZoom
  ]);

  const stageNames = { upload: 'Upload', ocr: 'OCR', chunking: 'Chunking', indexing: 'Indexing', insights: 'Insights', completed: 'Done' };

  const handleBreadcrumbClick = (level) => {
    if (level === 0) {
      setZoomLevel(ZOOM_LEVEL.OVERVIEW);
      setSelectedStage(null);
      setSelectedDoc(null);
      clearFilter('stage');
      clearFilter('documentId');
    } else if (level === 1) {
      setZoomLevel(ZOOM_LEVEL.BY_STAGE);
      setSelectedDoc(null);
      clearFilter('documentId');
    }
  };

  useEffect(() => {
    return () => {
      cleanupTooltips();
    };
  }, [cleanupTooltips]);

  const handleMouseLeave = () => {
    cleanupTooltips();
  };

  if (!normalizedDocuments || normalizedDocuments.length === 0) {
    return (
      <div className="sankey-container" ref={containerRef}>
        <div className="sankey-header">
          <h3>📊 Flujo de Documentos</h3>
          <p className="sankey-hint">No hay documentos para mostrar</p>
        </div>
      </div>
    );
  }

  const collapseAll = collapsedGroups.has('active') && collapsedGroups.has('inactive');
  const isDocZoomAvailable = Boolean(selectedDoc);

  return (
    <div className="sankey-container" ref={containerRef} onMouseLeave={handleMouseLeave}>
      <div className="sankey-header">
        <h3>📊 Flujo de Documentos</h3>
        <div className="sankey-controls">
          <div className="control-block">
            <span className="control-label">Vista</span>
            {ZOOM_CONFIG.map((option) => (
              <button
                key={option.level}
                className={`control-pill ${zoomLevel === option.level ? 'active' : ''}`}
                disabled={option.level === ZOOM_LEVEL.BY_DOCUMENT && !isDocZoomAvailable}
                onClick={() => handleZoomControl(option.level)}
                title={option.hint}
              >
                {option.label}
              </button>
            ))}
          </div>
          <div className="control-block">
            <span className="control-label">Métrica</span>
            {Object.entries(METRIC_OPTIONS).map(([key, option]) => (
              <button
                key={key}
                className={`control-pill ${metricMode === key ? 'active' : ''}`}
                onClick={() => setMetricMode(key)}
                title={option.legend}
              >
                {option.label}
              </button>
            ))}
          </div>
          <button
            className="control-pill secondary"
            onClick={handleGroupToggle}
            title="Alternar agrupación Activos/Inactivos"
          >
            {collapseAll ? 'Expandir grupos' : 'Agrupar Activos/Inactivos'}
          </button>
        </div>
        <div className="sankey-breadcrumb">
          <span
            className={`sankey-breadcrumb-item ${zoomLevel === ZOOM_LEVEL.OVERVIEW ? 'active' : 'clickable'}`}
            onClick={() => zoomLevel > 0 && handleBreadcrumbClick(0)}
          >
            Overview
          </span>
          {zoomLevel >= ZOOM_LEVEL.BY_STAGE && selectedStage && (
            <>
              <span className="sankey-breadcrumb-sep">›</span>
              <span
                className={`sankey-breadcrumb-item ${zoomLevel === ZOOM_LEVEL.BY_STAGE ? 'active' : 'clickable'}`}
                onClick={() => zoomLevel === ZOOM_LEVEL.BY_DOCUMENT && handleBreadcrumbClick(1)}
              >
                {stageNames[selectedStage] || selectedStage} ({documentsByStage[selectedStage]?.length || 0})
              </span>
            </>
          )}
          {zoomLevel === ZOOM_LEVEL.BY_DOCUMENT && selectedDoc && (
            <>
              <span className="sankey-breadcrumb-sep">›</span>
              <span className="sankey-breadcrumb-item active">
                {selectedDoc.filename?.slice(0, 40) || selectedDoc.document_id}
              </span>
            </>
          )}
        </div>
        <p className="sankey-hint">
          {zoomLevel === ZOOM_LEVEL.OVERVIEW && '💡 Click en etapa para filtrar • Doble click en tags para colapsar/expandir • Mantén Shift para ver detalles'}
          {zoomLevel === ZOOM_LEVEL.BY_STAGE && '💡 Click en documento para ver su flujo • Mantén Shift para ver detalles'}
          {zoomLevel === ZOOM_LEVEL.BY_DOCUMENT && '💡 Vista detalle de un documento (Shift muestra tooltips)'}
          {` • Métrica: ${metricConfig.label} • Shift ${inspectMode ? 'ACTIVO' : 'inactivo'}`}
        </p>
      </div>
      <svg ref={svgRef} className="sankey-svg"></svg>
    </div>
  );
}

// Default export for backwards compatibility
export default PipelineSankeyChart;

/**
 * Render grouped Sankey with tags on left + pipeline columns
 * Supports 3 zoom levels: Overview, By Stage, By Document
 */
function renderGroupedSankey(
  g,
  groupedDocuments,
  groupedMetrics,
  displayedDocuments,
  documentsByStage,
  innerWidth,
  innerHeight,
  collapsedGroups,
  setCollapsedGroups,
  hoveredDoc,
  setHoveredDoc,
  zoomLevel = 0,
  selectedStage = null,
  selectedDoc = null,
  setZoomLevel = () => {},
  setSelectedStage = () => {},
  setSelectedDoc = () => {},
  options = {}
) {
  const {
    metricConfig,
    docMetricMax,
    aggregateMetricMax,
    onDocumentSelect,
    onStageSelected,
    setUserAdjustedCollapse,
    cleanupTooltips = () => {},
    inspectMode = false
  } = options;
  const stages = ['upload', 'ocr', 'chunking', 'indexing', 'insights', 'completed'];
  const stageNames = {
    upload: 'Upload',
    ocr: 'OCR',
    chunking: 'Chunking',
    indexing: 'Indexing',
    insights: 'Insights',
    completed: 'Done'
  };
  
  const columnWidth = innerWidth / (stages.length + 1);
  const columnX = stages.map((_, i) => (i + 1) * columnWidth);

  // Draw pipeline column headers (clickable in Overview when zoomLevel === 0)
  stages.forEach((stage, i) => {
    const count = documentsByStage[stage]?.length || 0;
    
    const headerGroup = g.append('g')
      .attr('transform', `translate(${columnX[i]}, -35)`);
    
    if (zoomLevel === 0) {
      headerGroup
        .style('cursor', 'pointer')
        .on('mouseover', function() {
          d3.select(this).select('text').attr('fill', '#93c5fd');
        })
        .on('mouseout', function() {
          d3.select(this).select('text').attr('fill', stageColors[stage]);
        })
        .on('click', function() {
          if (count > 0) {
            if (onStageSelected) {
              onStageSelected(stage);
            } else {
              setZoomLevel(1);
              setSelectedStage(stage);
            }
          }
        });
    }
    
    headerGroup.append('text')
      .attr('x', 0)
      .attr('y', 0)
      .attr('text-anchor', 'middle')
      .attr('font-weight', 'bold')
      .attr('font-size', '14px')
      .attr('fill', stageColors[stage])
      .text(stageNames[stage]);
    
    g.append('text')
      .attr('x', columnX[i])
      .attr('y', -20)
      .attr('text-anchor', 'middle')
      .attr('font-size', '11px')
      .attr('fill', '#94a3b8')
      .text(`${count} docs`);
  });

  // Level 1 (By Stage) or Level 2 (By Document): render displayedDocuments directly
  if (zoomLevel === 1 || zoomLevel === 2) {
    const docs = displayedDocuments;
    if (docs.length === 0) return;
    
    const lineSpacing = docs.length === 1 ? 0 : 8;
    const totalHeight = docs.length === 1 ? 0 : (docs.length - 1) * lineSpacing;
    const startY = (innerHeight - totalHeight) / 2;
    
    renderIndividualFlows({
      g,
      docs,
      stages,
      columnX,
      startY,
      verticalSpacing: lineSpacing,
      hoveredDoc,
      setHoveredDoc,
      mapStageToColumn,
      enableDocClick: zoomLevel === 1,
      setZoomLevel,
      setSelectedDoc,
      metricConfig,
      docMetricMax,
      onDocumentSelect,
      cleanupTooltips,
      inspectMode
    });
    return;
  }

  // Level 0 (Overview): Draw group tags on the left + flow lines
  let yOffset = 0;
  const groupSpacing = innerHeight / 3;

  ['active', 'inactive'].forEach((groupId, groupIdx) => {
    const groupDocs = groupedDocuments[groupId] || [];
    if (groupDocs.length === 0) return;

    const isCollapsed = collapsedGroups.has(groupId);
    const groupInfo = GROUP_HIERARCHY[groupId];
    const metrics = groupedMetrics[groupId]?.metrics || aggregateGroupMetrics(groupDocs);
    
    const groupY = groupIdx * groupSpacing + 100;

    const tagGroup = g.append('g')
      .attr('transform', `translate(-120, ${groupY})`)
      .style('cursor', 'pointer')
      .on('dblclick', function() {
        if (setUserAdjustedCollapse) {
          setUserAdjustedCollapse(true);
        }
        setCollapsedGroups(prev => {
          const newSet = new Set(prev);
          if (newSet.has(groupId)) newSet.delete(groupId);
          else newSet.add(groupId);
          return newSet;
        });
      });

    tagGroup.append('rect')
      .attr('width', 110)
      .attr('height', isCollapsed ? 40 : 60)
      .attr('rx', 5)
      .attr('fill', groupInfo.color)
      .attr('opacity', 0.2)
      .attr('stroke', groupInfo.color)
      .attr('stroke-width', 2);

    tagGroup.append('text')
      .attr('x', 55)
      .attr('y', 20)
      .attr('text-anchor', 'middle')
      .attr('font-size', '14px')
      .attr('font-weight', 'bold')
      .attr('fill', groupInfo.color)
      .text(groupInfo.label);

    tagGroup.append('text')
      .attr('x', 55)
      .attr('y', 35)
      .attr('text-anchor', 'middle')
      .attr('font-size', '11px')
      .attr('fill', '#94a3b8')
      .text(`${metrics.count} docs`);

    if (!isCollapsed) {
      tagGroup.append('text')
        .attr('x', 55)
        .attr('y', 52)
        .attr('text-anchor', 'middle')
        .attr('font-size', '10px')
        .attr('fill', '#6b7280')
        .text('⇄ doble click');
    }

    if (isCollapsed) {
      renderAggregatedFlow({
        g,
        docs: groupDocs,
        stages,
        columnX,
        groupY,
        color: groupInfo.color,
        mapStageToColumn,
        metricConfig,
        aggregateMetricMax,
        groupMetrics: groupedMetrics[groupId]
      });
    } else {
      renderIndividualFlows({
        g,
        docs: groupDocs,
        stages,
        columnX,
        startY: groupY,
        verticalSpacing: 3,
        hoveredDoc,
        setHoveredDoc,
        mapStageToColumn,
        enableDocClick: false,
        metricConfig,
        docMetricMax,
        onDocumentSelect,
        cleanupTooltips,
        inspectMode
      });
    }

    yOffset += isCollapsed ? 100 : (groupDocs.length * 3 + 150);
  });
}

/**
 * Render aggregated thick line for collapsed group
 */
function renderAggregatedFlow({
  g,
  docs,
  stages,
  columnX,
  groupY,
  color,
  mapStageToColumn,
  metricConfig,
  aggregateMetricMax,
  groupMetrics
}) {
  if (docs.length === 0) return;

  // Calculate max stage reached by any document in group
  const maxStageIndex = Math.max(...docs.map(doc => {
    const stage = mapStageToColumn(doc);
    return stages.indexOf(stage);
  }));

  // Draw thick line from start to max stage
  for (let i = 0; i < maxStageIndex; i++) {
    const startX = columnX[i];
    const endX = columnX[i + 1];
    const metrics = groupMetrics?.metrics || aggregateGroupMetrics(docs);
    const strokeWidth = calculateCollapsedStrokeWidth(
      metrics,
      metricConfig?.aggregateKey || 'count',
      aggregateMetricMax || (metrics[metricConfig?.aggregateKey] || docs.length || 1)
    );

    g.append('line')
      .attr('x1', 0) // Start from left (after tag)
      .attr('y1', groupY)
      .attr('x2', endX)
      .attr('y2', groupY)
      .attr('stroke', color)
      .attr('stroke-width', strokeWidth)
      .attr('opacity', 0.6)
      .attr('stroke-linecap', 'round');
  }

  // Label with count
  g.append('text')
    .attr('x', columnX[maxStageIndex] + 10)
    .attr('y', groupY + 5)
    .attr('font-size', '11px')
    .attr('fill', color)
    .text(`${docs.length} docs`);
}

/**
 * Render individual lines for expanded group
 * @param {boolean} enableDocClick - When true (Level 1), click navigates to Level 2
 * @param {Function} setZoomLevel - Optional, for drill-down
 * @param {Function} setSelectedDoc - Optional, for drill-down
 */
function renderIndividualFlows({
  g,
  docs,
  stages,
  columnX,
  startY,
  verticalSpacing,
  hoveredDoc,
  setHoveredDoc,
  mapStageToColumn,
  enableDocClick = false,
  setZoomLevel = null,
  setSelectedDoc = null,
  metricConfig,
  docMetricMax,
  onDocumentSelect,
  cleanupTooltips = () => {},
  inspectMode = false
}) {
  const spacing = verticalSpacing ?? Math.max(3, 20 / docs.length);

  docs.forEach((doc, idx) => {
    const currentColumn = mapStageToColumn(doc);
    const currentIndex = stages.indexOf(currentColumn);
    
    if (currentIndex === -1) return;
    
    const yPosition = startY + (idx * spacing);
    const isHovered = hoveredDoc === doc.document_id;

    for (let i = 0; i < currentIndex; i++) {
      const startX = (i === 0) ? 0 : columnX[i];
      const endX = columnX[i + 1];
      const endStage = stages[i + 1];
      
      const metricValue = metricConfig?.docValue ? metricConfig.docValue(doc) : 1;
      const baseWidth = getLineWidth(metricValue, docMetricMax);
      const strokeWidth = isHovered ? baseWidth + 1 : baseWidth;
      const isActive = (doc.status && doc.status.endsWith('_processing')) && i === currentIndex - 1;

      const lineGroup = g.append('g');
      
      // Invisible hit area for easier clicking
      lineGroup.append('rect')
        .attr('x', startX)
        .attr('y', yPosition - 6)
        .attr('width', endX - startX)
        .attr('height', 12)
        .attr('fill', 'transparent');
      
      lineGroup.append('line')
        .attr('x1', startX)
        .attr('y1', yPosition)
        .attr('x2', endX)
        .attr('y2', yPosition)
        .attr('stroke', isActive ? stageColors[endStage] : '#6b7280')
        .attr('stroke-width', strokeWidth)
        .attr('opacity', isHovered ? 1 : (isActive ? 0.7 : 0.3));

      lineGroup
        .style('cursor', 'pointer')
        .on('mouseover', function(event) {
          if (!inspectMode) {
            return;
          }
          setHoveredDoc(doc.document_id);
          cleanupTooltips();
          const tooltipHTML = `${generateTooltipHTML(doc, currentColumn, isActive)}<hr style="margin:4px 0;border-color:#334155;"><small>Métrica ${metricConfig?.label || 'Documentos'}: ${Math.max(0, Math.round(metricValue))}</small>`;
          d3.select('body').append('div')
            .attr('class', 'sankey-tooltip')
            .style('position', 'absolute')
            .style('background', '#1e1e2e')
            .style('color', '#fff')
            .style('padding', '8px 12px')
            .style('border-radius', '4px')
            .style('border', '1px solid #4dd0e1')
            .style('pointer-events', 'none')
            .style('z-index', 1000)
            .html(tooltipHTML)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 10) + 'px');
        })
        .on('mouseout', function() {
          setHoveredDoc(null);
          cleanupTooltips();
        })
        .on('click', function() {
          if (enableDocClick && setZoomLevel && setSelectedDoc) {
            setZoomLevel(2);
            setSelectedDoc(doc);
          }
          if (onDocumentSelect) {
            onDocumentSelect(doc);
          }
        });
    }
  });
}

function getLineWidth(value, maxValue = 1) {
  const safeMax = Math.max(maxValue, 1);
  const normalized = Math.min(value / safeMax, 1);
  const MIN_WIDTH = 1;
  const MAX_WIDTH = 14;
  return MIN_WIDTH + normalized * (MAX_WIDTH - MIN_WIDTH);
}
