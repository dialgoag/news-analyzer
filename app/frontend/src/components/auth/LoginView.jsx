/**
 * LoginView Component
 * Single Responsibility: Login UI only
 * No business logic - delegates to useAuth hook
 */

import React from 'react';

export function LoginView({ 
  branding, 
  loginForm, 
  setLoginForm, 
  handleLogin, 
  loggingIn, 
  loginError 
}) {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="bg-slate-800 p-8 rounded-2xl shadow-2xl w-full max-w-md border border-slate-700">
        {/* Branding Header */}
        <div className="text-center mb-8">
          {branding.clientLogo ? (
            <img 
              src={branding.clientLogo} 
              alt={branding.clientName} 
              className="mx-auto h-16 mb-4"
            />
          ) : (
            <h1 className="text-3xl font-bold text-white mb-2">
              {branding.clientName}
            </h1>
          )}
          <p className="text-slate-400 text-sm">
            Powered by <span className="text-blue-400 font-semibold">{branding.poweredBy}</span>
          </p>
          <p className="text-slate-500 text-xs">{branding.poweredBySubtitle}</p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Username
            </label>
            <input
              type="text"
              value={loginForm.username}
              onChange={(e) => setLoginForm({ ...loginForm, username: e.target.value })}
              disabled={loggingIn}
              className="w-full px-4 py-3 bg-slate-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              placeholder="Enter your username (min 3 characters)"
              minLength={3}
              maxLength={50}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Password
            </label>
            <input
              type="password"
              value={loginForm.password}
              onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
              disabled={loggingIn}
              className="w-full px-4 py-3 bg-slate-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              placeholder="Enter your password (min 6 characters)"
              minLength={6}
              required
            />
          </div>

          {loginError && (
            <div className="bg-red-900/30 border border-red-700 text-red-300 px-4 py-3 rounded-lg text-sm">
              {loginError}
            </div>
          )}

          <button
            type="submit"
            disabled={loggingIn}
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white rounded-lg font-semibold transition"
          >
            {loggingIn ? '⏳ Logging in...' : '🔐 Login'}
          </button>
        </form>

        {/* Footer */}
        <div className="mt-6 text-center text-slate-500 text-xs">
          {branding.version}
        </div>
      </div>
    </div>
  );
}
