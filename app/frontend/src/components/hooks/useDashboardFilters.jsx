/**
 * useDashboardFilters Hook
 * 
 * Coordinated filters for dashboard visualizations (Brushing & Linking pattern).
 * All visualizations share the same filter state, so clicking/selecting in one
 * automatically filters the others.
 */

import { createContext, useContext, useState, useCallback } from 'react';

const DashboardContext = createContext();

export const DashboardProvider = ({ children }) => {
  const [filters, setFilters] = useState({
    stage: null,       // 'upload', 'ocr', 'chunking', 'indexing', 'insights', 'completed'
    timeRange: null,   // [Date, Date]
    status: null,      // 'active', 'idle', 'error', 'completed'
    keyword: null,     // string (for insights dashboard)
    workerId: null,    // string
    documentId: null   // string
  });

  const updateFilter = useCallback((key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  }, []);

  const clearFilter = useCallback((key) => {
    setFilters(prev => ({ ...prev, [key]: null }));
  }, []);

  const clearAllFilters = useCallback(() => {
    setFilters({
      stage: null,
      timeRange: null,
      status: null,
      keyword: null,
      workerId: null,
      documentId: null
    });
  }, []);

  const hasActiveFilters = useCallback(() => {
    return Object.values(filters).some(value => value !== null);
  }, [filters]);

  return (
    <DashboardContext.Provider 
      value={{ 
        filters, 
        updateFilter, 
        clearFilter, 
        clearAllFilters,
        hasActiveFilters
      }}
    >
      {children}
    </DashboardContext.Provider>
  );
};

export const useDashboardFilters = () => {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error('useDashboardFilters must be used within DashboardProvider');
  }
  return context;
};
