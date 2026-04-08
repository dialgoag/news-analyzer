/**
 * KPISparkline Component
 * 
 * Mini D3 sparkline chart for KPI trend visualization
 * Designed to fit inside KPI cards (compact, ~40px height)
 * 
 * Pattern: React owns SVG structure, D3 calculates geometry
 */

import React, { useMemo, useRef, useEffect } from 'react';
import * as d3 from 'd3';
import PropTypes from 'prop-types';

export function KPISparkline({ 
  data = [], 
  width = 120, 
  height = 40, 
  color = '#4caf50',
  showDots = false,
  showArea = true
}) {
  const svgRef = useRef();

  // Memoize scales (D3 responsibility)
  const { xScale, yScale, line, area } = useMemo(() => {
    if (!data || data.length === 0) {
      return { xScale: null, yScale: null, line: null, area: null };
    }

    const margin = { top: 4, right: 4, bottom: 4, left: 4 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // X scale: map index to horizontal position
    const xScale = d3.scaleLinear()
      .domain([0, data.length - 1])
      .range([0, innerWidth]);

    // Y scale: map value to vertical position (inverted)
    const values = data.map(d => d.value);
    const yMin = Math.min(...values, 0);
    const yMax = Math.max(...values);
    
    const yScale = d3.scaleLinear()
      .domain([yMin, yMax])
      .range([innerHeight, 0])
      .nice();

    // Line generator
    const line = d3.line()
      .x((d, i) => xScale(i))
      .y(d => yScale(d.value))
      .curve(d3.curveMonotoneX); // Smooth curve

    // Area generator (for fill under line)
    const area = d3.area()
      .x((d, i) => xScale(i))
      .y0(innerHeight)
      .y1(d => yScale(d.value))
      .curve(d3.curveMonotoneX);

    return { xScale, yScale, line, area };
  }, [data, width, height]);

  // Generate path data (memoized)
  const pathData = useMemo(() => {
    if (!line || !area || !data || data.length === 0) {
      return { linePath: '', areaPath: '' };
    }

    return {
      linePath: line(data),
      areaPath: area(data)
    };
  }, [line, area, data]);

  // No data state
  if (!data || data.length === 0) {
    return (
      <svg width={width} height={height}>
        <text
          x={width / 2}
          y={height / 2}
          textAnchor="middle"
          fill="#94a3b8"
          fontSize="10px"
        >
          No data
        </text>
      </svg>
    );
  }

  return (
    <svg 
      ref={svgRef} 
      width={width} 
      height={height}
      className="kpi-sparkline"
      aria-label={`Trend sparkline: ${data.length} data points`}
      role="img"
    >
      <g transform="translate(4, 4)">
        {/* Area fill (optional) */}
        {showArea && pathData.areaPath && (
          <path
            d={pathData.areaPath}
            fill={color}
            fillOpacity={0.15}
          />
        )}

        {/* Line */}
        {pathData.linePath && (
          <path
            d={pathData.linePath}
            fill="none"
            stroke={color}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}

        {/* Dots at data points (optional) */}
        {showDots && xScale && yScale && data.map((d, i) => (
          <circle
            key={i}
            cx={xScale(i)}
            cy={yScale(d.value)}
            r={2}
            fill={color}
            opacity={i === data.length - 1 ? 1 : 0.6}
          />
        ))}

        {/* Highlight last point */}
        {xScale && yScale && data.length > 0 && (
          <circle
            cx={xScale(data.length - 1)}
            cy={yScale(data[data.length - 1].value)}
            r={3}
            fill={color}
            stroke="#fff"
            strokeWidth={1.5}
          />
        )}
      </g>
    </svg>
  );
}

KPISparkline.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      timestamp: PropTypes.instanceOf(Date),
      value: PropTypes.number.isRequired
    })
  ).isRequired,
  width: PropTypes.number,
  height: PropTypes.number,
  color: PropTypes.string,
  showDots: PropTypes.bool,
  showArea: PropTypes.bool
};

export default KPISparkline;
