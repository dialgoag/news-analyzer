/**
 * useAuth Hook
 * Manages authentication state and operations
 * Single Responsibility: Authentication logic only
 */

import { useState, useEffect } from 'react';
import axios from 'axios';

export function useAuth(API_URL) {
  // Auth state
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loginForm, setLoginForm] = useState({ username: '', password: '' });
  const [loggingIn, setLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState('');

  // Check existing token on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('rag_auth_token');
    const storedUser = localStorage.getItem('rag_auth_user');

    if (storedToken && storedUser) {
      setToken(storedToken);
      setUser(JSON.parse(storedUser));
      setIsAuthenticated(true);
    }
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoggingIn(true);
    setLoginError('');

    try {
      const response = await axios.post(`${API_URL}/api/auth/login`, {
        username: loginForm.username,
        password: loginForm.password
      });

      const { access_token, user: userData } = response.data;

      setToken(access_token);
      setUser(userData);
      setIsAuthenticated(true);

      // Save to localStorage (same keys as original)
      localStorage.setItem('rag_auth_token', access_token);
      localStorage.setItem('rag_auth_user', JSON.stringify(userData));

      console.log('✅ Login successful:', userData.username, 'role:', userData.role);
    } catch (err) {
      console.error('Login error:', err);
      const detail = err.response?.data?.detail;
      const msg = Array.isArray(detail)
        ? detail.map(d => d.msg || JSON.stringify(d)).join('. ')
        : (typeof detail === 'string' ? detail : 'Login error');
      setLoginError(msg);
    } finally {
      setLoggingIn(false);
    }
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setUser(null);
    setToken(null);
    setLoginForm({ username: '', password: '' });
    localStorage.removeItem('rag_auth_token');
    localStorage.removeItem('rag_auth_user');
  };

  return {
    isAuthenticated,
    user,
    token,
    loginForm,
    setLoginForm,
    loggingIn,
    loginError,
    handleLogin,
    handleLogout
  };
}
