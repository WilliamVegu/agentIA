import apiClient from './apiClient';

export interface LocalDeploymentSession {
  sessionId: string;
  serviceName: string;
  status: 'NOT_DEPLOYED' | 'STARTING' | 'BUILDING' | 'RUNNING' | 'HEALTHY' | 'STOPPED' | 'ERROR' | 'FAILED' | 'IDLE' | 'DOCKER_UNAVAILABLE';
  hostPort: number;
  containerId?: string;
  dbEngine: string;
  healthStatus: 'UP' | 'DOWN' | 'UNKNOWN';
  message: string;
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
  sessionId: string;
  serviceName: string;
  dockerfile: string;
  dockerCompose: string;
  k8sDeployment: string;
  k8sService: string;
  githubCiWorkflow: string;
}

export const devopsService = {
  async generateManifests(sessionId: string, dbEngine = 'POSTGRESQL', hostPort = 8080): Promise<ManifestBundle> {
    const response = await apiClient.post<ManifestBundle>(`/devops/${sessionId}/generate`, null, {
      params: { db_engine: dbEngine, host_port: hostPort },
    });
    return response.data;
  },

  async deployLocal(sessionId: string, hostPort = 8080, rebuild = false): Promise<LocalDeploymentSession> {
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

  async runSmokeTest(sessionId: string, hostPort = 8080): Promise<SmokeTestResult> {
    const response = await apiClient.post<SmokeTestResult>(`/devops/${sessionId}/smoke-test`, null, {
      params: { host_port: hostPort },
    });
    return response.data;
  },

  async stopContainers(sessionId: string): Promise<LocalDeploymentSession> {
    const response = await apiClient.post<LocalDeploymentSession>(`/devops/${sessionId}/stop`);
    return response.data;
  },

  async getLogs(sessionId: string): Promise<string[]> {
    const response = await apiClient.get<{ logs: string[] }>(`/devops/${sessionId}/logs`);
    return response.data.logs;
  },
};
