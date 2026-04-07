import React from 'react';
import './KPICard.css';

export function KPICard({ 
  icon: IconComponent, 
  label, 
  value, 
  total, 
  percentage, 
  status = 'info',
  trend,
  onClick 
}) {
  const formatPercent = (val) => {
    if (val === null || val === undefined || Number.isNaN(val)) return '0%';
    return `${Math.round(val)}%`;
  };

  return (
    <div 
      className={`kpi-card kpi-card--${status} ${onClick ? 'cursor-pointer' : ''}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyPress={(e) => {
        if (onClick && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onClick();
        }
      }}
    >
      {IconComponent && (
        <IconComponent className="kpi-card__icon" aria-hidden="true" />
      )}
      
      <span className="kpi-card__label">{label}</span>
      
      <div className="kpi-card__value">
        {value !== undefined && value !== null ? value : '—'}
        {total !== undefined && total !== null && `/${total}`}
      </div>
      
      {percentage !== undefined && percentage !== null && (
        <span className="kpi-card__percentage">{formatPercent(percentage)}</span>
      )}
      
      {trend && (
        <span className="kpi-card__trend">{trend}</span>
      )}
    </div>
  );
}

export default KPICard;
