import React, { createContext, useContext, useState, useEffect } from 'react';
import { User } from '../types';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  login: (email: string, password?: string) => Promise<{ success: boolean; error?: string }>;
  loginDemo: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const DEMO_USER: User = {
  email: 'architect@tcs.com',
  name: 'Rodrigo Mendoza',
  role: 'Architect',
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('agentia_user');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        return null;
      }
    }
    // Default to demo user for seamless onboarding
    return DEMO_USER;
  });

  useEffect(() => {
    if (user) {
      localStorage.setItem('agentia_user', JSON.stringify(user));
    } else {
      localStorage.removeItem('agentia_user');
    }
  }, [user]);

  const login = async (email: string, password?: string): Promise<{ success: boolean; error?: string }> => {
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail.endsWith('@tcs.com')) {
      return {
        success: false,
        error: 'Debe ingresar un correo corporativo válido con dominio @tcs.com',
      };
    }
    if (!password || password.length < 4) {
      return {
        success: false,
        error: 'La contraseña corporativa debe tener al menos 4 caracteres',
      };
    }

    const namePart = cleanEmail.split('@')[0].replace('.', ' ');
    const formattedName = namePart
      .split(' ')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');

    const loggedUser: User = {
      email: cleanEmail,
      name: formattedName || 'Consultor TCS',
      role: cleanEmail.includes('admin') ? 'Lead' : 'Architect',
    };

    setUser(loggedUser);
    return { success: true };
  };

  const loginDemo = () => {
    setUser(DEMO_USER);
  };

  const logout = () => {
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        login,
        loginDemo,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
