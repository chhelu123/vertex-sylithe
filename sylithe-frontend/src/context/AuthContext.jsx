import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const AuthContext = createContext(null);

function decodeJwt(token) {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch {
    return null;
  }
}

function isTokenExpired(token) {
  const payload = decodeJwt(token);
  if (!payload?.exp) return true;
  return Date.now() >= payload.exp * 1000;
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    const t = localStorage.getItem('sylithe_token');
    if (!t || isTokenExpired(t)) {
      localStorage.removeItem('sylithe_token');
      localStorage.removeItem('sylithe_user');
      return null;
    }
    return t;
  });

  const [user, setUser] = useState(() => {
    const t = localStorage.getItem('sylithe_token');
    if (!t || isTokenExpired(t)) return null;
    try { return JSON.parse(localStorage.getItem('sylithe_user') || 'null'); }
    catch { return null; }
  });

  const logout = useCallback(() => {
    localStorage.removeItem('sylithe_token');
    localStorage.removeItem('sylithe_user');
    setToken(null);
    setUser(null);
  }, []);

  const login = useCallback((newToken, newUser) => {
    localStorage.setItem('sylithe_token', newToken);
    localStorage.setItem('sylithe_user', JSON.stringify(newUser));
    setToken(newToken);
    setUser(newUser);
  }, []);

  // Auto-sync user profile from backend on mount (picks up tier/role changes)
  useEffect(() => {
    if (!token) return;
    const API = import.meta.env.VITE_API_URL || '';
    fetch(`${API}/api/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data) => {
        if (data?.status === 'success' && data.user) {
          const merged = { ...user, ...data.user };
          localStorage.setItem('sylithe_user', JSON.stringify(merged));
          setUser(merged);
        }
      })
      .catch(() => {/* silent – offline or token invalid */});
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-logout when JWT hits expiry
  useEffect(() => {
    if (!token) return;
    const payload = decodeJwt(token);
    if (!payload?.exp) { logout(); return; }
    const msUntilExpiry = payload.exp * 1000 - Date.now();
    if (msUntilExpiry <= 0) { logout(); return; }
    const timer = setTimeout(logout, msUntilExpiry);
    return () => clearTimeout(timer);
  }, [token, logout]);

  return (
    <AuthContext.Provider value={{ token, user, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
