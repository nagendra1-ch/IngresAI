import React, { createContext, useState, useEffect, useContext } from 'react';
import api from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch current user details if token exists
  useEffect(() => {
    const fetchCurrentUser = async () => {
      const token = localStorage.getItem('ingres_token');
      if (token) {
        try {
          const res = await api.get('/api/auth/me');
          setUser(res.data);
          localStorage.setItem('ingres_user', JSON.stringify(res.data));
        } catch (err) {
          console.error("Failed to load user profile", err);
          localStorage.removeItem('ingres_token');
          localStorage.removeItem('ingres_user');
          setUser(null);
        }
      }
      setLoading(false);
    };

    fetchCurrentUser();
  }, []);

  const login = async (email, password) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.post('/api/auth/login', { email, password });
      const { access_token } = res.data;
      localStorage.setItem('ingres_token', access_token);
      
      // Load user profile
      const userRes = await api.get('/api/auth/me');
      setUser(userRes.data);
      localStorage.setItem('ingres_user', JSON.stringify(userRes.data));
      setLoading(false);
      return userRes.data;
    } catch (err) {
      setLoading(false);
      const msg = err.response?.data?.detail || "Invalid email or password.";
      setError(msg);
      throw new Error(msg);
    }
  };

  const register = async (name, email, password, confirm_password) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.post('/api/auth/register', {
        name,
        email,
        password,
        confirm_password,
      });
      setLoading(false);
      return res.data;
    } catch (err) {
      setLoading(false);
      const msg = err.response?.data?.detail || "Registration failed. Try again.";
      setError(msg);
      throw new Error(msg);
    }
  };

  const logout = async () => {
    try {
      await api.post('/api/auth/logout');
    } catch (err) {
      console.warn("Logout request failed, cleaning local session anyway", err);
    } finally {
      localStorage.removeItem('ingres_token');
      localStorage.removeItem('ingres_user');
      setUser(null);
    }
  };

  const value = {
    user,
    loading,
    error,
    login,
    register,
    logout,
    isAdmin: user?.role === 'ADMIN',
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
