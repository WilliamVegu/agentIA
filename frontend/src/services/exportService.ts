import apiClient from './apiClient';

export interface PublishPayload {
  repositoryUrl: string;
  branchName: string;
  gitToken?: string;
  commitMessage?: string;
}

export interface PublishResult {
  branchUrl: string;
  commitHash: string;
  pullRequestUrl?: string;
  branchName: string;
}

export interface ArtifactItem {
  id: string;
  sessionId: string;
  relativePath: string;
  fileType: string;
  sizeBytes: number;
}

export const exportService = {
  getDownloadZipUrl(sessionId: string): string {
    return `/api/v1/sessions/${sessionId}/export`;
  },

  async listArtifacts(sessionId: string): Promise<ArtifactItem[]> {
    const response = await apiClient.get<ArtifactItem[]>(`/sessions/${sessionId}/artifacts`);
    return response.data;
  },

  async getArtifactContent(sessionId: string, filePath: string): Promise<string> {
    const response = await apiClient.get<string>(`/sessions/${sessionId}/artifacts/content`, {
      params: { path: filePath },
    });
    return response.data;
  },

  async publishToGit(sessionId: string, payload: PublishPayload): Promise<PublishResult> {
    const response = await apiClient.post<PublishResult>(`/sessions/${sessionId}/publish`, payload);
    return response.data;
  },
};
