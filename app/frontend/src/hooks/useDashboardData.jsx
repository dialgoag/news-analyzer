/**
 * useDashboardData Hook
 * 
 * Centralized data fetching for the entire dashboard
 * Returns memoized, transformed data ready for visualization
 * 
 * Pattern: Single source of truth for all dashboard data
 * Benefits:
 * - Cleaner components (no API logic)
 * - Easier caching
 * - Consistent error handling
 * - Unified loading states
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { API_TIMEOUT_MS } from '../config/apiConfig';
import { transformDocumentsForVisualization } from '../services/documentDataService';
import { getWorkerCapacityByType } from '../services/workerDataService';
import { groupErrorsByType, sortErrorsByPriority } from '../services/errorDataService';

/**
 * Main hook for dashboard data
 * 
 * @param {string} API_URL - Base API URL
 * @param {string} token - JWT token
 * @param {number} refreshInterval - Auto-refresh interval in ms (0 = disabled)
 * @param {number} refreshTrigger - External trigger for manual refresh
 * @returns {Object} - {data, loading, error, refetch}
 */
export function useDashboardData(API_URL, token, refreshInterval = 20000, refreshTrigger = 0) {
  // Raw data from API
  const [rawData, setRawData] = useState({
    summary: null,
    analysis: null,
    documents: null,
    workers: null,
    parallelData: null
  });
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  /**
   * Fetch all dashboard data in parallel
   */
  const fetchData = useCallback(async () => {
    if (!token) {
      setError('No authentication token');
      setLoading(false);
      return;
    }

    try {
      setRefreshing(true);
      setError(null);

      // Fetch all endpoints in parallel
      const [summaryRes, analysisRes, docsRes, workersRes, parallelRes] = await Promise.allSettled([
        axios.get(`${API_URL}/api/dashboard/summary`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_MS
        }),
        axios.get(`${API_URL}/api/dashboard/analysis`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_MS
        }),
        axios.get(`${API_URL}/api/documents`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_MS
        }),
        axios.get(`${API_URL}/api/workers/status`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_MS
        }),
        axios.get(`${API_URL}/api/dashboard/parallel-data`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_MS
        })
      ]);

      // Process results (keep previous data on failure for resilience)
      setRawData(prev => ({
        summary: summaryRes.status === 'fulfilled' ? summaryRes.value.data : prev.summary,
        analysis: analysisRes.status === 'fulfilled' ? analysisRes.value.data : prev.analysis,
        documents: docsRes.status === 'fulfilled' ? docsRes.value.data?.documents : prev.documents,
        workers: workersRes.status === 'fulfilled' ? workersRes.value.data : prev.workers,
        parallelData: parallelRes.status === 'fulfilled' ? parallelRes.value.data : prev.parallelData
      }));

      // Log warnings for failed requests (but don't throw)
      if (summaryRes.status === 'rejected') console.warn('Summary fetch failed:', summaryRes.reason);
      if (analysisRes.status === 'rejected') console.warn('Analysis fetch failed:', analysisRes.reason);
      if (docsRes.status === 'rejected') console.warn('Documents fetch failed:', docsRes.reason);
      if (workersRes.status === 'rejected') console.warn('Workers fetch failed:', workersRes.reason);
      if (parallelRes.status === 'rejected') console.warn('Parallel data fetch failed:', parallelRes.reason);

      setLoading(false);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
      setError(err.message || 'Connection error');
      setLoading(false);
    } finally {
      setRefreshing(false);
    }
  }, [API_URL, token]);

  /**
   * Manual refetch
   */
  const refetch = useCallback(async () => {
    setRefreshing(true);
    await fetchData();
  }, [fetchData]);

  /**
   * Auto-refresh effect
   */
  useEffect(() => {
    fetchData();
    
    if (refreshInterval > 0) {
      const interval = setInterval(fetchData, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchData, refreshInterval, refreshTrigger]);

  /**
   * Memoized transformed data
   * This is where we apply all data services
   */
  const transformedData = useMemo(() => {
    // If still loading initial data, return null
    if (loading && !rawData.summary) {
      return null;
    }

    // Transform documents
    const documents = transformDocumentsForVisualization(rawData.documents || []);

    // Transform workers
    const workerCapacity = rawData.workers?.workers && rawData.workers?.summary?.limits
      ? getWorkerCapacityByType(rawData.workers.workers, rawData.workers.summary.limits)
      : {};

    // Transform errors
    const errorGroups = rawData.analysis?.errors?.groups
      ? sortErrorsByPriority(groupErrorsByType(rawData.analysis.errors.groups))
      : [];

    // Extract KPI metrics
    const kpis = {
      documents: {
        current: rawData.summary?.files?.total || 0,
        completed: rawData.summary?.files?.completed || 0,
        errors: rawData.summary?.files?.errors || 0,
        percentDone: rawData.summary?.files?.percentage_done || 0
      },
      news: {
        current: rawData.summary?.news_items?.total || 0,
        done: rawData.summary?.news_items?.done || 0,
        errors: rawData.summary?.news_items?.errors || 0,
        percentDone: rawData.summary?.news_items?.percentage_done || 0
      },
      insights: {
        current: rawData.summary?.insights?.total || 0,
        done: rawData.summary?.insights?.done || 0,
        errors: rawData.summary?.insights?.errors || 0,
        percentDone: rawData.summary?.insights?.percentage_done || 0
      },
      errors: {
        current: errorGroups.filter(g => g.is_real_error !== false).length,
        retriable: errorGroups.filter(g => g.canRetry).length,
        critical: errorGroups.filter(g => g.severity === 'critical').length
      }
    };

    // Pipeline stages (for Sankey)
    const pipeline = rawData.analysis?.pipeline || null;

    // Workers summary
    const workers = {
      capacity: workerCapacity,
      active: rawData.workers?.summary?.active || 0,
      idle: rawData.workers?.summary?.idle || 0,
      total: rawData.workers?.summary?.total || 0,
      limits: rawData.workers?.summary?.limits || {}
    };

    return {
      // Raw data (if needed)
      raw: rawData,
      
      // Transformed data ready for components
      documents,
      kpis,
      pipeline,
      workers,
      errors: {
        groups: errorGroups,
        realErrors: errorGroups.filter(g => g.is_real_error !== false),
        count: errorGroups.length
      },
      parallelData: rawData.parallelData
    };
  }, [rawData, loading]);

  return {
    data: transformedData,
    loading,
    error,
    refreshing,
    refetch
  };
}

export default useDashboardData;
