import apiClient from './apiClient';

export interface AuditFinding {
  id: string;
  title: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  category: string;
  filePath: string;
  lineNumber: number;
  cweId: string;
  owaspCategory: string;
  codeSnippet: string;
  description: string;
  remediationGuidance: string;
  autoFixAvailable: boolean;
}

export interface SecurityQualityReport {
  sessionId: string;
  serviceName: string;
  evaluatedStatus?: string;
  auditedAt?: string;
  qualityGate: {
    status: 'PASS' | 'WARNING' | 'BLOCKED';
    canExport: boolean;
    canDeploy?: boolean;
    score: number | null;
    summaryMessage: string;
    criticalCount: number;
    highCount: number;
    mediumCount: number;
    lowCount: number;
  };
  metrics: {
    averageCyclomaticComplexity: number;
    maxCyclomaticComplexity: number;
    totalMethodsAudited: number;
    methodsExceedingThreshold: number;
    totalLinesOfCode: number;
    duplicationPercentage: number;
    testAssertionDensity: number;
    totalCodeSmells: number;
  };
  vulnerabilities: AuditFinding[];
  violations: any[];
}

export interface RemediationPayload {
  sessionId?: string;
  persist?: boolean;
  expectedFingerprint?: string;
  findingId: string;
  filePath: string;
  sourceCode?: string;
}

export interface RemediationResponse {
  findingId: string;
  filePath: string;
  originalCode: string;
  remediatedCode: string;
  diff: string;
  applied: boolean;
}

export const securityService = {
  async getAuditReport(sessionId: string): Promise<SecurityQualityReport> {
    const response = await apiClient.get<SecurityQualityReport>(`/security/${sessionId}/report`);
    return response.data;
  },

  async runAudit(files: Record<string, string>, pomXml?: string, serviceName?: string) {
    const response = await apiClient.post<SecurityQualityReport>('/security/audit', {
      files,
      pomXml,
      serviceName,
    });
    return response.data;
  },

  async applySurgicalRemediation(payload: RemediationPayload): Promise<RemediationResponse> {
    const response = await apiClient.post<RemediationResponse>('/security/remediate', payload);
    return response.data;
  },
};
