/**
 * Enhanced KPICard Component
 * 
 * Displays a KPI with:
 * - Current value (large number)
 * - Sparkline trend (mini chart)
 * - Comparison indicator (↑↓ with percentage)
 * - Tooltip with details
 * 
 * Replaces the simpler KPIsInline badges
 */

import React, { useState } from 'react';
import PropTypes from 'prop-types';
import KPISparkline from './KPISparkline';
import './KPICard.css';

export function KPICard({
  label,
  value,
  icon: Icon,
  sparklineData = [],
  comparison = null,
  color = '#4caf50',
  status = 'normal', // 'normal' | 'warning' | 'error'
  tooltip = null
}) {
  const [showTooltip, setShowTooltip] = useState(false);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  const handleMouseEnter = (e) => {
    if (!tooltip) return;
    const rect = e.currentTarget.getBoundingClientRect();
    setTooltipPos({ x: rect.left, y: rect.bottom + 8 });
    setShowTooltip(true);
  };

  const handleMouseLeave = () => {
    setShowTooltip(false);
  };

  // Status styling
  const statusClass = status === 'error' ? 'kpi-card--error' : 
                       status === 'warning' ? 'kpi-card--warning' : '';

  // Comparison styling
  const comparisonClass = comparison?.direction === 'up' ? 'comparison--up' :
                           comparison?.direction === 'down' ? 'comparison--down' : 
                           'comparison--stable';

  const comparisonColor = comparison?.isImprovement ? '#4caf50' : '#f59e0b';

  return (
    <>
      <div 
        className={`kpi-card ${statusClass}`}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        role="article"
        aria-label={`${label}: ${value}`}
      >
        {/* Header: Icon + Label */}
        <div className="kpi-card__header">
          {Icon && <Icon className="kpi-card__icon" aria-hidden="true" />}
          <span className="kpi-card__label">{label}</span>
        </div>

        {/* Main Value */}
        <div className="kpi-card__value" style={{ color }}>
          {typeof value === 'number' ? value.toLocaleString() : value}
        </div>

        {/* Sparkline + Comparison Row */}
        <div className="kpi-card__trend-row">
          {/* Sparkline */}
          <div className="kpi-card__sparkline">
            {sparklineData.length > 0 ? (
              <KPISparkline
                data={sparklineData}
                width={100}
                height={32}
                color={color}
                showArea={true}
                showDots={false}
              />
            ) : (
              <div className="kpi-card__no-data">—</div>
            )}
          </div>

          {/* Comparison Indicator */}
          {comparison && (
            <div 
              className={`kpi-card__comparison ${comparisonClass}`}
              style={{ color: comparisonColor }}
              aria-label={`${comparison.direction === 'up' ? 'Increased' : comparison.direction === 'down' ? 'Decreased' : 'Stable'} by ${Math.abs(comparison.changePercent)}%`}
            >
              <span className="comparison__indicator">
                {comparison.indicator}
              </span>
              <span className="comparison__value">
                {Math.abs(comparison.change)}
              </span>
              <span className="comparison__percent">
                ({Math.abs(comparison.changePercent)}%)
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Tooltip */}
      {showTooltip && tooltip && (
        <div
          className="kpi-card__tooltip"
          style={{
            position: 'fixed',
            left: `${tooltipPos.x}px`,
            top: `${tooltipPos.y}px`,
            zIndex: 1000
          }}
          role="tooltip"
        >
          <div dangerouslySetInnerHTML={{ __html: tooltip }} />
        </div>
      )}
    </>
  );
}

KPICard.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]).isRequired,
  icon: PropTypes.elementType,
  sparklineData: PropTypes.array,
  comparison: PropTypes.shape({
    change: PropTypes.number,
    changePercent: PropTypes.number,
    direction: PropTypes.oneOf(['up', 'down', 'stable']),
    isImprovement: PropTypes.bool,
    indicator: PropTypes.string
  }),
  color: PropTypes.string,
  status: PropTypes.oneOf(['normal', 'warning', 'error']),
  tooltip: PropTypes.string
};

export default KPICard;
