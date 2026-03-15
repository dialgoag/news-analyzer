/**
 * DashboardView Component
 * Single Responsibility: Dashboard orchestration
 * Coordinates PipelineDashboard with its data fetching
 */

import React, { useState, useEffect } from 'react';
import { PipelineDashboard } from '../PipelineDashboard';

export function DashboardView({ API_URL, token }) {
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
    <main className="flex-1 flex flex-col overflow-hidden">
      {/* Dashboard Header with manual refresh */}
      <div className="px-6 py-3 border-b border-slate-700 flex items-center justify-between bg-slate-800/50">
        <div>
          <h1 className="text-xl font-bold text-white">📊 Pipeline Dashboard</h1>
          <p className="text-sm text-slate-400">Real-time monitoring • Auto-refresh every 30s</p>
        </div>
        <button
          onClick={handleManualRefresh}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition flex items-center gap-2"
          title="Manual refresh"
        >
          🔄 Refresh
        </button>
      </div>

      {/* Full Width Pipeline Dashboard */}
      <div className="flex-1 overflow-hidden">
        <PipelineDashboard 
          API_URL={API_URL} 
          token={token} 
          refreshTrigger={refreshTrigger} 
        />
      </div>
    </main>
  );
}
