/**
 * WorkerStatusPanel Component
 * 
 * Container for worker bullet charts in small multiples pattern
 * Shows capacity utilization for all worker types
 */

import React, { useState, useRef } from 'react';
import PropTypes from 'prop-types';
import WorkerBulletChart from './WorkerBulletChart';
import { 
  transformForBulletCharts, 
  sortWorkersByPriority,
  generateWorkerTooltipHTML,
  calculateOverallUtilization
} from '../../../services/workerDataService';
import './WorkerStatusPanel.css';

export function WorkerStatusPanel({ workerCapacity }) {
  const [hoveredWorker, setHoveredWorker] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const containerRef = useRef();

  // Transform and sort worker data
  const bulletChartData = transformForBulletCharts(workerCapacity);
  const sortedWorkers = sortWorkersByPriority(bulletChartData);
  const overallUtilization = calculateOverallUtilization(workerCapacity);

  const handleHover = (workerData, event) => {
    if (!workerData) {
      setHoveredWorker(null);
      return;
    }

    setHoveredWorker(workerData);
    
    if (event && containerRef.current) {
      const containerRect = containerRef.current.getBoundingClientRect();
      setTooltipPos({
        x: event.clientX - containerRect.left + 12,
        y: event.clientY - containerRect.top + 12
      });
    }
  };

  if (!bulletChartData || bulletChartData.length === 0) {
    return (
      <div className="worker-status-panel worker-status-panel--empty">
        <p>No worker data available</p>
      </div>
    );
  }

  return (
    <div className="worker-status-panel" ref={containerRef}>
      {/* Overall summary header */}
      <div className="worker-status-panel__header">
        <div className="worker-summary">
          <div className="worker-summary__metric">
            <span className="metric__label">Total Active</span>
            <span className="metric__value metric__value--active">
              {overallUtilization.active}
            </span>
          </div>
          <div className="worker-summary__metric">
            <span className="metric__label">Total Idle</span>
            <span className="metric__value metric__value--idle">
              {overallUtilization.idle}
            </span>
          </div>
          <div className="worker-summary__metric">
            <span className="metric__label">Max Capacity</span>
            <span className="metric__value metric__value--max">
              {overallUtilization.max}
            </span>
          </div>
          <div className="worker-summary__metric">
            <span className="metric__label">Overall Utilization</span>
            <span className={`metric__value metric__value--percent metric__value--${overallUtilization.status}`}>
              {overallUtilization.utilizationPercent}%
            </span>
          </div>
        </div>

        {/* Overall status indicator */}
        <div className={`worker-status-panel__status worker-status-panel__status--${overallUtilization.status}`}>
          {overallUtilization.status === 'critical' && (
            <span>🔴 High utilization - Consider scaling</span>
          )}
          {overallUtilization.status === 'warning' && (
            <span>⚠️ Moderate utilization - Monitor closely</span>
          )}
          {overallUtilization.status === 'good' && (
            <span>✅ Healthy utilization - Capacity available</span>
          )}
        </div>
      </div>

      {/* Bullet charts grid */}
      <div className="worker-status-panel__charts">
        {sortedWorkers.map(worker => (
          <WorkerBulletChart
            key={worker.type}
            data={worker}
            width={480}
            height={60}
            showLabel={true}
            onHover={handleHover}
          />
        ))}
      </div>

      {/* Legend */}
      <div className="worker-status-panel__legend">
        <div className="legend-item">
          <div className="legend-swatch legend-swatch--good" />
          <span>Good (0-60%)</span>
        </div>
        <div className="legend-item">
          <div className="legend-swatch legend-swatch--warning" />
          <span>Warning (61-90%)</span>
        </div>
        <div className="legend-item">
          <div className="legend-swatch legend-swatch--critical" />
          <span>Critical (91-100%)</span>
        </div>
        <div className="legend-item">
          <div className="legend-marker" />
          <span>Max capacity</span>
        </div>
      </div>

      {/* Tooltip */}
      {hoveredWorker && (
        <div
          className="worker-status-panel__tooltip"
          style={{
            position: 'absolute',
            left: `${tooltipPos.x}px`,
            top: `${tooltipPos.y}px`,
            pointerEvents: 'none'
          }}
          role="tooltip"
        >
          <div dangerouslySetInnerHTML={{ 
            __html: generateWorkerTooltipHTML(hoveredWorker) 
          }} />
        </div>
      )}

      {/* Help text */}
      <details className="worker-status-panel__help">
        <summary>💡 How to read bullet charts</summary>
        <div className="help-content">
          <p><strong>Colored bar</strong> = Current active workers</p>
          <p><strong>Background ranges</strong> = Good (green), Warning (orange), Critical (red) zones</p>
          <p><strong>Vertical line</strong> = Maximum capacity limit</p>
          <p><strong>Percentage</strong> = Current utilization</p>
          <br />
          <p><em>Charts are sorted by priority: Critical issues first, then warnings, then healthy workers.</em></p>
        </div>
      </details>
    </div>
  );
}

WorkerStatusPanel.propTypes = {
  workerCapacity: PropTypes.object.isRequired
};

export default WorkerStatusPanel;
