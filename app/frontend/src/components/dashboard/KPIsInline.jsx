/**
 * KPIsInline Component
 * 
 * Compact horizontal KPI badges for dashboard header
 * Replaces large KPICard components to save vertical space
 */

import React from 'react';
import { 
  DocumentTextIcon, 
  NewspaperIcon, 
  SparklesIcon, 
  ExclamationCircleIcon 
} from '@heroicons/react/24/outline';
import './KPIsInline.css';

export function KPIsInline({ stats }) {
  const getStatusClass = (value, threshold = 0) => {
    if (!value || value === 0) return 'status-ok';
    if (value > threshold) return 'status-warning';
    return 'status-ok';
  };

  const badges = [
    {
      id: 'docs',
      icon: DocumentTextIcon,
      label: 'Documentos',
      value: stats?.total_docs || 0,
      status: getStatusClass(stats?.total_docs),
    },
    {
      id: 'news',
      icon: NewspaperIcon,
      label: 'News Items',
      value: stats?.total_news || 0,
      status: getStatusClass(stats?.total_news),
    },
    {
      id: 'insights',
      icon: SparklesIcon,
      label: 'Insights',
      value: stats?.total_insights || 0,
      status: getStatusClass(stats?.total_insights),
    },
    {
      id: 'errors',
      icon: ExclamationCircleIcon,
      label: 'Errores',
      value: stats?.total_errors || 0,
      status: stats?.total_errors > 0 ? 'status-error' : 'status-ok',
      highlight: stats?.total_errors > 0,
    },
  ];

  return (
    <div className="kpis-inline">
      {badges.map((badge) => {
        const Icon = badge.icon;
        return (
          <div
            key={badge.id}
            className={`kpi-badge ${badge.status} ${badge.highlight ? 'kpi-badge--highlight' : ''}`}
          >
            <Icon className="kpi-badge__icon" aria-hidden="true" />
            <span className="kpi-badge__label">{badge.label}</span>
            <span className="kpi-badge__value">{badge.value}</span>
          </div>
        );
      })}
    </div>
  );
}

export default KPIsInline;
