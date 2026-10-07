import apiClient from './apiClient';

export interface AuditFinding {
  id: string;
  rule_id: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  category: string;
  file: string;
  line: number;
  message: string;
  snippet?: string;
  remediation?: string;
  title?: string;
  filePath?: string;
  lineNumber?: number;
  cweId?: string;
  owaspCategory?: string;
}

export interface SecurityQualityReport {
  sessionId: string;
  serviceName: string;
  qualityGate: {
    verdict: 'PASS' | 'WARNING' | 'BLOCKED';
    canExport: boolean;
    canDeploy: boolean;
    score: number;
    summaryMessage: string;
    criticalCount: number;
    highCount: number;
    mediumCount: number;
    lowCount: number;
  };
  metrics: {
    linesOfCode: number;
    testCoverageEstimate: number;
    cyclomaticComplexityAverage: number;
    maintainabilityIndex: number;
  };
  vulnerabilities: AuditFinding[];
  violations: any[];
}

export interface RemediationPayload {
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
