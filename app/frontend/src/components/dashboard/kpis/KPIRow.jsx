/**
 * KPIRow Component
 * 
 * Container for 4-6 KPI cards in responsive grid
 * Orchestrates data from useDashboardData and passes to individual cards
 */

import React from 'react';
import PropTypes from 'prop-types';
import { 
  DocumentTextIcon, 
  NewspaperIcon, 
  SparklesIcon, 
  ExclamationCircleIcon 
} from '@heroicons/react/24/outline';
import KPICard from './KPICard';
import { 
  prepareSparklineData, 
  extractSparklineComparison,
  generateKPITooltipHTML 
} from '../../../services/documentDataService';
import './KPIRow.css';

export function KPIRow({ kpis, historicalData = [] }) {
  // Define KPI configurations
  const kpiConfigs = [
    {
      id: 'documents',
      label: 'Documentos',
      icon: DocumentTextIcon,
      color: '#3b82f6',
      getValue: () => kpis?.documents?.current || 0,
      getSparklineData: () => prepareSparklineData(historicalData, 'total_docs', 1),
      getStatus: () => {
        if (!kpis?.documents) return 'normal';
        const errorRate = kpis.documents.current > 0 
          ? (kpis.documents.errors / kpis.documents.current) 
          : 0;
        if (errorRate > 0.2) return 'error';
        if (errorRate > 0.1) return 'warning';
        return 'normal';
      }
    },
    {
      id: 'news',
      label: 'News Items',
      icon: NewspaperIcon,
      color: '#8b5cf6',
      getValue: () => kpis?.news?.current || 0,
      getSparklineData: () => prepareSparklineData(historicalData, 'total_news', 1),
      getStatus: () => {
        if (!kpis?.news) return 'normal';
        const errorRate = kpis.news.current > 0 
          ? (kpis.news.errors / kpis.news.current) 
          : 0;
        if (errorRate > 0.2) return 'error';
        if (errorRate > 0.1) return 'warning';
        return 'normal';
      }
    },
    {
      id: 'insights',
      label: 'Insights',
      icon: SparklesIcon,
      color: '#10b981',
      getValue: () => kpis?.insights?.current || 0,
      getSparklineData: () => prepareSparklineData(historicalData, 'total_insights', 1),
      getStatus: () => {
        if (!kpis?.insights) return 'normal';
        const errorRate = kpis.insights.current > 0 
          ? (kpis.insights.errors / kpis.insights.current) 
          : 0;
        if (errorRate > 0.2) return 'error';
        if (errorRate > 0.1) return 'warning';
        return 'normal';
      }
    },
    {
      id: 'errors',
      label: 'Errores',
      icon: ExclamationCircleIcon,
      color: '#f44336',
      getValue: () => kpis?.errors?.current || 0,
      getSparklineData: () => prepareSparklineData(historicalData, 'total_errors', 1),
      getStatus: () => {
        if (!kpis?.errors) return 'normal';
        if (kpis.errors.current === 0) return 'normal';
        if (kpis.errors.critical > 0) return 'error';
        return 'warning';
      }
    }
  ];

  return (
    <div className="kpi-row" role="region" aria-label="Key Performance Indicators">
      {kpiConfigs.map(config => {
        const value = config.getValue();
        const sparklineData = config.getSparklineData();
        const comparison = sparklineData.length > 0 
          ? extractSparklineComparison(sparklineData, 12)
          : null;
        const status = config.getStatus();
        
        const tooltip = generateKPITooltipHTML(
          { label: config.label, current: value },
          comparison || { change: 0, changePercent: 0, direction: 'stable', isImprovement: false }
        );

        return (
          <KPICard
            key={config.id}
            label={config.label}
            value={value}
            icon={config.icon}
            sparklineData={sparklineData}
            comparison={comparison}
            color={config.color}
            status={status}
            tooltip={tooltip}
          />
        );
      })}
    </div>
  );
}

KPIRow.propTypes = {
  kpis: PropTypes.shape({
    documents: PropTypes.object,
    news: PropTypes.object,
    insights: PropTypes.object,
    errors: PropTypes.object
  }).isRequired,
  historicalData: PropTypes.array
};

export default KPIRow;
