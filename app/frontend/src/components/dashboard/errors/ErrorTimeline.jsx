/**
 * ErrorTimeline Component
 * 
 * Sparkline timeline showing error frequency over time
 * Shows temporal patterns for error diagnosis
 * 
 * Pattern: React owns SVG, D3 calculates scales and area
 */

import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import * as d3 from 'd3';
import './ErrorTimeline.css';

export function ErrorTimeline({
  data = [],
  width = 600,
  height = 120,
  hours = 24
}) {
  // Memoize scales and paths
  const { xScale, yScale, areaPath, linePath, timeFormat } = useMemo(() => {
    if (!data || data.length === 0) {
      return { xScale: null, yScale: null, areaPath: null, linePath: null, timeFormat: null };
    }

    const margin = { top: 20, right: 20, bottom: 30, left: 40 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // X scale: time
    const timeExtent = d3.extent(data, d => d.timestamp);
    const xScale = d3.scaleTime()
      .domain(timeExtent)
      .range([0, innerWidth]);

    // Y scale: error count
    const maxCount = d3.max(data, d => d.count) || 1;
    const yScale = d3.scaleLinear()
      .domain([0, maxCount])
      .range([innerHeight, 0])
      .nice();

    // Area generator (stacked by severity)
    const area = d3.area()
      .x(d => xScale(d.timestamp))
      .y0(innerHeight)
      .y1(d => yScale(d.count))
      .curve(d3.curveMonotoneX);

    // Line generator
    const line = d3.line()
      .x(d => xScale(d.timestamp))
      .y(d => yScale(d.count))
      .curve(d3.curveMonotoneX);

    // Time format
    const timeFormat = hours <= 24 
      ? d3.timeFormat('%H:%M')
      : d3.timeFormat('%m/%d %H:%M');

    return {
      xScale,
      yScale,
      areaPath: area(data),
      linePath: line(data),
      timeFormat,
      margin,
      innerWidth,
      innerHeight
    };
  }, [data, width, height, hours]);

  if (!data || data.length === 0) {
    return (
      <div className="error-timeline error-timeline--empty">
        <p>No error history available</p>
      </div>
    );
  }

  if (!xScale) return null;

  const { margin, innerWidth, innerHeight } = yScale ? 
    { margin: { top: 20, right: 20, bottom: 30, left: 40 }, innerWidth: width - 60, innerHeight: height - 50 } : 
    {};

  return (
    <div className="error-timeline">
      <svg 
        width={width} 
        height={height}
        className="error-timeline__svg"
        role="img"
        aria-label={`Error timeline: Last ${hours} hours`}
      >
        <g transform={`translate(${margin.left}, ${margin.top})`}>
          {/* Grid lines */}
          <g className="error-timeline__grid">
            {yScale.ticks(4).map(tick => (
              <g key={tick} transform={`translate(0, ${yScale(tick)})`}>
                <line
                  x1={0}
                  x2={innerWidth}
                  stroke="rgba(148, 163, 184, 0.1)"
                  strokeWidth={1}
                  strokeDasharray="2,2"
                />
              </g>
            ))}
          </g>

          {/* Area fill */}
          {areaPath && (
            <path
              d={areaPath}
              fill="url(#errorGradient)"
              opacity={0.6}
            />
          )}

          {/* Line */}
          {linePath && (
            <path
              d={linePath}
              fill="none"
              stroke="#f44336"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Data points */}
          {data.map((d, i) => {
            const isHigh = d.critical > 0 || d.high > 0;
            return (
              <circle
                key={i}
                cx={xScale(d.timestamp)}
                cy={yScale(d.count)}
                r={isHigh ? 4 : 2.5}
                fill={isHigh ? '#f44336' : '#f59e0b'}
                stroke="#fff"
                strokeWidth={1}
                className="error-timeline__dot"
              />
            );
          })}

          {/* X axis */}
          <g transform={`translate(0, ${innerHeight})`}>
            <line x1={0} x2={innerWidth} stroke="#475569" strokeWidth={1} />
            {xScale.ticks(6).map(tick => (
              <g key={tick} transform={`translate(${xScale(tick)}, 0)`}>
                <line y1={0} y2={4} stroke="#475569" strokeWidth={1} />
                <text
                  y={16}
                  textAnchor="middle"
                  className="error-timeline__axis-label"
                  fill="#94a3b8"
                >
                  {timeFormat(tick)}
                </text>
              </g>
            ))}
          </g>

          {/* Y axis */}
          <g>
            <line y1={0} y2={innerHeight} stroke="#475569" strokeWidth={1} />
            {yScale.ticks(4).map(tick => (
              <g key={tick} transform={`translate(0, ${yScale(tick)})`}>
                <line x1={-4} x2={0} stroke="#475569" strokeWidth={1} />
                <text
                  x={-8}
                  textAnchor="end"
                  dominantBaseline="middle"
                  className="error-timeline__axis-label"
                  fill="#94a3b8"
                >
                  {tick}
                </text>
              </g>
            ))}
            <text
              x={-margin.left + 10}
              y={innerHeight / 2}
              textAnchor="middle"
              transform={`rotate(-90, ${-margin.left + 10}, ${innerHeight / 2})`}
              className="error-timeline__axis-title"
              fill="#cbd5e1"
            >
              Errors/hour
            </text>
          </g>

          {/* Gradient definition */}
          <defs>
            <linearGradient id="errorGradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#f44336" stopOpacity={0.8} />
              <stop offset="100%" stopColor="#f44336" stopOpacity={0.1} />
            </linearGradient>
          </defs>
        </g>
      </svg>
    </div>
  );
}

ErrorTimeline.propTypes = {
  data: PropTypes.arrayOf(PropTypes.shape({
    timestamp: PropTypes.instanceOf(Date).isRequired,
    count: PropTypes.number.isRequired,
    critical: PropTypes.number,
    high: PropTypes.number
  })).isRequired,
  width: PropTypes.number,
  height: PropTypes.number,
  hours: PropTypes.number
};

export default ErrorTimeline;
