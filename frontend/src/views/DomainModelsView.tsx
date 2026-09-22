import React, { useState } from 'react';
import {
  Database,
  Code2,
  Download,
  Sparkles,
  Send,
  CheckCircle2,
  ArrowRight,
  Boxes,
  Key,
  ShieldCheck,
  Table,
  Workflow,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
} from 'lucide-react';
import JSZip from 'jszip';
import { SingleRowCard } from '../components/common/SingleRowCard';
import { MermaidViewer } from '../components/common/MermaidViewer';
import { CodeViewer } from '../components/common/CodeViewer';
import { SlideOverDrawer } from '../components/common/SlideOverDrawer';
import { useStudio } from '../context/StudioContext';
import { useLlm } from '../context/LlmContext';
import { modelsService } from '../services/modelsService';
import { specService } from '../services/specService';
import { orchestratorService } from '../services/orchestratorService';
import apiClient from '../services/apiClient';

const DEFAULT_ER_MERMAID = `erDiagram
    ORDER ||--|{ ORDER_ITEM : contains
    CUSTOMER ||--o{ ORDER : places
    ORDER {
        bigint id PK
        varchar customer_id
        varchar status
        numeric total_amount
        timestamp created_at
        timestamp updated_at
    }
    ORDER_ITEM {
        bigint id PK
        bigint order_id FK
        varchar product_id
        int quantity
        numeric unit_price
    }
    CUSTOMER {
        varchar id PK
        varchar name
        varchar email
    }
`;

const DEFAULT_SCHEMA_SQL = `-- PostgreSQL 16 ANSI DDL & H2 In-Memory (MODE=PostgreSQL)
CREATE TABLE IF NOT EXISTS customers (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    customer_id VARCHAR(64) NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id VARCHAR(64) NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
`;

const DEFAULT_DATA_SQL = `-- PostgreSQL / H2 Seed Data (DML)
INSERT INTO customers (id, name, email) VALUES
    ('cust-001', 'Rodrigo Mendoza', 'architect@tcs.com'),
    ('cust-002', 'Tata Enterprise Client', 'enterprise@client.com')
ON CONFLICT (id) DO NOTHING;

INSERT INTO orders (id, customer_id, status, total_amount) VALUES
    (101, 'cust-001', 'CONFIRMED', 250.00),
    (102, 'cust-002', 'PENDING', 1420.50)
ON CONFLICT (id) DO NOTHING;

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
    (101, 'PROD-TCS-CLOUD', 1, 250.00),
    (102, 'PROD-TCS-INFRA', 2, 710.25)
ON CONFLICT DO NOTHING;
`;

