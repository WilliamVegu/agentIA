import apiClient from './apiClient';

export interface LocalDeploymentSession {
  sessionId: string;
  serviceName?: string;
  status: 'NOT_DEPLOYED' | 'STARTING' | 'BUILDING' | 'RUNNING' | 'HEALTHY' | 'STOPPED' | 'ERROR' | 'FAILED' | 'IDLE' | 'DOCKER_UNAVAILABLE' | 'SKIPPED_BY_CHOICE' | 'DEGRADED';
  hostPort: number;
  containerId?: string;
  dbEngine?: string;
  healthStatus?: 'UP' | 'DOWN' | 'UNKNOWN' | null;
  errorMessage?: string | null;
  message?: string;
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
  passed: boolean;
  testUrl: string;
  statusCode: number;
  statusPayload?: Record<string, unknown>;
  sessionId?: string;
  endpointTested?: string;
  status?: 'SUCCESS' | 'FAILURE' | 'SKIPPED';
  httpStatusCode?: number;
  latencyMs?: number;
  details?: string;
  message?: string;
}

/**
 * Mirrors the API's `DevOpsManifestBundle` field for field.
 *
 * It previously declared `dockerfile`, `dockerCompose`, `k8sDeployment`, `k8sService`
 * and `githubCiWorkflow` -- **none of which the API returns**. A caller reading those
 * names got `undefined`, which is why the Kubernetes tab showed hardcoded sample YAML
 * instead: the real manifests were on the response under a name this interface did not
 * describe, so the response was simply never read.
 */
export interface ManifestBundle {
  sessionId: string;
  serviceName: string;
  databaseEngine: string;
  dockerfileContent: string;
  dockerignoreContent: string;
  dockerComposeContent: string;
  githubActionsWorkflow: string;
  gitlabCiWorkflow: string;
  /** filename -> file content, e.g. `{"deployment.yaml": "..."}`. */
  kubernetesManifests: Record<string, string>;
  generatedAt: string;
}

export interface DockerCapabilityReport {
  sessionId: string;
  executionMode: 'SOURCE_ONLY' | 'DOCKER';
  readyForPreparation: boolean;
  preparedImagesAvailable: boolean;
  offlineVerified: boolean;
  checks: Array<{ name: string; status: string; detail: string }>;
  availableActions: string[];
}

export const devopsService = {
  async getDiagnostics(sessionId: string): Promise<DockerCapabilityReport> {
    return (await apiClient.get<DockerCapabilityReport>(`/devops/${sessionId}/diagnostics`)).data;
  },
  async prepareLocal(sessionId: string): Promise<LocalDeploymentSession> {
    return (await apiClient.post<LocalDeploymentSession>(`/devops/${sessionId}/prepare`)).data;
  },
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
