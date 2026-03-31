import React from 'react';
import './PipelineSummaryCard.css';

function formatPercent(value) {
  if (Number.isNaN(value) || value === null || value === undefined) {
    return '0%';
  }
  return `${Math.round(value)}%`;
}

export default function PipelineSummaryCard({ files, newsItems, insights }) {
  const totalDocs = files?.total || 0;
  const completedDocs = files?.completed || 0;
  const insightsDone = insights?.done || 0;
  const insightsTotal = insights?.total || 0;
  const newsPending = newsItems?.pending || 0;

  return (
    <div className="pipeline-summary-card">
      <div className="pipeline-summary-card__row">
        <div className="pipeline-summary-card__metric">
          <span>Docs procesados</span>
          <strong>{completedDocs}/{totalDocs}</strong>
          <small>{formatPercent(files?.percentage_done)}</small>
        </div>
        <div className="pipeline-summary-card__metric">
          <span>Insights listos</span>
          <strong>{insightsDone}/{insightsTotal || '∞'}</strong>
          <small>{formatPercent(insights?.percentage_done)}</small>
        </div>
        <div className="pipeline-summary-card__metric">
          <span>News pendientes</span>
          <strong>{newsPending}</strong>
          <small>cola activa</small>
        </div>
      </div>
      <div className="pipeline-summary-card__bar">
        <div
          className="pipeline-summary-card__fill"
          style={{ width: `${Math.min(100, files?.percentage_done || 0)}%` }}
        />
      </div>
      <p className="pipeline-summary-card__hint">
        La barra muestra el avance global de documentos completados.
      </p>
    </div>
  );
}
