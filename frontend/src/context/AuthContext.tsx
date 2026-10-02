import React, { createContext, useContext, useState, useEffect } from 'react';
import { User } from '../types';
import apiClient from '../services/apiClient';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isAutomaticAccess: boolean;
  enterMvp: () => Promise<{ success: boolean; error?: string }>;
  login: (email: string, password?: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
}
const AuthContext = createContext<AuthContextType | undefined>(undefined);
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  useEffect(() => {
    localStorage.removeItem('agentia_user');
    apiClient.get<User>('/auth/session').then(({ data }) => setUser(data)).catch(() => setUser(null)).finally(() => setIsLoading(false));
  }, []);
  const login = async (email: string, password?: string) => {
    try {
      const { data } = await apiClient.post<User>('/auth/login', { email, password });
      setUser(data);
      return { success: true };
    } catch (err: any) {
      return { success: false, error: err.response?.data?.detail || 'No se pudo iniciar sesión' };
    }
  };
  const logout = () => {
    apiClient.post('/auth/logout').then(() => { window.dispatchEvent(new Event('agentia:logout')); setUser(null); }).catch(() => {
      // Keep the session visible if server revocation failed; allow retry.
      window.alert('No se pudo cerrar la sesión. Intente nuevamente.');
    });
  };
  const enterMvp = async () => {
    try {
      const { data } = await apiClient.post<User>('/auth/mvp');
      setUser(data);
      return { success: true };
    } catch (err: any) {
      return { success: false, error: err.response?.data?.detail || 'No se pudo entrar al MVP' };
    }
  };
  return <AuthContext.Provider value={{ user, isAuthenticated: !!user, isLoading, isAutomaticAccess: user?.accessMode === 'mvp', login, enterMvp, logout }}>{children}</AuthContext.Provider>;
};
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};
