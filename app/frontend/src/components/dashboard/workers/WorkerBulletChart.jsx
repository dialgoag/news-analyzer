/**
 * WorkerBulletChart Component
 * 
 * D3 Bullet chart for worker capacity visualization
 * Shows: actual vs capacity with good/warning/critical ranges
 * 
 * Pattern: React owns SVG, D3 calculates geometry
 */

import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import * as d3 from 'd3';
import './WorkerBulletChart.css';

export function WorkerBulletChart({
  data,
  width = 320,
  height = 60,
  showLabel = true,
  onHover = null
}) {
  // Memoize scale and positions (D3 responsibility)
  const { xScale, positions } = useMemo(() => {
    if (!data) return { xScale: null, positions: null };

    const margin = { top: 20, right: 40, bottom: 10, left: showLabel ? 120 : 10 };
    const innerWidth = width - margin.left - margin.right;

    // X scale: 0 to max capacity
    const xScale = d3.scaleLinear()
      .domain([0, data.max])
      .range([0, innerWidth]);

    // Calculate positions for all elements
    const positions = {
      goodWidth: xScale(data.ranges.good),
      warningWidth: xScale(data.ranges.warning - data.ranges.good),
      criticalWidth: xScale(data.max - data.ranges.warning),
      currentWidth: xScale(data.current),
      targetX: xScale(data.max),
      margin
    };

    return { xScale, positions };
  }, [data, width, showLabel]);

  if (!data || !xScale) {
    return (
      <div className="worker-bullet-chart worker-bullet-chart--empty">
        No data
      </div>
    );
  }

  const { margin } = positions;
  const barHeight = 20;
  const barY = margin.top;

  // Status color for current bar
  const currentBarColor = data.status === 'critical' ? '#f44336' :
                           data.status === 'warning' ? '#f59e0b' :
                           data.color || '#4caf50';

  return (
    <div 
      className={`worker-bullet-chart worker-bullet-chart--${data.status}`}
      onMouseEnter={(e) => onHover && onHover(data, e)}
      onMouseLeave={() => onHover && onHover(null)}
    >
      <svg 
        width={width} 
        height={height}
        className="bullet-chart-svg"
        role="img"
        aria-label={`${data.label}: ${data.current} of ${data.max} workers active (${data.meta.utilizationPercent}%)`}
      >
        <g transform={`translate(${margin.left}, 0)`}>
          {/* Label */}
          {showLabel && (
            <text
              x={-8}
              y={barY + barHeight / 2}
              textAnchor="end"
              dominantBaseline="middle"
              className="bullet-chart__label"
            >
              {data.label}
            </text>
          )}

          {/* Background ranges */}
          <g className="bullet-chart__ranges">
            {/* Good range (lightest) */}
            <rect
              x={0}
              y={barY}
              width={positions.goodWidth}
              height={barHeight}
              fill="#4caf50"
              fillOpacity={0.15}
            />
            {/* Warning range (medium) */}
            <rect
              x={positions.goodWidth}
              y={barY}
              width={positions.warningWidth}
              height={barHeight}
              fill="#f59e0b"
              fillOpacity={0.2}
            />
            {/* Critical range (darkest) */}
            <rect
              x={positions.goodWidth + positions.warningWidth}
              y={barY}
              width={positions.criticalWidth}
              height={barHeight}
              fill="#f44336"
              fillOpacity={0.25}
            />
          </g>

          {/* Current value bar */}
          <rect
            x={0}
            y={barY + 2}
            width={positions.currentWidth}
            height={barHeight - 4}
            fill={currentBarColor}
            fillOpacity={0.9}
            rx={2}
            className="bullet-chart__current"
          />

          {/* Target marker (vertical line at max) */}
          <line
            x1={positions.targetX}
            y1={barY - 4}
            x2={positions.targetX}
            y2={barY + barHeight + 4}
            stroke="#0f172a"
            strokeWidth={3}
            className="bullet-chart__target"
          />

          {/* Value labels */}
          <text
            x={positions.currentWidth + 4}
            y={barY + barHeight / 2}
            dominantBaseline="middle"
            className="bullet-chart__value"
            fill={currentBarColor}
          >
            {data.current}
          </text>

          <text
            x={positions.targetX + 4}
            y={barY + barHeight / 2}
            dominantBaseline="middle"
            className="bullet-chart__max"
          >
            / {data.max}
          </text>

          {/* Utilization percentage */}
          <text
            x={positions.targetX + 28}
            y={barY + barHeight / 2}
            dominantBaseline="middle"
            className="bullet-chart__percent"
          >
            ({data.meta.utilizationPercent}%)
          </text>
        </g>
      </svg>

      {/* Status indicator badge */}
      <div className={`bullet-chart__status-badge bullet-chart__status-badge--${data.status}`}>
        {data.status === 'critical' ? '🔴' : data.status === 'warning' ? '⚠️' : '✅'}
      </div>
    </div>
  );
}

WorkerBulletChart.propTypes = {
  data: PropTypes.shape({
    type: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired,
    color: PropTypes.string,
    current: PropTypes.number.isRequired,
    max: PropTypes.number.isRequired,
    utilization: PropTypes.number.isRequired,
    ranges: PropTypes.shape({
      good: PropTypes.number.isRequired,
      warning: PropTypes.number.isRequired,
      critical: PropTypes.number.isRequired
    }).isRequired,
    status: PropTypes.oneOf(['good', 'warning', 'critical']).isRequired,
    meta: PropTypes.shape({
      active: PropTypes.number,
      idle: PropTypes.number,
      utilizationPercent: PropTypes.number,
      availableSlots: PropTypes.number
    }).isRequired
  }).isRequired,
  width: PropTypes.number,
  height: PropTypes.number,
  showLabel: PropTypes.bool,
  onHover: PropTypes.func
};

export default WorkerBulletChart;
