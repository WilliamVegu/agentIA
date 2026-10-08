import apiClient from './apiClient';

export interface LocalDeploymentSession {
  sessionId: string;
  serviceName?: string;
  status: 'NOT_DEPLOYED' | 'STARTING' | 'BUILDING' | 'RUNNING' | 'HEALTHY' | 'STOPPED' | 'ERROR' | 'FAILED' | 'IDLE' | 'DOCKER_UNAVAILABLE' | 'UNKNOWN';
  hostPort?: number | null;
  containerId?: string;
  errorMessage?: string;
  dbEngine?: string;
  healthStatus?: 'UP' | 'DOWN' | 'UNKNOWN';
  message?: string;
  startedAt?: string;
}

export interface SmokeTestResult {
  sessionId: string;
  endpointTested: string;
  status: 'SUCCESS' | 'FAILURE' | 'SKIPPED';
  httpStatusCode?: number;
  latencyMs?: number;
  details?: Record<string, any>;
  message: string;
}

export interface ManifestBundle {
  sessionId?: string;
  serviceName?: string;
  databaseEngine?: string;
  dockerfileContent: string;
  dockerignoreContent: string;
  dockerComposeContent: string;
  githubActionsWorkflow: string;
  gitlabCiWorkflow: string;
  kubernetesManifests: Record<string,string>;
}

export const devopsService = {
  async getConfiguration(sessionId: string): Promise<{databaseEngine?: string; hostPort?: number}> {
    return (await apiClient.get('/devops/' + sessionId + '/configuration')).data;
  },
  async getManifests(sessionId: string): Promise<ManifestBundle> {
    return (await apiClient.get('/devops/' + sessionId + '/manifests')).data;
  },
  async proxyRequest(sessionId: string, method: string, path: string, body?: unknown): Promise<{statusCode: number | null; latencyMs: number | null; body: unknown; error?: string}> {
    return (await apiClient.post('/devops/' + sessionId + '/playground', {method,path,body})).data;
  },
  async generateManifests(sessionId: string, dbEngine?: string, hostPort?: number): Promise<ManifestBundle> {
    const response = await apiClient.post<ManifestBundle>(`/devops/${sessionId}/generate`, null, {
      params: { db_engine: dbEngine, host_port: hostPort },
    });
    return response.data;
  },

  async deployLocal(sessionId: string, hostPort?: number, rebuild = false): Promise<LocalDeploymentSession> {
    const response = await apiClient.post<LocalDeploymentSession>(`/devops/${sessionId}/deploy`, {
      hostPort,
      rebuild,
    });
    return response.data;
  },

  async getDeploymentStatus(sessionId: string): Promise<LocalDeploymentSession> {
    const response = await apiClient.get<LocalDeploymentSession>(`/devops/${sessionId}/status`);
    return response.data;
  },

  async runSmokeTest(sessionId: string, hostPort?: number): Promise<SmokeTestResult> {
    const response = await apiClient.post<SmokeTestResult>(`/devops/${sessionId}/smoke-test`, null, {
      params: { host_port: hostPort },
    });
    const native = response.data as any;
    return { sessionId, endpointTested: native.testUrl || '', status: native.passed ? 'SUCCESS' : 'FAILURE',
      httpStatusCode: native.statusCode, latencyMs: native.latencyMs, message: native.details || 'Salud no confirmada' };
  },

  async stopContainers(sessionId: string): Promise<LocalDeploymentSession> {
    const response = await apiClient.post<LocalDeploymentSession>(`/devops/${sessionId}/stop`);
    return response.data;
  },

  async cleanupPreview(sessionId: string): Promise<{ resources: Record<string, string[]>; confirmationToken: string }> {
    return (await apiClient.get('/devops/' + sessionId + '/cleanup/preview')).data;
  },

  async cleanupLocal(sessionId: string, deleteData: boolean, confirmationToken: string): Promise<LocalDeploymentSession> {
    return (await apiClient.post<LocalDeploymentSession>('/devops/' + sessionId + '/cleanup', { deleteData, confirmationToken })).data;
  },

  async getLogs(sessionId: string): Promise<string[]> {
    const response = await apiClient.get<{ logs: string[] }>(`/devops/${sessionId}/logs`);
    return response.data.logs;
  },
};
