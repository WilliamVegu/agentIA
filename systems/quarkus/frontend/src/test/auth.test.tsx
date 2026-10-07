import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { AuthProvider, useAuth } from '../context/AuthContext';
const Consumer = () => {
  const { isAuthenticated } = useAuth();
  return <span data-testid="auth-status">{isAuthenticated ? 'LOGGED_IN' : 'LOGGED_OUT'}</span>;
};
describe('Server authentication', () => {
  it('does not grant access from a fabricated localStorage user', () => {
    localStorage.setItem('agentia_user', JSON.stringify({ email: 'architect@tcs.com', role: 'Lead' }));
    render(<AuthProvider><Consumer /></AuthProvider>);
    expect(screen.getByTestId('auth-status')).toHaveTextContent('LOGGED_OUT');
    expect(localStorage.getItem('agentia_user')).toBeNull();
  });
});
