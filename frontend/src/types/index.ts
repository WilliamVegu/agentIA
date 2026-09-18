export type SessionStatus = 'CREATED' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'BLOCKED';

export type LifecycleStage =
  | 'REQUIREMENTS'
  | 'STORIES'
  | 'ARCHITECTURE'
  | 'DATA_MODEL'
  | 'CODE_TESTS'
  | 'SECURITY_AUDIT'
  | 'DEVOPS_DEPLOY';

export type StageState = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'OUTDATED' | 'SKIPPED';

export interface StageInfo {
  stage: LifecycleStage;
  label: string;
  status: StageState;
  progress: number;
  message?: string;
  started_at?: string;
  completed_at?: string;
}

export interface LifecycleOverview {
  session_id: string;
  status: SessionStatus;
  current_stage: LifecycleStage;
  overall_progress: number;
  stages: Record<LifecycleStage, StageInfo>;
  is_paused: boolean;
  has_outdated_upstream: boolean;
  block_reason?: string;
}

export interface Session {
  session_id: string;
  spec_name: string;
  database: 'POSTGRESQL' | 'MYSQL' | 'H2';
  status: SessionStatus;
  created_at: string;
  updated_at?: string;
  current_stage: LifecycleStage;
  repair_iterations?: number;
  block_reason?: string;
  workspace_dir?: string;
  metrics?: Record<string, any>;
}

export interface BddScenario {
  title: string;
  given: string;
  when: string;
  then: string;
}

export interface BddStory {
  id: string;
  title: string;
  role: string;
  feature: string;
  benefit: string;
  scenarios: BddScenario[];
  detected_entities: string[];
}

export interface RequirementsData {
  stories: BddStory[];
  entities: string[];
  raw_spec_md?: string;
}

export interface ArchitectureLayer {
  name: string;
  description: string;
  components: {
    name: string;
    package: string;
    responsibilities: string[];
  }[];
}

export interface RestContract {
  endpoint: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  description: string;
  requestRecord?: string;
  responseRecord?: string;
  statusCode: number;
}

export interface ArchitectureData {
  mermaid_diagram: string;
  layers: ArchitectureLayer[];
  contracts: RestContract[];
}

export interface EntityField {
  name: string;
  type: string;
  primaryKey?: boolean;
  nullable?: boolean;
  relationship?: string;
}

export interface DomainEntity {
  name: string;
  tableName: string;
  description?: string;
  fields: EntityField[];
}

export interface DomainModelsData {
  entities: DomainEntity[];
  er_diagram: string;
  schema_sql: string;
  data_sql: string;
}

export type QualityVerdict = 'PASS' | 'WARNING' | 'BLOCKED';

export interface SastFinding {
  id: string;
  rule_id: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  category: string;
  file: string;
  line: number;
  message: string;
  snippet?: string;
  remediation?: string;
}

export interface SecurityAuditData {
  score: number;
  verdict: QualityVerdict;
  findings: SastFinding[];
  has_hardcoded_secrets: boolean;
  cve_count: number;
  test_coverage_pct: number;
}

export interface ManifestItem {
  filename: string;
  content: string;
  language: string;
}

export interface OrderPlaygroundItem {
  id: number;
  customerName: string;
  product: string;
  amount: number;
  status: 'PENDING' | 'CONFIRMED' | 'SHIPPED' | 'CANCELLED';
  createdAt: string;
}

export interface DevOpsData {
  deployment_status: 'NOT_DEPLOYED' | 'STARTING' | 'RUNNING' | 'STOPPED' | 'ERROR' | 'DOCKER_UNAVAILABLE';
  service_port: number;
  container_id?: string;
  health_status: 'UP' | 'DOWN' | 'UNKNOWN';
  manifests: ManifestItem[];
  logs: string[];
  orders: OrderPlaygroundItem[];
}

export type LlmProviderType = 'gemini' | 'groq' | 'openai' | 'mock';

export interface LlmConfig {
  provider: LlmProviderType;
  apiKey: string;
  model: string;
  temperature: number;
}

export interface User {
  email: string;
  name: string;
  role: 'Architect' | 'Lead' | 'Engineer' | 'Demo';
  avatarUrl?: string;
}

export interface SelfRepairItem {
  iteration: number;
  timestamp: string;
  stage: string;
  error_type: string;
  diff: string;
  explanation: string;
  status: 'FIXED' | 'FAILED' | 'RETRYING';
}
