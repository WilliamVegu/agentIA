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

export interface PlaygroundProxyResult {
  statusCode: number | null;
  url: string;
  latencyMs: number | null;
  contentType?: string;
  truncated?: boolean;
  body?: unknown;
  bodyText?: string | null;
  /** Populated only when the call did NOT complete. `statusCode` is null in that case. */
  error: string | null;
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

  /**
   * Forward one playground call through the platform.
   *
   * The browser cannot call the container directly: the generated service ships no
   * CORS configuration, so every cross-origin call is rejected (403 on preflight) and
   * surfaces as "Failed to fetch" while Docker is healthy. The platform proxies it
   * server-side, which also lets it refuse dangerous paths and derive the endpoint
   * from the service's own controllers.
   */
  async proxyPlayground(
    sessionId: string,
    payload: { method: string; path: string; body?: unknown },
  ): Promise<PlaygroundProxyResult> {
    const response = await apiClient.post<PlaygroundProxyResult>(
      `/devops/${sessionId}/playground`,
      payload,
    );
    return response.data;
  },

  /** The REST paths the generated service exposes, read from its controllers. */
  async getPlaygroundResources(sessionId: string): Promise<{
    sessionId: string;
    resources: string[];
    defaultResource: string | null;
  }> {
    const response = await apiClient.get(`/devops/${sessionId}/playground/resources`);
    return response.data;
  },

  async getLogs(sessionId: string): Promise<string[]> {
    const response = await apiClient.get<{ logs: string[] }>(`/devops/${sessionId}/logs`);
    return response.data.logs;
  },
};
