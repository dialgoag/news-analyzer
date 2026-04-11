/**
 * App.jsx - Simplified Main Application
 * Single Responsibility: Routing + Authentication gate
 * Business logic delegated to hooks and view components
 */

import React, { useState } from 'react';
import { useAuth } from './hooks/useAuth';
import { LoginView } from './components/auth/LoginView';
import { DashboardView } from './components/dashboard/DashboardView';
import './App.css';

// Branding configuration (customizable for each client)
const BRANDING = {
  clientLogo: '/logo.png',
  clientName: 'RAG Enterprise',
  primaryColor: '#3b82f6',
  poweredBy: 'DialogAI',
  poweredBySubtitle: 'based on RAG Architecture',
  version: 'v1.1'
};

// API Configuration
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App() {
  // Auth state (delegated to hook)
  const {
    isAuthenticated,
    user,
    token,
    loginForm,
    setLoginForm,
    loggingIn,
    loginError,
    handleLogin,
    handleLogout
  } = useAuth(API_URL);

  // View state (simple routing)
  const [currentView, setCurrentView] = useState('dashboard'); // 'dashboard' | 'query' | 'documents'

  // Not authenticated -> Login screen
  if (!isAuthenticated) {
    return (
      <LoginView
        branding={BRANDING}
        loginForm={loginForm}
        setLoginForm={setLoginForm}
        handleLogin={handleLogin}
        loggingIn={loggingIn}
        loginError={loginError}
      />
    );
  }

  // Authenticated -> Main app with navigation
  return (
    <div className="flex flex-col h-screen bg-slate-900 text-white" data-section="app-shell">
      {/* Top Navigation Bar */}
      <nav
        className="bg-slate-800 border-b border-slate-700 px-6 py-3"
        data-section="app-primary-nav"
      >
        <div className="flex items-center justify-between">
          {/* Left: Logo + Navigation */}
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3">
              {BRANDING.clientLogo && (
                <img src={BRANDING.clientLogo} alt={BRANDING.clientName} className="h-8" />
              )}
              <h1 className="text-xl font-bold">{BRANDING.clientName}</h1>
            </div>

            {/* Navigation Tabs */}
            <div className="flex gap-2">
              <button
                onClick={() => setCurrentView('dashboard')}
                className={`px-4 py-2 rounded-lg font-semibold transition ${
                  currentView === 'dashboard'
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-300 hover:bg-slate-700'
                }`}
              >
                📊 Dashboard
              </button>
              <button
                onClick={() => setCurrentView('query')}
                className={`px-4 py-2 rounded-lg font-semibold transition ${
                  currentView === 'query'
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-300 hover:bg-slate-700'
                }`}
              >
                🔍 Query
              </button>
              <button
                onClick={() => setCurrentView('documents')}
                className={`px-4 py-2 rounded-lg font-semibold transition ${
                  currentView === 'documents'
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-300 hover:bg-slate-700'
                }`}
              >
                📁 Documents
              </button>
            </div>
          </div>

          {/* Right: User menu */}
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-400">
              👤 {user?.username || 'User'} 
              {user?.role === 'admin' && <span className="ml-2 px-2 py-1 bg-purple-900/30 text-purple-300 rounded text-xs">Admin</span>}
            </span>
            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-semibold transition"
            >
              🚪 Logout
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content Area (View-based routing) */}
      {currentView === 'dashboard' && (
        <DashboardView API_URL={API_URL} token={token} isAdmin={user?.role === 'admin'} />
      )}

      {currentView === 'query' && (
        <div className="flex-1 flex items-center justify-center text-slate-400">
          <div className="text-center">
            <div className="text-6xl mb-4">🔍</div>
            <h2 className="text-2xl font-bold mb-2">Query View</h2>
            <p>To be implemented (extract from old App.jsx)</p>
          </div>
        </div>
      )}

      {currentView === 'documents' && (
        <div className="flex-1 flex items-center justify-center text-slate-400">
          <div className="text-center">
            <div className="text-6xl mb-4">📁</div>
            <h2 className="text-2xl font-bold mb-2">Documents View</h2>
            <p>To be implemented (extract from old App.jsx)</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
