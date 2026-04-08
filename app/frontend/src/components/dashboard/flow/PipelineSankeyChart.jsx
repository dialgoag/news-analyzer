/**
 * PipelineSankeyChart Component
 * 
 * D3 Sankey diagram for pipeline flow visualization
 * Shows document flow between stages with volumes
 * 
 * Pattern: React owns SVG structure, D3 calculates Sankey layout
 */

import React, { useMemo, useState, useRef } from 'react';
import PropTypes from 'prop-types';
import * as d3 from 'd3';
import { sankey, sankeyLinkHorizontal } from 'd3-sankey';
import { transformForSankey } from '../../../services/documentDataService';
import './PipelineSankeyChart.css';

export function PipelineSankeyChart({
  analysisData,
  width = 960,
  height = 500
}) {
  const [hoveredNode, setHoveredNode] = useState(null);
  const [hoveredLink, setHoveredLink] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const containerRef = useRef();

  // Memoize Sankey layout
  const { nodes, links } = useMemo(() => {
    if (!analysisData) {
      return { nodes: [], links: [] };
    }

    const margin = { top: 40, right: 160, bottom: 40, left: 20 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // Transform data
    const { nodes: rawNodes, links: rawLinks } = transformForSankey(analysisData);

    if (rawNodes.length === 0) {
      return { nodes: [], links: [] };
    }

    // Create Sankey generator
    const sankeyGenerator = sankey()
      .nodeWidth(24)
      .nodePadding(20)
      .extent([[0, 0], [innerWidth, innerHeight]]);

    // Generate layout
    const { nodes, links } = sankeyGenerator({
      nodes: rawNodes.map(d => ({ ...d })),
      links: rawLinks.map(d => ({ ...d }))
    });

    return { nodes, links, margin };
  }, [analysisData, width, height]);

  const handleNodeHover = (node, event) => {
    if (!node) {
      setHoveredNode(null);
      return;
    }

    setHoveredNode(node);
    
    if (event && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setTooltipPos({
        x: event.clientX - rect.left + 12,
        y: event.clientY - rect.top + 12
      });
    }
  };

  const handleLinkHover = (link, event) => {
    if (!link) {
      setHoveredLink(null);
      return;
    }

    setHoveredLink(link);
    
    if (event && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setTooltipPos({
        x: event.clientX - rect.left + 12,
        y: event.clientY - rect.top + 12
      });
    }
  };

  if (!nodes || nodes.length === 0) {
    return (
      <div className="pipeline-sankey-chart pipeline-sankey-chart--empty">
        <p>No pipeline data available</p>
      </div>
    );
  }

  const { margin } = nodes[0] ? { margin: { top: 40, right: 160, bottom: 40, left: 20 } } : {};

  return (
    <div className="pipeline-sankey-chart" ref={containerRef}>
      <svg 
        width={width} 
        height={height}
        className="sankey-chart__svg"
        role="img"
        aria-label="Pipeline flow Sankey diagram"
      >
        <g transform={`translate(${margin.left}, ${margin.top})`}>
          {/* Links (flows) */}
          <g className="sankey-links">
            {links.map((link, i) => {
              const isHovered = hoveredLink === link;
              const isRelated = hoveredNode && 
                (hoveredNode === link.source || hoveredNode === link.target);
              const opacity = isHovered || isRelated ? 0.7 : 
                              (hoveredNode || hoveredLink) ? 0.15 : 0.4;

              return (
                <g key={i}>
                  {/* Link path */}
                  <path
                    d={sankeyLinkHorizontal()(link)}
                    fill="none"
                    stroke={link.source.color || '#94a3b8'}
                    strokeWidth={Math.max(1, link.width)}
                    opacity={opacity}
                    className="sankey-link__path"
                    onMouseEnter={(e) => handleLinkHover(link, e)}
                    onMouseLeave={() => handleLinkHover(null)}
                  />
                  
                  {/* Link value label (on hover) */}
                  {isHovered && (
                    <text
                      x={(link.source.x1 + link.target.x0) / 2}
                      y={(link.y0 + link.y1) / 2}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      className="sankey-link__label"
                      fill="#f1f5f9"
                    >
                      {link.value}
                    </text>
                  )}
                </g>
              );
            })}
          </g>

          {/* Nodes (stages) */}
          <g className="sankey-nodes">
            {nodes.map((node, i) => {
              const isHovered = hoveredNode === node;
              const isRelated = hoveredLink && 
                (hoveredLink.source === node || hoveredLink.target === node);
              const opacity = isHovered || isRelated ? 1 : 
                              (hoveredNode || hoveredLink) ? 0.5 : 1;

              return (
                <g key={i}>
                  {/* Node rectangle */}
                  <rect
                    x={node.x0}
                    y={node.y0}
                    width={node.x1 - node.x0}
                    height={node.y1 - node.y0}
                    fill={node.color}
                    opacity={opacity}
                    stroke={isHovered ? '#fff' : 'none'}
                    strokeWidth={2}
                    rx={4}
                    className="sankey-node__rect"
                    onMouseEnter={(e) => handleNodeHover(node, e)}
                    onMouseLeave={() => handleNodeHover(null)}
                  />

                  {/* Node label */}
                  <text
                    x={node.x1 + 8}
                    y={(node.y0 + node.y1) / 2}
                    dominantBaseline="middle"
                    className="sankey-node__label"
                    fill={node.color}
                  >
                    {node.name}
                  </text>

                  {/* Node value */}
                  <text
                    x={node.x1 + 8}
                    y={(node.y0 + node.y1) / 2 + 14}
                    dominantBaseline="middle"
                    className="sankey-node__value"
                    fill="#94a3b8"
                  >
                    {node.value} docs
                  </text>
                </g>
              );
            })}
          </g>
        </g>
      </svg>

      {/* Tooltip */}
      {(hoveredNode || hoveredLink) && (
        <div
          className="sankey-chart__tooltip"
          style={{
            position: 'absolute',
            left: `${tooltipPos.x}px`,
            top: `${tooltipPos.y}px`,
            pointerEvents: 'none'
          }}
          role="tooltip"
        >
          {hoveredNode && (
            <div>
              <strong>{hoveredNode.name}</strong><br />
              Total: {hoveredNode.value} documents<br />
              {hoveredNode.meta && (
                <>
                  <hr style={{ margin: '6px 0', borderColor: '#334155', opacity: 0.3 }} />
                  ✅ Done: {hoveredNode.meta.done}<br />
                  🔄 Processing: {hoveredNode.meta.processing}<br />
                  ⏳ Pending: {hoveredNode.meta.pending}<br />
                  ❌ Errors: {hoveredNode.meta.error}
                </>
              )}
            </div>
          )}
          {hoveredLink && (
            <div>
              <strong>{hoveredLink.source.name} → {hoveredLink.target.name}</strong><br />
              {hoveredLink.value} documents flowing<br />
              <small style={{ color: '#94a3b8' }}>
                {Math.round((hoveredLink.value / hoveredLink.source.value) * 100)}% of source
              </small>
            </div>
          )}
        </div>
      )}

      {/* Legend */}
      <div className="sankey-chart__legend">
        <div className="legend-item">
          <div className="legend-node" style={{ background: '#3b82f6' }} />
          <span>Document Flow</span>
        </div>
        <div className="legend-item">
          <div className="legend-thickness" />
          <span>Width = Document Count</span>
        </div>
      </div>
    </div>
  );
}

PipelineSankeyChart.propTypes = {
  analysisData: PropTypes.object.isRequired,
  width: PropTypes.number,
  height: PropTypes.number
};

export default PipelineSankeyChart;
