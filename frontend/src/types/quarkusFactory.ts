export type BuildTool = 'maven' | 'gradle';
export type AIMode = 'Bajo' | 'Medio' | 'Alto';
export type OrderStatus =
  | 'Recibido'
  | 'Contrato en revisión'
  | 'Aprobado'
  | 'Generando'
  | 'Probando'
  | 'En revisión'
  | 'Entregado'
  | 'Fallido';

export type ArchitecturePattern = 'layered' | 'hexagonal' | 'reactive';
export type DatabaseType =
  | 'SQL Server'
  | 'Azure SQL'
  | 'SQLite (Demo local portable)'
  | 'PostgreSQL'
  | 'H2 (En memoria)'
  | 'MySQL';

export type SecurityType =
  | 'JWT (SmallRye JWT)'
  | 'OAuth2 / OIDC'
  | 'Sin autenticación';

export interface BasicDataBlock {
  service_name: string;
  team: string;
  group_id: string;
  java_version: string;
  build_tool: BuildTool;
}

export interface BusinessRequirementBlock {
  description: string;
}

export interface TechnicalRequirementsBlock {
  database: DatabaseType;
  security: SecurityType;
  enable_kafka: boolean;
  integraciones: string[];
}

export interface AIModeBlock {
  mode: AIMode;
  estimated_tokens_min: number;
  estimated_tokens_max: number;
}

export interface AttachmentsBlock {
  existing_openapi?: string | null;
  support_docs: string[];
}

export interface CreateOrderRequest {
  basic_data: BasicDataBlock;
  business: BusinessRequirementBlock;
  technical: TechnicalRequirementsBlock;
  ai_mode?: AIModeBlock;
  attachments?: AttachmentsBlock;
}

export interface ClarificationQuestion {
  id: string;
  category?: string;
  question: string;
  context_or_reason: string;
  suggested_options: string[];
  user_answer?: string | null;
}

export interface ClarificationAnswerItem {
  question_id: string;
  answer: string;
}

export interface SubmitAnswersRequest {
  answers: ClarificationAnswerItem[];
}

export interface BddScenario {
  title: string;
  given: string;
  when: string;
  then: string;
}

export interface UserStory {
  id: string;
  title: string;
  role: string;
  goal: string;
  benefit: string;
  scenarios: BddScenario[];
}

export interface ColumnDefinition {
  name: string;
  data_type: string;
  is_primary_key: boolean;
  is_foreign_key: boolean;
  references?: string | null;
  is_nullable: boolean;
  description: string;
}

export interface TableDefinition {
  name: string;
  description: string;
  columns: ColumnDefinition[];
}

export interface RelationshipDefinition {
  source_table: string;
  target_table: string;
  relation_type: string;
  description: string;
}

export interface DatabaseModelProposal {
  database_engine: string;
  tables: TableDefinition[];
  relationships: RelationshipDefinition[];
  mermaid_er_diagram: string;
  ddl_sql: string;
  validation_notes: string[];
}

export interface ApproveContractRequest {
  approved_by: string;
  comments?: string;
  modified_openapi?: string | null;
  approve_database_model?: boolean;
  modified_user_stories?: UserStory[];
  modified_database_model?: DatabaseModelProposal;
}

export interface ArchitectureOption {
  id: ArchitecturePattern;
  title: string;
  description: string;
  structure_layers: string[];
  pros: string[];
  cons: string[];
  recommended_for: string;
  is_recommended: boolean;
}

export interface ArchetypePreview {
  build_tool: BuildTool;
  config_file_name: string;
  config_file_content: string;
  folder_tree: string[];
  command_dev: string;
  command_test: string;
  summary_features: string[];
}

export interface QuarkusExtensionItem {
  id: string;
  name: string;
  version: string;
  category: string;
  description: string;
  is_selected: boolean;
  is_mandatory: boolean;
}

export interface ArchitectureProposal {
  options: ArchitectureOption[];
  selected_option: ArchitecturePattern;
  recommended_extensions: string[];
  quarkus_extensions: QuarkusExtensionItem[];
  maven_preview: ArchetypePreview;
  gradle_preview: ArchetypePreview;
}

export interface SelectArchitectureRequest {
  selected_pattern: ArchitecturePattern;
  chosen_build_tool: BuildTool;
  extensions: string[];
  selected_extensions?: QuarkusExtensionItem[];
}

export interface ApproveDeliveryRequest {
  approved_by: string;
  comments?: string;
  target_git_repo?: string;
  branch_name?: string;
}

export interface SpecializedAgentInfo {
  id: string;
  number: number;
  name: string;
  role: string;
  status: string;
  tokens_consumed: number;
  deliverables: string[];
}

export interface TokensAudit {
  estimated_range: [number, number];
  by_agent: {
    // 8 Agentes Especializados
    requirements?: number;
    architecture?: number;
    coding?: number;
    database?: number;
    security?: number;
    testing_debug?: number;
    code_review?: number;
    devops?: number;
    // Retrocompatibilidad
    analista?: number;
    arquitecto?: number;
    desarrollador?: number;
    qa?: number;
    documentador?: number;
    revisor?: number;
  };
  total_consumed: number;
}

export interface FactoryOrder {
  id: string;
  created_at: string;
  updated_at: string;
  status: OrderStatus;
  basic_data: BasicDataBlock;
  business: BusinessRequirementBlock;
  technical: TechnicalRequirementsBlock;
  ai_mode: AIModeBlock;
  attachments: AttachmentsBlock;
  clarification_questions: ClarificationQuestion[];
  clarifications_completed: boolean;
  openapi_contract?: string | null;
  user_stories?: UserStory[];
  database_model?: DatabaseModelProposal | null;
  database_model_approved?: boolean;
  control_1_approved: boolean;
  control_1_approval_info?: {
    approved_by: string;
    timestamp: string;
    comments?: string;
    database_model_approved?: boolean;
  } | null;
  architecture_proposal?: ArchitectureProposal | null;
  chosen_architecture?: {
    pattern: string;
    build_tool: string;
    extensions: string[];
  } | null;
  skeleton_generated: boolean;
  code_generated: boolean;
  tests_executed: boolean;
  quarkus_extensions?: QuarkusExtensionItem[];
  self_healing_log?: Array<{
    step: string;
    status: string;
    detail: string;
    attempts?: number;
  }>;
  code_review_report?: {
    verdict: string;
    score: number;
    revisor?: string;
    checks: Array<{
      name: string;
      status: string;
      notes: string;
    }>;
  } | null;
  tests_summary?: {
    test_framework: string;
    total_tests: number;
    passed: number;
    failed: number;
    skipped: number;
    coverage_percentage: number;
    execution_time_ms: number;
    build_status: string;
    revisor_verdict?: string;
    tested_entities?: string[];
  } | null;
  correction_attempts_used: number;
  generated_files: Record<string, string>;
  documentation: Record<string, string>;
  control_2_approved: boolean;
  control_2_approval_info?: {
    approved_by: string;
    timestamp: string;
    comments?: string;
    target_git_repo?: string;
    branch_name?: string;
  } | null;
  devops_artifacts: Record<string, string>;
  tokens_audit: TokensAudit;
  specialized_agents?: SpecializedAgentInfo[];
  step_durations_sec: Record<string, number>;
  timeline_events: Array<{
    timestamp: string;
    event: string;
    message: string;
    tokens?: number;
    mode?: string;
  }>;
}

