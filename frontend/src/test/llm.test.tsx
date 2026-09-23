import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LlmProvider, useLlm } from '../context/LlmContext';
import { SettingsDrawer } from '../components/layout/SettingsDrawer';
import { llmService } from '../services/llmService';

vi.mock('../services/llmService', () => ({
  llmService: {
    verifyConnection: vi.fn(),
  },
}));

const TestLlmConsumer: React.FC = () => {
  const { provider, model, apiKey, isVerified, setProvider, setApiKey, setModel } = useLlm();
  return (
    <div>
      <span data-testid="provider">{provider}</span>
      <span data-testid="model">{model}</span>
      <span data-testid="apiKey">{apiKey}</span>
      <span data-testid="isVerified">{isVerified ? 'VERIFIED' : 'UNVERIFIED'}</span>
      <button data-testid="btn-gemini" onClick={() => setProvider('gemini')}>Gemini</button>
      <button data-testid="btn-groq" onClick={() => setProvider('groq')}>Groq</button>
      <button data-testid="btn-mock" onClick={() => setProvider('mock')}>Mock</button>
      <button data-testid="btn-key" onClick={() => setApiKey('test-key-123')}>Set Key</button>
      <button data-testid="btn-model" onClick={() => setModel('custom-model')}>Set Model</button>
    </div>
  );
};

describe('LlmContext & SettingsDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initializes with mock provider in verified offline state', () => {
    render(
      <LlmProvider>
        <TestLlmConsumer />
      </LlmProvider>
    );

    expect(screen.getByTestId('provider')).toHaveTextContent('mock');
    expect(screen.getByTestId('model')).toHaveTextContent('offline-mock');
    expect(screen.getByTestId('isVerified')).toHaveTextContent('VERIFIED');
  });

  it('updates provider and resets verification state for external providers', () => {
    render(
      <LlmProvider>
        <TestLlmConsumer />
      </LlmProvider>
    );

    fireEvent.click(screen.getByTestId('btn-gemini'));
    expect(screen.getByTestId('provider')).toHaveTextContent('gemini');
    expect(screen.getByTestId('model')).toHaveTextContent('gemini-3.6-flash');
    expect(screen.getByTestId('isVerified')).toHaveTextContent('UNVERIFIED');

    fireEvent.click(screen.getByTestId('btn-groq'));
    expect(screen.getByTestId('provider')).toHaveTextContent('groq');
    expect(screen.getByTestId('model')).toHaveTextContent('qwen/qwen3.8-27b');
    expect(screen.getByTestId('isVerified')).toHaveTextContent('UNVERIFIED');

    fireEvent.click(screen.getByTestId('btn-mock'));
    expect(screen.getByTestId('provider')).toHaveTextContent('mock');
    expect(screen.getByTestId('isVerified')).toHaveTextContent('VERIFIED');
  });

  it('updates apiKey and model properly', () => {
    render(
      <LlmProvider>
        <TestLlmConsumer />
      </LlmProvider>
    );

    fireEvent.click(screen.getByTestId('btn-key'));
    expect(screen.getByTestId('apiKey')).toHaveTextContent('test-key-123');
    expect(screen.getByTestId('isVerified')).toHaveTextContent('UNVERIFIED');

    fireEvent.click(screen.getByTestId('btn-model'));
    expect(screen.getByTestId('model')).toHaveTextContent('custom-model');
  });

  it('renders SettingsDrawer and executes verify connection flow', async () => {
    vi.mocked(llmService.verifyConnection).mockResolvedValueOnce({
      provider: 'gemini',
      model: 'gemini-3.6-flash',
      status: 'CONNECTED',
      message: 'Conexión exitosa con Google Gemini',
      latencyMs: 120,
    });

    render(
      <LlmProvider>
        <SettingsDrawer isOpen={true} onClose={() => {}} />
      </LlmProvider>
    );

    expect(screen.getByText('Configuración del Motor LLM')).toBeInTheDocument();
    expect(screen.getByText(/Seguridad Empresarial TCS/i)).toBeInTheDocument();

    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: 'gemini' } });

    const keyInput = screen.getByPlaceholderText(/AQ\.\.\. o AIzaSy\.\.\./i);
    fireEvent.change(keyInput, { target: { value: 'AIzaSyFakeKey123' } });

    const verifyBtn = screen.getByRole('button', { name: /Guardar y Probar Conexión/i });
    fireEvent.click(verifyBtn);

    await waitFor(() => {
      expect(llmService.verifyConnection).toHaveBeenCalledWith({
        apiKey: 'AIzaSyFakeKey123',
        provider: 'gemini',
        model: 'gemini-3.6-flash',
      });
    });
  });
});
