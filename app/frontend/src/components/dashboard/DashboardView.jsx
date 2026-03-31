/**
 * DashboardView Component
 * Single Responsibility: Dashboard orchestration
 * Coordinates PipelineDashboard with its data fetching
 */

import React, { useState, useEffect } from 'react';
import { PipelineDashboard } from '../PipelineDashboard';

export function DashboardView({ API_URL, token, isAdmin = false }) {
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setRefreshTrigger(prev => prev + 1);
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  const handleManualRefresh = () => {
    setRefreshTrigger(prev => prev + 1);
  };

  return (
    <main className="flex-1 flex flex-col overflow-hidden min-h-0">
      {/* Single compact toolbar — detail lives inside panels */}
      <div className="px-4 py-2 border-b border-slate-700 flex items-center justify-between gap-3 bg-slate-800/50 shrink-0">
        <div className="flex items-baseline gap-2 min-w-0">
          <h1 className="text-base font-semibold text-white truncate">Pipeline</h1>
          <span className="text-xs text-slate-500 whitespace-nowrap hidden sm:inline">
            datos ~20s · panel 30s
          </span>
        </div>
        <button
          onClick={handleManualRefresh}
          className="shrink-0 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-xs font-semibold transition flex items-center gap-1.5"
          title="Refrescar ahora"
        >
          🔄 Refrescar
        </button>
      </div>

      {/* Full Width Pipeline Dashboard */}
      <div className="flex-1 overflow-hidden min-h-0">
        <PipelineDashboard 
          API_URL={API_URL} 
          token={token} 
          isAdmin={isAdmin}
          refreshTrigger={refreshTrigger} 
        />
      </div>
    </main>
  );
}
