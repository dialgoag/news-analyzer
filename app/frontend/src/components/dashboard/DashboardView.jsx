/**
 * DashboardView Component
 * Single Responsibility: Dashboard orchestration
 * Coordinates PipelineDashboard with its data fetching
 */

import React, { useState, useEffect } from 'react';
import PipelineDashboard from '../PipelineDashboard';

export function DashboardView({ API_URL, token, isAdmin = false }) {
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Auto-refresh every 30 seconds (managed by parent for global coordination)
  useEffect(() => {
    const interval = setInterval(() => {
      setRefreshTrigger(prev => prev + 1);
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  return (
    <main className="flex-1 flex flex-col overflow-hidden min-h-0">
      {/* Dashboard Content - Full viewport */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden min-h-0">
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
