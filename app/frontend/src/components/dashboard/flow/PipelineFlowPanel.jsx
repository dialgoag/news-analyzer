/**
 * PipelineFlowPanel Component
 * 
 * Tabbed panel to switch between Sankey and Parallel Coordinates
 * Allows user to compare both visualizations
 */

import React, { useState, lazy, Suspense } from 'react';
import PropTypes from 'prop-types';
import PipelineSankeyChart from './PipelineSankeyChart';
import './PipelineFlowPanel.css';

// Lazy load Parallel Coordinates (heavy component)
const ParallelPipelineCoordinates = lazy(() => 
  import('../ParallelPipelineCoordinates')
);

const TABS = [
  {
    id: 'sankey',
    label: 'Sankey Flow',
    icon: '📊',
    description: 'Simplified flow view - Best for quick bottleneck identification'
  },
  {
    id: 'parallel',
    label: 'Parallel Coordinates',
    icon: '🗺️',
    description: 'Detailed flow view - Best for granular document tracking'
  }
];

export function PipelineFlowPanel({
  analysisData,
  parallelData,
  documents = [],
  width = 960
}) {
  const [activeTab, setActiveTab] = useState('sankey');

  return (
    <div className="pipeline-flow-panel">
      {/* Tab Navigation */}
      <div className="pipeline-flow-panel__tabs">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`tab-button ${activeTab === tab.id ? 'tab-button--active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
            aria-selected={activeTab === tab.id}
            role="tab"
          >
            <span className="tab-button__icon">{tab.icon}</span>
            <span className="tab-button__label">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab Description */}
      <div className="pipeline-flow-panel__description">
        {TABS.find(t => t.id === activeTab)?.description}
      </div>

      {/* Tab Content */}
      <div className="pipeline-flow-panel__content" role="tabpanel">
        {activeTab === 'sankey' && (
          <div className="tab-content">
            <PipelineSankeyChart
              analysisData={analysisData}
              width={width}
              height={500}
            />
          </div>
        )}

        {activeTab === 'parallel' && (
          <div className="tab-content">
            <Suspense fallback={
              <div className="tab-content__loading">
                <p>⏳ Loading detailed view...</p>
              </div>
            }>
              <ParallelPipelineCoordinates
                data={parallelData}
                documents={documents}
              />
            </Suspense>
          </div>
        )}
      </div>

      {/* Comparison Guide */}
      <details className="pipeline-flow-panel__guide">
        <summary>💡 Which view should I use?</summary>
        <div className="guide-content">
          <div className="guide-section">
            <h4>📊 Sankey Flow (Simplified)</h4>
            <ul>
              <li><strong>Best for:</strong> Quick operational monitoring</li>
              <li><strong>Shows:</strong> Overall flow, stage-level volumes, bottlenecks</li>
              <li><strong>Speed:</strong> Fast rendering, minimal interaction</li>
              <li><strong>Use when:</strong> You need a quick health check</li>
            </ul>
          </div>

          <div className="guide-section">
            <h4>🗺️ Parallel Coordinates (Detailed)</h4>
            <ul>
              <li><strong>Best for:</strong> Deep investigation, document-level tracking</li>
              <li><strong>Shows:</strong> Individual documents, bifurcation to news, topics, granular states</li>
              <li><strong>Speed:</strong> More complex, interactive filters</li>
              <li><strong>Use when:</strong> You need to trace specific documents or identify patterns</li>
            </ul>
          </div>

          <p className="guide-recommendation">
            <strong>💡 Recommendation:</strong> Start with Sankey for overview, switch to Parallel Coordinates for deep-dive.
          </p>
        </div>
      </details>
    </div>
  );
}

PipelineFlowPanel.propTypes = {
  analysisData: PropTypes.object.isRequired,
  parallelData: PropTypes.object,
  documents: PropTypes.array,
  width: PropTypes.number
};

export default PipelineFlowPanel;
