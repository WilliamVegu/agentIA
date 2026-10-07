import { describe, it, expect, vi, beforeEach } from 'vitest';
import apiClient, {
  setEphemeralLlmCredentials,
  getEphemeralLlmCredentials,
} from '../services/apiClient';
import { sessionService } from '../services/sessionService';
import { requirementsService } from '../services/requirementsService';
import { architectureService } from '../services/architectureService';
import { modelsService } from '../services/modelsService';
import { orchestratorService } from '../services/orchestratorService';
import { exportService } from '../services/exportService';
import { securityService } from '../services/securityService';
import { devopsService } from '../services/devopsService';
import { llmService } from '../services/llmService';
import axios from 'axios';

describe('Frontend API Services & Client Interceptors', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('apiClient & Ephemeral Credentials (Principio VI)', () => {
    it('sets and retrieves ephemeral in-memory credentials without touching disk', () => {
      setEphemeralLlmCredentials('test-secret-key-xyz', 'groq');
      const creds = getEphemeralLlmCredentials();

      expect(creds.apiKey).toBe('test-secret-key-xyz');
      expect(creds.provider).toBe('groq');
    });

    it('injects X-LLM-API-Key and X-LLM-Provider into outgoing request headers', async () => {
      setEphemeralLlmCredentials('ephemeral-key-999', 'gemini');

      // Test the interceptor directly
      const requestInterceptor = (apiClient.interceptors.request as any).handlers[0].fulfilled;
      const dummyConfig = { headers: {} } as any;
      const modifiedConfig = requestInterceptor(dummyConfig);

      expect(modifiedConfig.headers['X-LLM-API-Key']).toBe('ephemeral-key-999');
      expect(modifiedConfig.headers['X-LLM-Provider']).toBe('gemini');
    });
  });

  describe('sessionService', () => {
    it('listSessions calls GET /sessions with limit parameter', async () => {
      const spy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ data: [{ sessionId: 'sess-1' }] });
      const res = await sessionService.listSessions(20);

      expect(spy).toHaveBeenCalledWith('/sessions', { params: { limit: 20 } });
      expect(res).toEqual([{ sessionId: 'sess-1' }]);
    });

    it('quickStart calls POST /sessions/quick-start with payload', async () => {
      const spy = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({ data: { sessionId: 'sess-2' } });
      const payload = { service_name: 'order-service', prompt: 'Create order service' };
      const res = await sessionService.quickStart(payload);

      expect(spy).toHaveBeenCalledWith('/sessions/quick-start', payload);
      expect(res).toEqual({ sessionId: 'sess-2' });
    });

    it('cancelSession calls DELETE /sessions/:id', async () => {
      const spy = vi.spyOn(apiClient, 'delete').mockResolvedValueOnce({ data: { status: 'CANCELLED' } });
      await sessionService.cancelSession('sess-3');

      expect(spy).toHaveBeenCalledWith('/sessions/sess-3');
    });
  });

  describe('requirementsService', () => {
    it('transform posts naturalLanguageText to /requirements/transform', async () => {
      const spy = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({ data: { stories: [] } });
      const res = await requirementsService.transform({ naturalLanguageText: 'Manage invoices' });

      expect(spy).toHaveBeenCalledWith('/requirements/transform', {
        rawText: 'Manage invoices',
        serviceName: undefined,
        apiKey: undefined,
        provider: undefined,
      });
      expect(res).toEqual({ stories: [] });
    });

    it('getSessionRequirements calls GET /requirements/sessions/:id', async () => {
      const spy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ data: { specificationDraft: {} } });
      const res = await requirementsService.getSessionRequirements('sess-10');

      expect(spy).toHaveBeenCalledWith('/requirements/sessions/sess-10');
      expect(res).toEqual({ specificationDraft: {} });
    });
  });

  describe('architectureService & modelsService', () => {
    it('architectureService.design calls POST /architecture/design', async () => {
      const spy = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({ data: { mermaidDiagram: 'graph TD' } });
      const res = await architectureService.design({ draft: { name: 'test' } });

      expect(spy).toHaveBeenCalledWith('/architecture/design', { draft: { name: 'test' } });
      expect(res).toEqual({ mermaidDiagram: 'graph TD' });
    });

    it('modelsService.generate calls POST /models/generate', async () => {
      const spy = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({ data: { schemaSql: 'CREATE TABLE...' } });
      const res = await modelsService.generate({ draft: { name: 'test' } });

      expect(spy).toHaveBeenCalledWith('/models/generate', { draft: { name: 'test' } });
      expect(res).toEqual({ schemaSql: 'CREATE TABLE...' });
    });
  });

  describe('orchestratorService', () => {
    it('getOverview calls GET /orchestrator/sessions/:id/overview', async () => {
      const spy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ data: { sessionId: 'sess-1' } });
      const res = await orchestratorService.getOverview('sess-1');

      expect(spy).toHaveBeenCalledWith('/orchestrator/sessions/sess-1/overview');
      expect(res).toEqual({ sessionId: 'sess-1' });
    });

    it('runPipeline posts payload to /orchestrator/pipeline/run', async () => {
      const spy = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({ data: { status: 'STARTED' } });
      const res = await orchestratorService.runPipeline({ session_id: 'sess-1', target_phase: 'VERIFIED' });

      expect(spy).toHaveBeenCalledWith('/orchestrator/pipeline/run', {
        session_id: 'sess-1',
        target_phase: 'VERIFIED',
      });
      expect(res).toEqual({ status: 'STARTED' });
    });

    it('pause, resume, and cancel pipeline endpoints', async () => {
      const spy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { ok: true } });

      await orchestratorService.pausePipeline('s1');
      expect(spy).toHaveBeenCalledWith('/orchestrator/pipeline/s1/pause');

      await orchestratorService.resumePipeline('s1');
      expect(spy).toHaveBeenCalledWith('/orchestrator/pipeline/s1/resume');

      await orchestratorService.cancelPipeline('s1');
      expect(spy).toHaveBeenCalledWith('/orchestrator/pipeline/s1/cancel');
    });
  });

  describe('exportService & securityService', () => {
    it('exportService produces correct zip export url', () => {
      const url = exportService.getDownloadZipUrl('sess-99');
      expect(url).toBe('/api/v1/sessions/sess-99/export');
    });

    it('listArtifacts calls GET /sessions/:id/artifacts', async () => {
      const spy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ data: [{ relativePath: 'pom.xml' }] });
      const res = await exportService.listArtifacts('sess-99');

      expect(spy).toHaveBeenCalledWith('/sessions/sess-99/artifacts');
      expect(res).toEqual([{ relativePath: 'pom.xml' }]);
    });

    it('securityService.getAuditReport calls GET /security/:id/report', async () => {
      const spy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ data: { qualityGate: { verdict: 'PASS' } } });
      const res = await securityService.getAuditReport('sess-99');

      expect(spy).toHaveBeenCalledWith('/security/sess-99/report');
      expect(res.qualityGate.verdict).toBe('PASS');
    });
  });

  describe('devopsService & llmService', () => {
    it('deployLocal calls POST /devops/:id/deploy', async () => {
      const spy = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({ data: { status: 'RUNNING', hostPort: 8080 } });
      const res = await devopsService.deployLocal('sess-100', 8080, false);

      expect(spy).toHaveBeenCalledWith('/devops/sess-100/deploy', {
        hostPort: 8080,
        rebuild: false,
      });
      expect(res.status).toBe('RUNNING');
    });

    it('llmService.checkHealth calls GET /healthz', async () => {
      const spy = vi.spyOn(axios, 'get').mockResolvedValueOnce({ data: { status: 'UP', app: 'AgentIA API' } });
      const res = await llmService.checkHealth();

      expect(spy).toHaveBeenCalledWith('/healthz');
      expect(res.status).toBe('UP');
    });
  });
});

