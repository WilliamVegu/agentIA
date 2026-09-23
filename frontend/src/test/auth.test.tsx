import { describe, it, expect, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { LlmProvider } from '../context/LlmContext';
import { ThemeProvider } from '../context/ThemeContext';
import { LoginView } from '../views/LoginView';

const renderLoginView = (extra?: React.ReactNode) => {
  return render(
    <ThemeProvider>
      <AuthProvider>
        <LlmProvider>
          <LoginView />
          {extra}
        </LlmProvider>
      </AuthProvider>
    </ThemeProvider>
  );
};

const TestAuthConsumer: React.FC = () => {
  const { user, isAuthenticated, logout, loginDemo } = useAuth();
  return (
    <div>
      <span data-testid="auth-status">{isAuthenticated ? 'LOGGED_IN' : 'LOGGED_OUT'}</span>
      <span data-testid="user-name">{user?.name || 'NONE'}</span>
      <span data-testid="user-email">{user?.email || 'NONE'}</span>
      <span data-testid="user-role">{user?.role || 'NONE'}</span>
      <button onClick={logout} data-testid="btn-logout">Logout</button>
      <button onClick={loginDemo} data-testid="btn-demo">Demo</button>
    </div>
  );
};

describe('Auth Module & LoginView', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders default demo user in initial state if no localStorage', () => {
    render(
      <AuthProvider>
        <TestAuthConsumer />
      </AuthProvider>
    );

    expect(screen.getByTestId('auth-status')).toHaveTextContent('LOGGED_IN');
    expect(screen.getByTestId('user-name')).toHaveTextContent('Rodrigo Mendoza');
    expect(screen.getByTestId('user-email')).toHaveTextContent('architect@tcs.com');
  });

  it('allows logging out and clearing user from state and localStorage', async () => {
    render(
      <AuthProvider>
        <TestAuthConsumer />
      </AuthProvider>
    );

    fireEvent.click(screen.getByTestId('btn-logout'));

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('LOGGED_OUT');
      expect(screen.getByTestId('user-name')).toHaveTextContent('NONE');
      expect(localStorage.getItem('agentia_user')).toBeNull();
    });
  });

  it('validates non-@tcs.com email and displays error message in LoginView', async () => {
    // Clear initial user first
    localStorage.setItem('agentia_user', 'null');

    renderLoginView();

    // Logout first if already logged in
    const emailInput = screen.getByPlaceholderText('usuario@tcs.com');
    const passwordInput = screen.getByPlaceholderText('••••••••');
    const submitBtn = screen.getByRole('button', { name: /Ingresar al Studio/i });

    fireEvent.change(emailInput, { target: { value: 'invalid@gmail.com' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/Debe ingresar un correo corporativo válido con dominio @tcs.com/i)
      ).toBeInTheDocument();
    });
  });

  it('validates password length (< 4 chars) and displays error', async () => {
    renderLoginView();

    const emailInput = screen.getByPlaceholderText('usuario@tcs.com');
    const passwordInput = screen.getByPlaceholderText('••••••••');
    const submitBtn = screen.getByRole('button', { name: /Ingresar al Studio/i });

    fireEvent.change(emailInput, { target: { value: 'architect@tcs.com' } });
    fireEvent.change(passwordInput, { target: { value: '12' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/La contraseña corporativa debe tener al menos 4 caracteres/i)
      ).toBeInTheDocument();
    });
  });

  it('logs in successfully with valid @tcs.com credentials', async () => {
    let contextUser: any = null;

    const Inspector = () => {
      const { user } = useAuth();
      contextUser = user;
      return null;
    };

    renderLoginView(<Inspector />);

    const emailInput = screen.getByPlaceholderText('usuario@tcs.com');
    const passwordInput = screen.getByPlaceholderText('••••••••');
    const submitBtn = screen.getByRole('button', { name: /Ingresar al Studio/i });

    fireEvent.change(emailInput, { target: { value: 'carlos.sanchez@tcs.com' } });
    fireEvent.change(passwordInput, { target: { value: 'securePass123' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(contextUser).not.toBeNull();
      expect(contextUser.email).toBe('carlos.sanchez@tcs.com');
      expect(contextUser.name).toBe('Carlos Sanchez');
      expect(contextUser.role).toBe('Architect');
    });
  });

  it('handles 1-Click Demo Login button in LoginView', async () => {
    let contextUser: any = null;

    const Inspector = () => {
      const { user } = useAuth();
      contextUser = user;
      return null;
    };

    renderLoginView(<Inspector />);

    const demoBtn = screen.getByRole('button', { name: /Acceso Rápido de Demostración/i });
    fireEvent.click(demoBtn);

    await waitFor(() => {
      expect(contextUser).not.toBeNull();
      expect(contextUser.name).toBe('Rodrigo Mendoza');
      expect(contextUser.email).toBe('architect@tcs.com');
    });
  });
});
