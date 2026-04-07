import React from 'react';
import { 
  DocumentTextIcon, 
  SparklesIcon, 
  ClockIcon 
} from '@heroicons/react/24/outline';
import { KPICard } from './KPICard';
import './PipelineSummaryCard.css';

export default function PipelineSummaryCard({ files, newsItems, insights }) {
  const totalDocs = files?.total || 0;
  const completedDocs = files?.completed || 0;
  const insightsDone = insights?.done || 0;
  const insightsTotal = insights?.total || 0;
  const newsPending = newsItems?.pending || 0;
  const percentageDone = files?.percentage_done || 0;

  return (
    <div className="pipeline-summary-card">
      {/* KPI Cards Grid */}
      <div className="kpi-grid">
        <KPICard
          icon={DocumentTextIcon}
          label="Docs Procesados"
          value={completedDocs}
          total={totalDocs}
          percentage={percentageDone}
          status="completed"
        />
        
        <KPICard
          icon={SparklesIcon}
          label="Insights Listos"
          value={insightsDone}
          total={insightsTotal || '∞'}
          percentage={insights?.percentage_done}
          status="active"
        />
        
        <KPICard
          icon={ClockIcon}
          label="News Pendientes"
          value={newsPending}
          status="pending"
        />
      </div>
      
      {/* Progress Bar Stacked */}
      <div className="progress-section">
        <div className="progress-bar-stack">
          <div
            className="progress-segment progress-segment--completed"
            style={{ width: `${Math.min(100, percentageDone || 0)}%` }}
            title={`Completado: ${percentageDone.toFixed(1)}%`}
          />
          <div
            className="progress-segment progress-segment--processing"
            style={{ width: `${Math.min(100, (files?.processing_percentage || 0))}%` }}
            title={`Procesando: ${(files?.processing_percentage || 0).toFixed(1)}%`}
          />
          <div
            className="progress-segment progress-segment--pending"
            style={{ width: `${Math.max(0, 100 - percentageDone - (files?.processing_percentage || 0))}%` }}
            title={`Pendiente: ${(100 - percentageDone - (files?.processing_percentage || 0)).toFixed(1)}%`}
          />
        </div>
        
        {/* Legend */}
        <div className="progress-legend">
          <span className="legend-item">
            <span className="dot dot--completed" />
            Completado ({Math.round(percentageDone)}%)
          </span>
          <span className="legend-item">
            <span className="dot dot--processing" />
            Procesando ({Math.round(files?.processing_percentage || 0)}%)
          </span>
          <span className="legend-item">
            <span className="dot dot--pending" />
            Pendiente ({Math.round(100 - percentageDone - (files?.processing_percentage || 0))}%)
          </span>
        </div>
      </div>
    </div>
  );
}
