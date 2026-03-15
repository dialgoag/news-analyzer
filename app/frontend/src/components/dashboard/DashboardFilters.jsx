/**
 * DashboardFilters Component
 * 
 * Global filter controls that affect all coordinated visualizations.
 * Shows active filters with clear buttons.
 */

import React from 'react';
import { useDashboardFilters } from '../hooks/useDashboardFilters.jsx';
import './DashboardFilters.css';

export function DashboardFilters() {
  const { filters, clearFilter, clearAllFilters, hasActiveFilters } = useDashboardFilters();

  const formatTimeRange = (timeRange) => {
    if (!timeRange) return '';
    const [start, end] = timeRange;
    const startStr = start.toLocaleDateString();
    const endStr = end.toLocaleDateString();
    return `${startStr} - ${endStr}`;
  };

  const activeFiltersCount = Object.values(filters).filter(v => v !== null).length;

  return (
    <div className="dashboard-filters">
      <div className="filters-header">
        <h3>🔍 Filtros Activos</h3>
        {hasActiveFilters() && (
          <button 
            className="clear-all-btn"
            onClick={clearAllFilters}
            title="Limpiar todos los filtros"
          >
            ✖ Limpiar todo ({activeFiltersCount})
          </button>
        )}
      </div>

      <div className="filters-content">
        {!hasActiveFilters() && (
          <p className="no-filters">Sin filtros activos. Click en cualquier visualización para filtrar.</p>
        )}

        {filters.stage && (
          <div className="filter-chip">
            <span className="filter-label">Stage:</span>
            <span className="filter-value">{filters.stage}</span>
            <button 
              className="filter-clear"
              onClick={() => clearFilter('stage')}
              aria-label="Clear stage filter"
            >
              ✖
            </button>
          </div>
        )}

        {filters.timeRange && (
          <div className="filter-chip">
            <span className="filter-label">Período:</span>
            <span className="filter-value">{formatTimeRange(filters.timeRange)}</span>
            <button 
              className="filter-clear"
              onClick={() => clearFilter('timeRange')}
              aria-label="Clear time range filter"
            >
              ✖
            </button>
          </div>
        )}

        {filters.status && (
          <div className="filter-chip">
            <span className="filter-label">Estado:</span>
            <span className="filter-value">{filters.status}</span>
            <button 
              className="filter-clear"
              onClick={() => clearFilter('status')}
              aria-label="Clear status filter"
            >
              ✖
            </button>
          </div>
        )}

        {filters.workerId && (
          <div className="filter-chip">
            <span className="filter-label">Worker:</span>
            <span className="filter-value">{filters.workerId}</span>
            <button 
              className="filter-clear"
              onClick={() => clearFilter('workerId')}
              aria-label="Clear worker filter"
            >
              ✖
            </button>
          </div>
        )}

        {filters.keyword && (
          <div className="filter-chip">
            <span className="filter-label">Palabra clave:</span>
            <span className="filter-value">{filters.keyword}</span>
            <button 
              className="filter-clear"
              onClick={() => clearFilter('keyword')}
              aria-label="Clear keyword filter"
            >
              ✖
            </button>
          </div>
        )}

        {filters.documentId && (
          <div className="filter-chip">
            <span className="filter-label">Documento:</span>
            <span className="filter-value">{filters.documentId.substring(0, 8)}...</span>
            <button 
              className="filter-clear"
              onClick={() => clearFilter('documentId')}
              aria-label="Clear document filter"
            >
              ✖
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default DashboardFilters;
