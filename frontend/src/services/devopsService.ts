import apiClient from './apiClient';

/**
 * Mirrors the server's deployment record.
 *
 * It previously declared `serviceName`, `dbEngine` and `message`, none of which the API
 * returns, and omitted `errorMessage`, which it does. The consequence was not cosmetic:
 * the deploy handler read `res.message || '🚀 Contenedor levantado localmente'`, so the
 * always-undefined `message` made the success fallback fire for **every** outcome,
 * including a FAILED deployment. The failure text the server had written was never read.
 *
 * The two optional fields are kept because the UI displays them; they arrive only from
 * endpoints that enrich the record, so their absence is now expressed in the type rather
 * than hidden behind a plausible default.
 */
export interface LocalDeploymentSession {
  sessionId: string;
  status: 'IDLE' | 'BUILDING' | 'RUNNING' | 'HEALTHY' | 'FAILED' | 'STOPPED' | 'DOCKER_UNAVAILABLE';
  hostPort: number;
  containerId?: string | null;
  databaseContainerId?: string | null;
  containerPort?: number;
  testUrl?: string | null;
  healthStatus?: 'UP' | 'DOWN' | 'UNKNOWN' | null;
  /** Why a deployment did not complete. Was missing here while `message` was declared. */
  errorMessage?: string | null;
  startedAt?: string | null;
  /** Enriched by some endpoints; absent from the deployment record itself. */
  serviceName?: string;
  dbEngine?: string;
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
