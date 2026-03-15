/**
 * PipelineSankeyChart Component - WITH SEMANTIC GROUPING
 * 
 * Layout:
 * - Left: Group tags (🟢 Activos, ⚫ No Activos) - Double click to collapse/expand
 * - Center: Pipeline columns (always visible: Upload → OCR → Chunking → ... → Done)
 * - Flows: Individual lines (expanded) or aggregated thick line (collapsed)
 * 
 * Interaction:
 * - Double click on group tag: Toggle collapse/expand for that group
 * - Collapsed: Single thick line representing all documents in group
 * - Expanded: Individual lines for each document
 */

import React, { useEffect, useRef, useMemo, useState } from 'react';
import * as d3 from 'd3';
import { useDashboardFilters } from '../hooks/useDashboardFilters.jsx';
import { 
  transformDocumentsForVisualization,
  calculateStrokeWidth,
  generateTooltipHTML,
  groupDocumentsByStage 
} from '../../services/documentDataService';
import {
  groupDocumentsByMetaGroup,
  aggregateGroupMetrics,
  GROUP_HIERARCHY
} from '../../services/semanticZoomService';
import './PipelineSankeyChart.css';
import './SemanticZoom.css';

// Stage colors (stage names: upload, ocr, chunking, indexing, insights, completed)
const stageColors = {
  upload: '#f59e0b',
  ocr: '#3b82f6',
  chunking: '#8b5cf6',
  indexing: '#ec4899',
  insights: '#10b981',
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

export function PipelineSankeyChart({ data, documents = [] }) {
  const svgRef = useRef();
  const containerRef = useRef();
  const { filters, updateFilter } = useDashboardFilters();
  const [hoveredDoc, setHoveredDoc] = useState(null);
  
  // Track which groups are collapsed (Set of group IDs: 'active', 'inactive')
  const [collapsedGroups, setCollapsedGroups] = useState(new Set());
  
  // Transform documents
  const normalizedDocuments = useMemo(() => 
    transformDocumentsForVisualization(documents),
    [documents]
  );
  
  // Group documents by meta-group (Active/Inactive)
  const groupedDocuments = useMemo(() => 
    groupDocumentsByMetaGroup(normalizedDocuments, mapStageToColumn),
    [normalizedDocuments]
  );
  
  // Group documents by current stage
  const documentsByStage = useMemo(() => 
    groupDocumentsByStage(normalizedDocuments, mapStageToColumn),
    [normalizedDocuments]
  );
  
  const [dimensions, setDimensions] = useState({ width: 900, height: 1200 });

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

    const { width, height } = dimensions;
    const margin = { top: 80, right: 20, bottom: 40, left: 150 }; // More space for tags
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // Clear
    d3.select(svgRef.current).selectAll("*").remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    // Main group
    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Info text
    const collapsedCount = collapsedGroups.size;
    const infoText = collapsedCount === 0
      ? `${normalizedDocuments.length} documentos expandidos • 💡 Doble click en tags para colapsar`
      : collapsedCount === 2
        ? `${normalizedDocuments.length} documentos colapsados • 💡 Doble click en tags para expandir`
        : `Vista mixta: ${collapsedCount}/2 grupos colapsados`;
    
    g.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', -50)
      .attr('text-anchor', 'middle')
      .attr('font-size', '12px')
      .attr('fill', '#94a3b8')
      .text(infoText);

    // Render the Sankey with groups
    renderGroupedSankey(
      g, 
      groupedDocuments,
      normalizedDocuments,
      documentsByStage,
      innerWidth, 
      innerHeight, 
      collapsedGroups,
      setCollapsedGroups,
      hoveredDoc,
      setHoveredDoc,
      updateFilter
    );

  }, [data, normalizedDocuments, dimensions, hoveredDoc, collapsedGroups, updateFilter, groupedDocuments, documentsByStage]);

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

  return (
    <div className="sankey-container" ref={containerRef}>
      <div className="sankey-header">
        <h3>📊 Flujo de Documentos (Agrupación Semántica)</h3>
        <p className="sankey-hint">
          💡 <strong>Doble click</strong> en tags de la izquierda para colapsar/expandir grupos
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
 */
function renderGroupedSankey(
  g,
  groupedDocuments,
  normalizedDocuments,
  documentsByStage,
  innerWidth,
  innerHeight,
  collapsedGroups,
  setCollapsedGroups,
  hoveredDoc,
  setHoveredDoc,
  updateFilter
) {
  // Define pipeline stages (columns - always visible)
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

  // Draw pipeline column headers
  stages.forEach((stage, i) => {
    const count = documentsByStage[stage]?.length || 0;
    
    g.append('text')
      .attr('x', columnX[i])
      .attr('y', -35)
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

  // Draw group tags on the left + flow lines
  let yOffset = 0;
  const groupSpacing = innerHeight / 3;

  ['active', 'inactive'].forEach((groupId, groupIdx) => {
    const groupDocs = groupedDocuments[groupId] || [];
    if (groupDocs.length === 0) return;

    const isCollapsed = collapsedGroups.has(groupId);
    const groupInfo = GROUP_HIERARCHY[groupId];
    const metrics = aggregateGroupMetrics(groupDocs);
    
    const groupY = groupIdx * groupSpacing + 100;

    // Group tag (left side) - Double clickeable
    const tagGroup = g.append('g')
      .attr('transform', `translate(-120, ${groupY})`)
      .style('cursor', 'pointer')
      .on('dblclick', function() {
        // Toggle collapse state for this group
        setCollapsedGroups(prev => {
          const newSet = new Set(prev);
          if (newSet.has(groupId)) {
            newSet.delete(groupId);
          } else {
            newSet.add(groupId);
          }
          return newSet;
        });
      });

    // Tag background
    tagGroup.append('rect')
      .attr('width', 110)
      .attr('height', isCollapsed ? 40 : 60)
      .attr('rx', 5)
      .attr('fill', groupInfo.color)
      .attr('opacity', 0.2)
      .attr('stroke', groupInfo.color)
      .attr('stroke-width', 2);

    // Tag icon + label
    tagGroup.append('text')
      .attr('x', 55)
      .attr('y', 20)
      .attr('text-anchor', 'middle')
      .attr('font-size', '14px')
      .attr('font-weight', 'bold')
      .attr('fill', groupInfo.color)
      .text(groupInfo.label);

    // Tag count
    tagGroup.append('text')
      .attr('x', 55)
      .attr('y', 35)
      .attr('text-anchor', 'middle')
      .attr('font-size', '11px')
      .attr('fill', '#94a3b8')
      .text(`${metrics.count} docs`);

    // Collapse indicator
    if (!isCollapsed) {
      tagGroup.append('text')
        .attr('x', 55)
        .attr('y', 52)
        .attr('text-anchor', 'middle')
        .attr('font-size', '10px')
        .attr('fill', '#6b7280')
        .text('⇄ doble click');
    }

    // Draw flow lines for this group
    if (isCollapsed) {
      // COLLAPSED: Single thick aggregated line
      renderAggregatedFlow(g, groupDocs, stages, columnX, groupY, groupInfo.color, mapStageToColumn);
    } else {
      // EXPANDED: Individual lines for each document
      renderIndividualFlows(g, groupDocs, stages, columnX, groupY, hoveredDoc, setHoveredDoc, updateFilter, mapStageToColumn);
    }

    yOffset += isCollapsed ? 100 : (groupDocs.length * 3 + 150);
  });
}

/**
 * Render aggregated thick line for collapsed group
 */
function renderAggregatedFlow(g, docs, stages, columnX, groupY, color, mapStageToColumn) {
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
    
    // Stroke width proportional to document count
    const strokeWidth = Math.min(50, Math.max(5, docs.length / 5));

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
 */
function renderIndividualFlows(g, docs, stages, columnX, startY, hoveredDoc, setHoveredDoc, updateFilter, mapStageToColumn) {
  const verticalSpacing = 3;

  docs.forEach((doc, idx) => {
    const currentColumn = mapStageToColumn(doc);
    const currentIndex = stages.indexOf(currentColumn);
    
    if (currentIndex === -1) return;
    
    const yPosition = startY + (idx * verticalSpacing);
    const isHovered = hoveredDoc === doc.document_id;

    // Draw segments between columns
    for (let i = 0; i < currentIndex; i++) {
      const startX = (i === 0) ? 0 : columnX[i]; // First segment starts from left
      const endX = columnX[i + 1];
      const endStage = stages[i + 1];
      
      const strokeWidth = isHovered ? 2 : 1;
      const isActive = (doc.status && doc.status.endsWith('_processing')) && i === currentIndex - 1;

      g.append('line')
        .attr('x1', startX)
        .attr('y1', yPosition)
        .attr('x2', endX)
        .attr('y2', yPosition)
        .attr('stroke', isActive ? stageColors[endStage] : '#6b7280')
        .attr('stroke-width', strokeWidth)
        .attr('opacity', isHovered ? 1 : (isActive ? 0.7 : 0.3))
        .style('cursor', 'pointer')
        .on('mouseover', function(event) {
          setHoveredDoc(doc.document_id);
          
          const tooltipHTML = generateTooltipHTML(doc, currentColumn, isActive);
          
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
          d3.selectAll('.sankey-tooltip').remove();
        })
        .on('click', function() {
          updateFilter({ documentId: doc.document_id });
        });
    }
  });
}