export const DomainModelsView: React.FC = () => {
  const {
    activeSessionId,
    activeSession,
    currentDraft,
    architectureDesign,
    dataModelDesign,
    setDataModelDesign,
    setCurrentSpecId,
    setParsedSpec,
    reloadCurrentOverview,
    setActiveTab,
    refreshSessions,
    selectSession,
  } = useStudio();
  const { provider, apiKey } = useLlm();

  // Active state
  const [design, setDesign] = useState<any>(
    dataModelDesign || {
      serviceName: activeSession?.specName || currentDraft?.serviceName || 'order-service',
      packageName: currentDraft?.packageName || 'com.tcs.microservice',
      mermaidErDiagram: DEFAULT_ER_MERMAID,
      sqlSchema: {
        schemaDdl: DEFAULT_SCHEMA_SQL,
        seedDml: DEFAULT_DATA_SQL,
      },
      entities: [
        {
          name: 'Order',
          tableName: 'orders',
          description: 'Entidad agregada principal que representa órdenes de compra',
          attributes: [
            { name: 'id', columnName: 'id', javaType: 'Long', sqlType: 'BIGINT', isPrimaryKey: true, nullable: false, isUnique: true, validationRules: ['@NotNull'] },
            { name: 'customerId', columnName: 'customer_id', javaType: 'String', sqlType: 'VARCHAR', isPrimaryKey: false, nullable: false, isUnique: false, validationRules: ['@NotBlank'] },
            { name: 'status', columnName: 'status', javaType: 'String', sqlType: 'VARCHAR', isPrimaryKey: false, nullable: false, isUnique: false, validationRules: ['@NotNull'] },
            { name: 'totalAmount', columnName: 'total_amount', javaType: 'BigDecimal', sqlType: 'NUMERIC', isPrimaryKey: false, nullable: false, isUnique: false, validationRules: ['@PositiveOrZero'] },
            { name: 'createdAt', columnName: 'created_at', javaType: 'Instant', sqlType: 'TIMESTAMP WITH TIME ZONE', isPrimaryKey: false, nullable: false, isUnique: false, validationRules: [] },
            { name: 'updatedAt', columnName: 'updated_at', javaType: 'Instant', sqlType: 'TIMESTAMP WITH TIME ZONE', isPrimaryKey: false, nullable: false, isUnique: false, validationRules: [] },
          ],
          relationships: [
            { relationshipType: 'ONE_TO_MANY', targetEntity: 'OrderItem', foreignKeyColumn: 'order_id', description: 'Una orden contiene múltiples ítems de compra' }
          ]
        },
        {
          name: 'OrderItem',
          tableName: 'order_items',
          description: 'Detalle de línea de producto en una orden',
          attributes: [
            { name: 'id', columnName: 'id', javaType: 'Long', sqlType: 'BIGINT', isPrimaryKey: true, nullable: false, isUnique: true, validationRules: ['@NotNull'] },
            { name: 'orderId', columnName: 'order_id', javaType: 'Long', sqlType: 'BIGINT', isPrimaryKey: false, nullable: false, isUnique: false, validationRules: ['@NotNull'] },
            { name: 'productId', columnName: 'product_id', javaType: 'String', sqlType: 'VARCHAR', isPrimaryKey: false, nullable: false, isUnique: false, validationRules: ['@NotBlank'] },
            { name: 'quantity', columnName: 'quantity', javaType: 'Integer', sqlType: 'INTEGER', isPrimaryKey: false, nullable: false, isUnique: false, validationRules: ['@Positive'] },
            { name: 'unitPrice', columnName: 'unit_price', javaType: 'BigDecimal', sqlType: 'NUMERIC', isPrimaryKey: false, nullable: false, isUnique: false, validationRules: ['@PositiveOrZero'] },
          ],
          relationships: [
            { relationshipType: 'MANY_TO_ONE', targetEntity: 'Order', foreignKeyColumn: 'order_id', description: 'Pertenece a una orden principal' }
          ]
        }
      ],
      javaEntityClasses: {
        Order: `package com.tcs.microservice.model;

import jakarta.persistence.*;
import jakarta.validation.constraints.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "orders")
public class Order {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    @Column(name = "customer_id", nullable = false)
    private String customerId;

    @NotNull
    @Column(name = "status", nullable = false)
    private String status;

    @PositiveOrZero
    @Column(name = "total_amount", nullable = false, precision = 12, scale = 2)
    private BigDecimal totalAmount;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt = Instant.now();

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<OrderItem> items = new ArrayList<>();

    public Order() {}

    // Getters and setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getCustomerId() { return customerId; }
    public void setCustomerId(String customerId) { this.customerId = customerId; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public BigDecimal getTotalAmount() { return totalAmount; }
    public void setTotalAmount(BigDecimal totalAmount) { this.totalAmount = totalAmount; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
    public List<OrderItem> getItems() { return items; }
    public void setItems(List<OrderItem> items) { this.items = items; }
}`,
        OrderItem: `package com.tcs.microservice.model;

import jakarta.persistence.*;
import jakarta.validation.constraints.*;
import java.math.BigDecimal;

@Entity
@Table(name = "order_items")
public class OrderItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "order_id", nullable = false)
    private Order order;

    @NotBlank
    @Column(name = "product_id", nullable = false)
    private String productId;

    @Positive
    @Column(name = "quantity", nullable = false)
    private Integer quantity;

    @PositiveOrZero
    @Column(name = "unit_price", nullable = false, precision = 12, scale = 2)
    private BigDecimal unitPrice;

    public OrderItem() {}

    // Getters and setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Order getOrder() { return order; }
    public void setOrder(Order order) { this.order = order; }
    public String getProductId() { return productId; }
    public void setProductId(String productId) { this.productId = productId; }
    public Integer getQuantity() { return quantity; }
    public void setQuantity(Integer quantity) { this.quantity = quantity; }
    public BigDecimal getUnitPrice() { return unitPrice; }
    public void setUnitPrice(BigDecimal unitPrice) { this.unitPrice = unitPrice; }
}`
      }
    }
  );

  const [activeSqlTab, setActiveSqlTab] = useState<'schema' | 'data'>('schema');
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [isRefining, setIsRefining] = useState(false);
  const [refinePrompt, setRefinePrompt] = useState('');
  const [targetEntity, setTargetEntity] = useState('Todas las entidades');
  const [feedback, setFeedback] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showErSource, setShowErSource] = useState(false);
  const [expandedEntity, setExpandedEntity] = useState<string | null>(design.entities?.[0]?.name || null);
  const [viewJavaCode, setViewJavaCode] = useState<string | null>(null);

  const updateDesign = (newDesign: any) => {
    setDesign(newDesign);
    setDataModelDesign(newDesign);
  };

  const handleSynthesizeAi = async () => {
    setIsSynthesizing(true);
    setErrorMsg(null);
    try {
      const draftPayload = currentDraft || architectureDesign || {
        serviceName: activeSession?.specName || 'order-service',
        packageName: 'com.tcs.microservice',
        basePort: 8080,
        entities: [{ name: 'Order', tableName: 'orders', attributes: [{ name: 'id', type: 'Long', isPrimaryKey: true }] }],
        userStories: [],
      };
      const res = await modelsService.generate({
        draft: draftPayload,
        apiKey,
        provider,
      });
      updateDesign(res);
      setFeedback('Modelos de dominio JPA y esquema SQL relacional sintetizados exitosamente.');
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Error al generar modelos y SQL relacional');
    } finally {
      setIsSynthesizing(false);
    }
  };

  const handleRefineSubmit = async () => {
    if (!refinePrompt.trim()) return;
    setIsRefining(true);
    setErrorMsg(null);
    try {
      const res = await modelsService.refine({
        currentResponse: design,
        feedbackPrompt: refinePrompt.trim(),
        targetEntity: targetEntity === 'Todas las entidades' ? undefined : targetEntity,
        apiKey,
        provider,
      });
      updateDesign(res);
      setIsRefining(false);
      setRefinePrompt('');
      setFeedback('Modelos JPA y scripts SQL actualizados con los cambios solicitados.');
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Error refinando modelos');
    } finally {
      setIsRefining(false);
    }
  };

  const handleDownloadSchemaSql = () => {
    const sql = design.sqlSchema?.schemaDdl || DEFAULT_SCHEMA_SQL;
    const blob = new Blob([sql], { type: 'application/sql;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `schema-${design.serviceName || 'service'}.sql`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const handleDownloadDataSql = () => {
    const sql = design.sqlSchema?.seedDml || DEFAULT_DATA_SQL;
    const blob = new Blob([sql], { type: 'application/sql;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `data-${design.serviceName || 'service'}.sql`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const handleDownloadJavaEntitiesZip = async () => {
    const zip = new JSZip();
    const schemaDdl = design.sqlSchema?.schemaDdl || DEFAULT_SCHEMA_SQL;
    const seedDml = design.sqlSchema?.seedDml || DEFAULT_DATA_SQL;
    zip.file('schema.sql', schemaDdl);
    zip.file('data.sql', seedDml);

    const modelFolder = zip.folder('model');
    const javaClasses = design.javaEntityClasses || {};
    Object.entries(javaClasses).forEach(([name, code]) => {
      modelFolder?.file(`${name}.java`, code as string);
    });

    const content = await zip.generateAsync({ type: 'blob' });
    const url = URL.createObjectURL(content);
    const a = document.createElement('a');
    a.href = url;
    a.download = `domain-entities-${design.serviceName || 'service'}.zip`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const handleTransferToGeneration = async () => {
    setIsSynthesizing(true);
    setErrorMsg(null);
    try {
      const rawServiceName = (design.serviceName || activeSession?.specName || currentDraft?.serviceName || 'order-service')
        .toLowerCase()
        .replace(/[^a-z0-9-]/g, '-')
        .replace(/^-+|-+$/g, '') || 'order-service';
      const cleanPackage = design.packageName || currentDraft?.packageName || `com.tcs.${rawServiceName.replace(/[^a-z0-9]/g, '')}`;

      const rawEntities = (design.entities && design.entities.length > 0)
        ? design.entities
        : (currentDraft?.entities && currentDraft.entities.length > 0)
        ? currentDraft.entities
        : [{ name: 'Order', tableName: 'orders', attributes: [{ name: 'id', type: 'Long', isPrimaryKey: true }] }];

      const rawStories = (architectureDesign?.userStories && architectureDesign.userStories.length > 0)
        ? architectureDesign.userStories
        : (currentDraft?.userStories && currentDraft.userStories.length > 0)
        ? currentDraft.userStories
        : [
            {
              id: 'US-001',
              priority: 'P1',
              role: 'Usuario',
              intent: 'Gestionar entidades relacionales',
              benefit: 'Mantener consistencia transaccional',
              scenarios: [
                {
                  scenarioId: 'AC-1.1',
                  given: 'Servicio y repositorio JPA inicializados',
                  when: 'Se envía una petición HTTP para persistir la entidad',
                  then: 'Se almacena en la tabla relacional y se retorna 201 Created',
                },
              ],
            },
          ];

      const blueprintPayload = {
        serviceName: rawServiceName,
        packageName: cleanPackage,
        basePort: 8080,
        databaseMode: 'PostgreSQL',
        entities: rawEntities.map((e: any) => {
          const name = typeof e === 'string' ? e : e?.name || 'Order';
          const tableName = typeof e === 'object' && e?.tableName ? e.tableName : `${name.toLowerCase()}s`;
          return {
            name,
            tableName,
            attributes: ((typeof e === 'object' && (e?.attributes || e?.fields)) || [{ name: 'id', type: 'Long', isPrimaryKey: true }]).map((a: any) => ({
              name: a.name,
              type: a.type || a.javaType || 'Long',
              nullable: !!a.nullable,
              isPrimaryKey: !!a.isPrimaryKey || !!a.primaryKey,
              validationRules: a.validationRules || [],
            })),
          };
        }),
        userStories: rawStories.map((s: any) => ({
          id: s.id,
          priority: s.priority || 'P1',
          role: s.role || 'Usuario',
          intent: s.intent || s.feature || 'Gestionar entidades de negocio',
          benefit: s.benefit || 'Completar operaciones',
          scenarios: (s.scenarios || []).map((sc: any, idx: number) => ({
            scenarioId: sc.scenarioId || `AC-${s.id}.${idx + 1}`,
            given: sc.given || 'Precondición válida',
            when: sc.when || 'Operación ejecutada',
            then: sc.then || 'Resultado esperado obtenido',
          })),
        })),
      };

      const res = await specService.submitJson(blueprintPayload);
      if (res?.specId) {
        setCurrentSpecId(res.specId);
        setParsedSpec(res);
        try {
          const sessResp = await apiClient.post('/sessions', { specId: res.specId });
          const newSessionId = sessResp.data?.sessionId || sessResp.data?.session_id;
          if (newSessionId) {
            await refreshSessions();
            selectSession(newSessionId);
          }
        } catch (sessErr) {
          console.warn('Could not auto-start session:', sessErr);
        }
      }
      if (activeSessionId) {
        await orchestratorService.invalidateDownstream(activeSessionId, 'DATA_MODEL');
        await reloadCurrentOverview();
      }
      setActiveTab(5); // Switch to Tab 5 Monitor
    } catch (err: any) {
      console.error('Error al transferir modelos a generación:', err);
      setActiveTab(5);
    } finally {
      setIsSynthesizing(false);
    }
  };

  const entities = design.entities || [];

  return (
    <div className="space-y-6">
      {/* Top Banner Card */}
      <SingleRowCard
        title="Fase 3: Modelos de Dominio JPA & Esquema SQL Relacional"
        subtitle="Entidades de dominio fuertemente tipadas, claves primarias autonuméricas, auditoría UTC y scripts relacionales sincronizados"
        badge={
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-900/60 text-emerald-700 dark:text-emerald-300">
            Jakarta Persistence / PostgreSQL 16
          </span>
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleSynthesizeAi}
              disabled={isSynthesizing}
              className="py-2 px-3.5 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-all shadow-sm flex items-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{isSynthesizing ? 'Sintetizando...' : 'Sintetizar con IA'}</span>
            </button>
            <button
              onClick={() => setIsRefining(true)}
              className="py-2 px-3.5 rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/60 transition-colors"
            >
              Refinar Esquema
            </button>
            <button
              onClick={handleTransferToGeneration}
              disabled={isSynthesizing}
              className="py-2 px-4 rounded-lg text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 shadow-sm transition-all flex items-center gap-1.5"
            >
              <span>Aprobar y Transferir a Generación →</span>
            </button>
          </div>
        }
      >
        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600 dark:text-slate-400">
          <span>
            Microservicio: <strong className="text-slate-900 dark:text-white">{design.serviceName}</strong>
          </span>
          <span>•</span>
          <span>
            Paquete: <code className="text-blue-600 dark:text-blue-400">{design.packageName}</code>
          </span>
          <span>•</span>
          <span>
            Entidades: <strong className="text-slate-900 dark:text-white">{entities.length}</strong>
          </span>
        </div>

        {feedback && (
          <div className="mt-2.5 p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-200 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{feedback}</span>
          </div>
        )}
        {errorMsg && (
          <div className="mt-2.5 p-2.5 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-200 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}
      </SingleRowCard>

      {/* 1. Mermaid Entity-Relationship Diagram */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
            <Workflow className="w-4 h-4 text-emerald-600" />
            <span>1. Diagrama Entidad-Relación Visual (Mermaid erDiagram)</span>
          </h3>
          <button
            onClick={() => setShowErSource(!showErSource)}
            className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline"
          >
            {showErSource ? 'Ocultar código fuente' : 'Ver código Mermaid erDiagram'}
          </button>
        </div>

        <MermaidViewer
          chart={design.mermaidErDiagram || DEFAULT_ER_MERMAID}
          title="Modelo Relacional Normalizado"
        />

        {showErSource && (
          <pre className="p-3 bg-slate-950 text-emerald-400 rounded-xl font-mono text-xs overflow-x-auto border border-slate-800">
            {design.mermaidErDiagram || DEFAULT_ER_MERMAID}
          </pre>
        )}
      </div>

      {/* 2. Interactive JPA Domain Entities & Attributes Table */}
      <div className="space-y-4">
        <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
          <Boxes className="w-4 h-4 text-indigo-600" />
          <span>2. Entidades de Dominio JPA & Atributos Tipados ({entities.length})</span>
        </h3>

        <div className="space-y-3">
          {entities.map((entity: any) => {
            const entityName = typeof entity === 'string' ? entity : entity?.name || 'Order';
            const entityTableName = typeof entity === 'object' && entity?.tableName ? entity.tableName : `${entityName.toLowerCase()}s`;
            const isExpanded = expandedEntity === entityName;
            const javaCode = design.javaEntityClasses?.[entityName];

            return (
              <div
                key={entityName}
                className="border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-900 overflow-hidden shadow-sm"
              >
                <div
                  onClick={() => setExpandedEntity(isExpanded ? null : entityName)}
                  className="flex flex-wrap items-center justify-between p-4 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-850 transition-colors"
                >
                  <div className="flex items-center gap-2 font-mono">
                    <span className="font-bold text-sm text-slate-900 dark:text-white">
                      📦 {entityName}
                    </span>
                    <span className="text-slate-400 text-xs">➔</span>
                    <span className="px-2 py-0.5 rounded text-xs bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold">
                      Tabla: {entityTableName}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {javaCode && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setViewJavaCode(viewJavaCode === entity.name ? null : entity.name);
                        }}
                        className="py-1 px-2.5 rounded text-xs font-semibold bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 hover:bg-blue-100 transition-colors flex items-center gap-1"
                      >
                        <Code2 className="w-3.5 h-3.5" />
                        <span>{viewJavaCode === entity.name ? 'Ocultar Java' : 'Ver Java JPA'}</span>
                      </button>
                    )}
                    {isExpanded ? (
                      <ChevronUp className="w-4 h-4 text-slate-500" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-slate-500" />
                    )}
                  </div>
                </div>

                {isExpanded && (
                  <div className="p-4 pt-0 space-y-4 border-t border-slate-100 dark:border-slate-800">
                    {entity.description && (
                      <p className="text-xs text-slate-600 dark:text-slate-400 italic pt-2">
                        {entity.description}
                      </p>
                    )}

                    {/* Java Source Preview if toggled */}
                    {viewJavaCode === entity.name && javaCode && (
                      <div className="pt-2">
                        <CodeViewer
                          code={javaCode}
                          language="java"
                          filename={`${entity.name}.java`}
                          maxHeight="max-h-80"
                        />
                      </div>
                    )}

                    {/* Attributes Table */}
                    <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
                      <table className="w-full text-left text-xs font-mono">
                        <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-700 dark:text-slate-300 uppercase text-[11px] border-b border-slate-200 dark:border-slate-800">
                          <tr>
                            <th className="py-2 px-3">Campo (Java)</th>
                            <th className="py-2 px-3">Columna (SQL)</th>
                            <th className="py-2 px-3">Tipo Java</th>
                            <th className="py-2 px-3">Tipo SQL</th>
                            <th className="py-2 px-2 text-center">PK</th>
                            <th className="py-2 px-2 text-center">Nulabilidad</th>
                            <th className="py-2 px-2 text-center">Unicidad</th>
                            <th className="py-2 px-3">Validaciones</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                          {(entity.attributes || []).map((attr: any, aIdx: number) => (
                            <tr key={aIdx} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                              <td className="py-2 px-3 font-semibold text-slate-900 dark:text-white">
                                {attr.name}
                              </td>
                              <td className="py-2 px-3 text-slate-600 dark:text-slate-400">
                                {attr.columnName}
                              </td>
                              <td className="py-2 px-3 text-blue-600 dark:text-blue-400">
                                {attr.javaType}
                              </td>
                              <td className="py-2 px-3 text-purple-600 dark:text-purple-400">
                                {attr.sqlType}
                              </td>
                              <td className="py-2 px-2 text-center">
                                {attr.isPrimaryKey ? (
                                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                                    🔑 PK
                                  </span>
                                ) : (
                                  <span className="text-slate-400">—</span>
                                )}
                              </td>
                              <td className="py-2 px-2 text-center">
                                {attr.nullable ? (
                                  <span className="text-slate-500">NULL</span>
                                ) : (
                                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                                    NOT NULL
                                  </span>
                                )}
                              </td>
                              <td className="py-2 px-2 text-center">
                                {attr.isUnique ? (
                                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                                    ⭐ UNIQUE
                                  </span>
                                ) : (
                                  <span className="text-slate-400">—</span>
                                )}
                              </td>
                              <td className="py-2 px-3 text-slate-500">
                                {(attr.validationRules || []).join(', ') || '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Domain Relationships */}
                    {entity.relationships && entity.relationships.length > 0 && (
                      <div className="space-y-1.5 pt-1">
                        <strong className="text-xs text-slate-700 dark:text-slate-300 block">
                          🔗 Relaciones de Dominio:
                        </strong>
                        <div className="space-y-1">
                          {entity.relationships.map((rel: any, rIdx: number) => (
                            <div
                              key={rIdx}
                              className="p-2 rounded bg-slate-50 dark:bg-slate-950/60 border border-slate-100 dark:border-slate-800 text-xs font-mono flex items-center gap-2"
                            >
                              <span className="px-2 py-0.5 rounded font-bold bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300 text-[11px]">
                                {rel.relationshipType}
                              </span>
                              <span>hacia</span>
                              <strong className="text-slate-900 dark:text-white">
                                {rel.targetEntity}
                              </strong>
                              {rel.foreignKeyColumn && (
                                <span className="text-slate-500">
                                  (FK: {rel.foreignKeyColumn})
                                </span>
                              )}
                              {rel.joinTableName && (
                                <span className="text-slate-500">
                                  [Tabla Join: {rel.joinTableName}]
                                </span>
                              )}
                              {rel.description && (
                                <span className="text-slate-400 font-sans italic ml-auto">
                                  {rel.description}
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. Synchronized SQL Scripts Tabs */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
            <Code2 className="w-4 h-4 text-blue-600" />
            <span>3. Scripts SQL Relacionales Sincronizados (PostgreSQL & H2)</span>
          </h3>
          <div className="flex items-center gap-1.5 p-1 rounded-lg bg-slate-200 dark:bg-slate-800 text-xs">
            <button
              onClick={() => setActiveSqlTab('schema')}
              className={`px-3 py-1 rounded-md transition-all font-medium ${
                activeSqlTab === 'schema'
                  ? 'bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
              }`}
            >
              schema.sql (DDL)
            </button>
            <button
              onClick={() => setActiveSqlTab('data')}
              className={`px-3 py-1 rounded-md transition-all font-medium ${
                activeSqlTab === 'data'
                  ? 'bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
              }`}
            >
              data.sql (Semillas DML)
            </button>
          </div>
        </div>

        {activeSqlTab === 'schema' ? (
          <CodeViewer
            code={design.sqlSchema?.schemaDdl || DEFAULT_SCHEMA_SQL}
            language="sql"
            filename="src/main/resources/schema.sql"
            maxHeight="max-h-[380px]"
          />
        ) : (
          <CodeViewer
            code={design.sqlSchema?.seedDml || DEFAULT_DATA_SQL}
            language="sql"
            filename="src/main/resources/data.sql"
            maxHeight="max-h-[380px]"
          />
        )}
      </div>

      {/* 4. Downloads & Pipeline Handoff */}
      <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4 shadow-sm">
        <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
          <Download className="w-4 h-4 text-blue-600" />
          <span>4. Exportación de Artefactos de Persistencia y Transferencia</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <button
            onClick={handleDownloadSchemaSql}
            className="flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-xs font-semibold text-slate-800 dark:text-slate-200 transition-colors shadow-sm"
          >
            <Download className="w-3.5 h-3.5 text-blue-600" />
            <span>Descargar schema.sql</span>
          </button>

          <button
            onClick={handleDownloadDataSql}
            className="flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-xs font-semibold text-slate-800 dark:text-slate-200 transition-colors shadow-sm"
          >
            <Download className="w-3.5 h-3.5 text-emerald-600" />
            <span>Descargar data.sql</span>
          </button>

          <button
            onClick={handleDownloadJavaEntitiesZip}
            className="flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-xs font-semibold text-slate-800 dark:text-slate-200 transition-colors shadow-sm"
          >
            <Download className="w-3.5 h-3.5 text-purple-600" />
            <span>Descargar Clases Java (.zip)</span>
          </button>
        </div>

        <div className="pt-2 border-t border-slate-200 dark:border-slate-800 flex justify-end">
          <button
            onClick={handleTransferToGeneration}
            disabled={isSynthesizing}
            className="w-full sm:w-auto flex items-center justify-center gap-2 py-2.5 px-6 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 shadow-md transition-all"
          >
            <span>➡️ Transferir al Motor de Generación de Código</span>
          </button>
        </div>
      </div>

      {/* SlideOverDrawer for Models & SQL Refinement */}
      <SlideOverDrawer
        isOpen={isRefining}
        onClose={() => setIsRefining(false)}
        title="Asistente IA de Refinamiento de Modelos & Esquema SQL"
        subtitle="Ajuste columnas, tipos de datos, restricciones únicas o nuevas relaciones"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Entidad Objetivo
            </label>
            <select
              value={targetEntity}
              onChange={(e) => setTargetEntity(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="Todas las entidades">Todas las entidades (Global)</option>
              {entities.map((e: any) => {
                const eName = typeof e === 'string' ? e : e?.name || 'Order';
                const eTable = typeof e === 'object' && e?.tableName ? e.tableName : `${eName.toLowerCase()}s`;
                return (
                  <option key={eName} value={eName}>
                    {eName} (Tabla: {eTable})
                  </option>
                );
              })}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Instrucción Semántica de Refinamiento
            </label>
            <textarea
              rows={5}
              value={refinePrompt}
              onChange={(e) => setRefinePrompt(e.target.value)}
              placeholder="Ejemplo: Añade un campo trackingNumber de tipo String con restricción de unicidad en la entidad Order y regenera el DDL..."
              className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-xs leading-relaxed focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={() => setIsRefining(false)}
              className="px-4 py-2 text-xs font-medium rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Cancelar
            </button>
            <button
              onClick={handleRefineSubmit}
              disabled={!refinePrompt.trim()}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg text-white bg-blue-600 hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Refinar Modelos & SQL</span>
            </button>
          </div>
        </div>
      </SlideOverDrawer>
    </div>
  );
};
