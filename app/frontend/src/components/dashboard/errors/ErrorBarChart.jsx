/**
 * ErrorBarChart Component
 * 
 * Horizontal sorted bar chart for error types
 * Shows count by error type with retry actions
 * 
 * Pattern: React owns SVG, D3 calculates scales and layout
 */

import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import * as d3 from 'd3';
import './ErrorBarChart.css';

export function ErrorBarChart({
  data = [],
  width = 600,
  height = 300,
  onBarClick = null,
  onRetryClick = null,
  selectedErrors = []
}) {
  // Memoize scales and bar positions
  const { xScale, barData } = useMemo(() => {
    if (!data || data.length === 0) {
      return { xScale: null, barData: [] };
    }

    const margin = { top: 20, right: 120, bottom: 40, left: 20 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    const barHeight = 32;
    const barGap = 8;

    // X scale: error count to width
    const maxCount = d3.max(data, d => d.count) || 1;
    const xScale = d3.scaleLinear()
      .domain([0, maxCount])
      .range([0, innerWidth])
      .nice();

    // Calculate bar positions (already sorted by service)
    const barData = data.map((error, index) => {
      const y = index * (barHeight + barGap);
      const barWidth = xScale(error.count);
      
      // Color by severity
      const color = error.severity === 'critical' ? '#f44336' :
                     error.severity === 'high' ? '#f59e0b' :
                     error.severity === 'medium' ? '#facc15' :
                     '#94a3b8';

      return {
        ...error,
        y,
        barWidth,
        barHeight,
        color,
        isSelected: selectedErrors.includes(error.error_message)
      };
    });

    return { xScale, barData, margin, innerWidth, innerHeight };
  }, [data, width, height, selectedErrors]);

  if (!data || data.length === 0) {
    return (
      <div className="error-bar-chart error-bar-chart--empty">
        <p>✅ No errors detected</p>
      </div>
    );
  }

  if (!xScale) return null;

  const { margin } = barData[0] ? { margin: { top: 20, right: 120, bottom: 40, left: 20 } } : {};

  return (
    <div className="error-bar-chart">
      <svg 
        width={width} 
        height={height}
        className="error-bar-chart__svg"
        role="img"
        aria-label={`Error bar chart: ${data.length} error types`}
      >
        <g transform={`translate(${margin.left}, ${margin.top})`}>
          {/* Bars */}
          {barData.map((error, index) => {
            const isSelected = error.isSelected;
            const opacity = isSelected ? 1 : selectedErrors.length > 0 ? 0.3 : 0.85;

            return (
              <g 
                key={error.error_message} 
                className={`error-bar-group ${isSelected ? 'error-bar-group--selected' : ''}`}
                style={{ cursor: 'pointer' }}
                onClick={() => onBarClick && onBarClick(error)}
              >
                {/* Background bar (full width, faint) */}
                <rect
                  x={0}
                  y={error.y}
                  width={xScale(xScale.domain()[1])}
                  height={error.barHeight}
                  fill={error.color}
                  fillOpacity={0.08}
                  rx={4}
                />

                {/* Actual count bar */}
                <rect
                  x={0}
                  y={error.y}
                  width={error.barWidth}
                  height={error.barHeight}
                  fill={error.color}
                  fillOpacity={opacity}
                  rx={4}
                  className="error-bar__rect"
                />

                {/* Severity icon */}
                <text
                  x={4}
                  y={error.y + error.barHeight / 2}
                  dominantBaseline="middle"
                  className="error-bar__icon"
                >
                  {error.severity === 'critical' ? '🔴' : 
                   error.severity === 'high' ? '🟠' :
                   error.severity === 'medium' ? '🟡' : '⚪'}
                </text>

                {/* Error message (truncated) */}
                <text
                  x={24}
                  y={error.y + error.barHeight / 2}
                  dominantBaseline="middle"
                  className="error-bar__label"
                  fill="#f1f5f9"
                >
                  {error.error_message.slice(0, 45)}
                  {error.error_message.length > 45 ? '...' : ''}
                </text>

                {/* Count value */}
                <text
                  x={error.barWidth - 8}
                  y={error.y + error.barHeight / 2}
                  textAnchor="end"
                  dominantBaseline="middle"
                  className="error-bar__count"
                  fill="#fff"
                >
                  {error.count}
                </text>

                {/* Retry button (if retriable) */}
                {error.canRetry && onRetryClick && (
                  <g
                    className="error-bar__retry-button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onRetryClick([error]);
                    }}
                    style={{ cursor: 'pointer' }}
                  >
                    <rect
                      x={xScale(xScale.domain()[1]) + 10}
                      y={error.y + 4}
                      width={90}
                      height={24}
                      fill="#3b82f6"
                      fillOpacity={0.2}
                      rx={4}
                      className="retry-button__bg"
                    />
                    <text
                      x={xScale(xScale.domain()[1]) + 55}
                      y={error.y + error.barHeight / 2}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      className="retry-button__text"
                      fill="#60a5fa"
                    >
                      Retry ({error.count})
                    </text>
                  </g>
                )}

                {/* Non-retriable indicator */}
                {!error.canRetry && (
                  <text
                    x={xScale(xScale.domain()[1]) + 10}
                    y={error.y + error.barHeight / 2}
                    dominantBaseline="middle"
                    className="error-bar__note"
                    fill="#64748b"
                  >
                    ❌ {error.note || 'Cannot retry'}
                  </text>
                )}
              </g>
            );
          })}

          {/* X axis */}
          <g transform={`translate(0, ${barData.length * 40})`}>
            <line
              x1={0}
              y1={0}
              x2={xScale(xScale.domain()[1])}
              y2={0}
              stroke="#475569"
              strokeWidth={1}
            />
            {xScale.ticks(5).map(tick => (
              <g key={tick} transform={`translate(${xScale(tick)}, 0)`}>
                <line y1={0} y2={4} stroke="#475569" strokeWidth={1} />
                <text
                  y={16}
                  textAnchor="middle"
                  className="error-bar__axis-label"
                  fill="#94a3b8"
                >
                  {tick}
                </text>
              </g>
            ))}
            <text
              x={xScale(xScale.domain()[1]) / 2}
              y={32}
              textAnchor="middle"
              className="error-bar__axis-title"
              fill="#cbd5e1"
            >
              Error Count
            </text>
          </g>
        </g>
      </svg>
    </div>
  );
}

ErrorBarChart.propTypes = {
  data: PropTypes.arrayOf(PropTypes.shape({
    error_message: PropTypes.string.isRequired,
    count: PropTypes.number.isRequired,
    severity: PropTypes.string.isRequired,
    canRetry: PropTypes.bool,
    note: PropTypes.string
  })).isRequired,
  width: PropTypes.number,
  height: PropTypes.number,
  onBarClick: PropTypes.func,
  onRetryClick: PropTypes.func,
  selectedErrors: PropTypes.arrayOf(PropTypes.string)
};

export default ErrorBarChart;
