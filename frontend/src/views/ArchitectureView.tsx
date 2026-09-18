import React, { useState } from 'react';
import {
  Layers,
  Sparkles,
  Send,
  CheckCircle2,
  Download,
  Database,
  ArrowRight,
  Code2,
  ChevronDown,
  ChevronUp,
  Boxes,
  Globe,
  Server,
  Workflow,
  AlertTriangle,
} from 'lucide-react';
import { SingleRowCard } from '../components/common/SingleRowCard';
import { MermaidViewer } from '../components/common/MermaidViewer';
import { SlideOverDrawer } from '../components/common/SlideOverDrawer';
import { useStudio } from '../context/StudioContext';
import { useLlm } from '../context/LlmContext';
import { architectureService } from '../services/architectureService';
import { modelsService } from '../services/modelsService';
import { specService } from '../services/specService';
import { orchestratorService } from '../services/orchestratorService';

const DEFAULT_MERMAID = `flowchart TD
  subgraph Layer1["Capa 1: Controllers (REST / HTTP)"]
    OrderController["OrderController\\n@RestController /api/v1/orders"]
  end

  subgraph Layer2["Capa 2: Services (Lógica de Negocio)"]
    OrderService["OrderService\\n@Service @Transactional"]
  end

  subgraph Layer3["Capa 3: Repositories (Spring Data JPA)"]
    OrderRepository["OrderRepository\\nJpaRepository<Order, Long>"]
  end

  subgraph Layer4["Capa 4: Models & SQL (PostgreSQL)"]
    OrderEntity["Order Entity\\n@Table(name='orders')"]
  end

  subgraph Layer5["Capa 5: Infraestructura Transversal"]
    GlobalExceptionHandler["GlobalExceptionHandler\\n@RestControllerAdvice"]
  end

  OrderController --> OrderService
  OrderService --> OrderRepository
  OrderRepository --> OrderEntity
  OrderController -.-> GlobalExceptionHandler
`;

export const ArchitectureView: React.FC = () => {
  const {
    activeSessionId,
    activeSession,
    currentDraft,
    architectureDesign,
    setArchitectureDesign,
    setDataModelDesign,
    setCurrentSpecId,
    setParsedSpec,
    reloadCurrentOverview,
    setActiveTab,
  } = useStudio();
  const { provider, apiKey } = useLlm();

  // Active design or fallback
  const [design, setDesign] = useState<any>(
    architectureDesign || {
      serviceName: activeSession?.specName || currentDraft?.serviceName || 'order-service',
      packageName: currentDraft?.packageName || 'com.tcs.microservice',
      basePort: 8080,
      mermaidDiagram: DEFAULT_MERMAID,
      architectureMarkdown: `# Arquitectura del Microservicio: ${activeSession?.specName || 'order-service'}\n\nTopología en 4 capas estrictas conforme a la Constitución de Desarrollo Autónomo.`,
      openapiYaml: `openapi: 3.0.3\ninfo:\n  title: ${activeSession?.specName || 'order-service'} API\n  version: 1.0.0\npaths:\n  /api/v1/orders:\n    post:\n      summary: Crear orden de compra\n    get:\n      summary: Listar órdenes`,
      components: [
        {
          name: 'OrderController',
          layer: 'controller',
          stereotype: '@RestController',
          packageName: 'com.tcs.microservice.controller',
          responsibilities: [
            'Exponer endpoints REST para creación y consulta de órdenes',
            'Validar contratos inmutables de entrada (Java Records)',
          ],
          dependencies: ['OrderService'],
          mappedStories: ['US-001'],
        },
        {
          name: 'OrderService',
          layer: 'service',
          stereotype: '@Service',
          packageName: 'com.tcs.microservice.service',
          responsibilities: [
            'Coordinar la transacción de negocio con aislamiento @Transactional',
            'Mapear DTOs a entidades de dominio JPA',
          ],
          dependencies: ['OrderRepository'],
          mappedStories: ['US-001', 'US-002'],
        },
        {
          name: 'OrderRepository',
          layer: 'repository',
          stereotype: '@Repository',
          packageName: 'com.tcs.microservice.repository',
          responsibilities: [
            'Interfaz Spring Data JPA para persistencia en base de datos relacional',
            'Consultas derivadas por nombre de método herméticas',
          ],
          dependencies: ['Order'],
          mappedStories: ['US-001'],
        },
        {
          name: 'Order',
          layer: 'model',
          stereotype: '@Entity',
          packageName: 'com.tcs.microservice.model',
          responsibilities: [
            'Entidad de dominio con clave primaria autonumérica e inmutabilidad',
            'Auditoría temporal normalizada con Instant createdAt y updatedAt',
          ],
          dependencies: [],
          mappedStories: ['US-001'],
        },
        {
          name: 'GlobalExceptionHandler',
          layer: 'infrastructure',
          stereotype: '@RestControllerAdvice',
          packageName: 'com.tcs.microservice.infrastructure',
          responsibilities: [
            'Captura centralizada de excepciones de negocio y de validación Bean',
            'Mapeo uniforme a ProblemDetails RFC 7807',
          ],
          dependencies: [],
          mappedStories: ['US-001'],
        },
      ],
      endpoints: [
        {
          method: 'POST',
          path: '/api/v1/orders',
          summary: 'Crear nueva orden de compra con validación de stock',
          requestDto: 'CreateOrderRequest',
          responseDto: 'OrderResponse',
          successStatus: 201,
          errorStatuses: [400, 422, 500],
          mappedScenarioId: 'AC-US-001.1',
        },
        {
          method: 'GET',
          path: '/api/v1/orders/{id}',
          summary: 'Consultar estado detallado de una orden',
          requestDto: null,
          responseDto: 'OrderDetailResponse',
          successStatus: 200,
          errorStatuses: [404, 500],
          mappedScenarioId: 'AC-US-001.2',
        },
      ],
    }
  );

  const [isGenerating, setIsGenerating] = useState(false);
  const [isRefining, setIsRefining] = useState(false);
  const [refinePrompt, setRefinePrompt] = useState('');
  const [targetComponent, setTargetComponent] = useState('GLOBAL');
  const [feedback, setFeedback] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [expandedLayers, setExpandedLayers] = useState<Record<string, boolean>>({
    controller: true,
    service: true,
    repository: true,
    model: true,
    infrastructure: true,
  });
  const [showMermaidSource, setShowMermaidSource] = useState(false);

  // Sync state if context updates
  const updateDesign = (newDesign: any) => {
    setDesign(newDesign);
    setArchitectureDesign(newDesign);
  };

  const handleGenerateAi = async () => {
    setIsGenerating(true);
    setErrorMsg(null);
    try {
      const draftPayload = currentDraft || {
        serviceName: activeSession?.specName || 'order-service',
        packageName: 'com.tcs.microservice',
        basePort: 8080,
        entities: [{ name: 'Order', tableName: 'orders', attributes: [{ name: 'id', type: 'Long', isPrimaryKey: true }] }],
        userStories: [],
      };
      const res = await architectureService.design({
        draft: draftPayload,
        apiKey,
        provider,
      });
      updateDesign(res);
      setFeedback('Diseño arquitectónico y componentes sintetizados exitosamente.');
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Error al sintetizar arquitectura con IA');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRefineSubmit = async () => {
    if (!refinePrompt.trim()) return;
    setIsRefining(true);
    setErrorMsg(null);
    try {
      const res = await architectureService.refine({
        currentDesign: design,
        feedbackPrompt: refinePrompt.trim(),
        targetComponent: targetComponent === 'GLOBAL' ? undefined : targetComponent,
        apiKey,
        provider,
      });
      updateDesign(res);
      setIsRefining(false);
      setRefinePrompt('');
      setFeedback('Ajustes arquitectónicos aplicados exitosamente.');
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Error refinando arquitectura');
    } finally {
      setIsRefining(false);
    }
  };

  const handleDownloadOpenApi = () => {
    const yaml = design.openapiYaml || 'openapi: 3.0.3';
    const blob = new Blob([yaml], { type: 'application/x-yaml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `openapi-${design.serviceName || 'service'}.yaml`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const handleDownloadArchitectureMd = () => {
    const md = design.architectureMarkdown || `# Arquitectura: ${design.serviceName}`;
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `architecture-${design.serviceName || 'service'}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const handleGotoModelsSql = async () => {
    setIsGenerating(true);
    setErrorMsg(null);
    try {
      const draftPayload = currentDraft || {
        serviceName: design.serviceName,
        packageName: design.packageName,
        basePort: design.basePort || 8080,
        entities: design.entities || [],
        userStories: design.userStories || [],
      };
      const res = await modelsService.generate({
        draft: draftPayload,
        apiKey,
        provider,
      });
      setDataModelDesign(res);
      if (activeSessionId) {
        await orchestratorService.invalidateDownstream(activeSessionId, 'ARCHITECTURE');
        await reloadCurrentOverview();
      }
      setActiveTab(3); // Go to tab 3 (Modelos & SQL)
    } catch (err: any) {
      // Fallback transition
      setActiveTab(3);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleTransferDirectToGeneration = async () => {
    setIsGenerating(true);
    setErrorMsg(null);
    try {
      const blueprintPayload = {
        serviceName: design.serviceName,
        packageName: design.packageName,
        basePort: design.basePort || 8080,
        entities: design.entities || [],
        userStories: design.userStories || [],
      };
      const res = await specService.submitJson(blueprintPayload);
      if (res?.specId) {
        setCurrentSpecId(res.specId);
        setParsedSpec(res);
      }
      setActiveTab(5); // Go to tab 5 (Generación & Logs)
    } catch (err: any) {
      setActiveTab(5);
    } finally {
      setIsGenerating(false);
    }
  };

  const layersConfig: Record<string, { label: string; icon: any; color: string }> = {
    controller: { label: 'Capa Controlador (REST / HTTP)', icon: Globe, color: 'text-blue-600 dark:text-blue-400' },
    service: { label: 'Capa Servicio (Lógica de Negocio)', icon: Workflow, color: 'text-emerald-600 dark:text-emerald-400' },
    repository: { label: 'Capa Repositorio (Persistencia Spring Data JPA)', icon: Database, color: 'text-purple-600 dark:text-purple-400' },
    model: { label: 'Capa Dominio & Modelos', icon: Boxes, color: 'text-amber-600 dark:text-amber-400' },
    infrastructure: { label: 'Componentes Transversales & Infraestructura', icon: Server, color: 'text-rose-600 dark:text-rose-400' },
  };

  const components = design.components || [];

  return (
    <div className="space-y-6">
      {/* Top Banner Card */}
      <SingleRowCard
        title="Fase 2: Diseño Arquitectónico & Catálogo de Componentes"
        subtitle="Topología en 4 capas estrictas (Controller ➔ Service ➔ Repository ➔ Model) con Java Records y @RestControllerAdvice"
        badge={
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300">
            Spring Boot 3.x / Java 21
          </span>
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleGenerateAi}
              disabled={isGenerating}
              className="py-2 px-3.5 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-all shadow-sm flex items-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{isGenerating ? 'Sintetizando...' : 'Generar / Regenerar con IA'}</span>
            </button>
            <button
              onClick={() => setIsRefining(true)}
              className="py-2 px-3.5 rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/60 transition-colors"
            >
              Refinar con IA
            </button>
            <button
              onClick={handleGotoModelsSql}
              disabled={isGenerating}
              className="py-2 px-4 rounded-lg text-xs font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 hover:bg-emerald-100 transition-colors flex items-center gap-1.5"
            >
              <span>Diseñar Modelos & SQL →</span>
            </button>
          </div>
        }
      >
        <p className="text-xs text-slate-600 dark:text-slate-400">
          Inspeccione y ajuste la arquitectura modular libre de dependencias cíclicas, contratos inmutables de endpoints REST derivados de BDD y compuertas de manejo de errores centralizado conforme a los Principios I, II y III de la Constitución.
        </p>

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

      {/* 1. Mermaid Architecture Flowchart */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
            <Workflow className="w-4 h-4 text-blue-600" />
            <span>1. Diagrama Direccional de Capas y Componentes (Mermaid)</span>
          </h3>
          <button
            onClick={() => setShowMermaidSource(!showMermaidSource)}
            className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline"
          >
            {showMermaidSource ? 'Ocultar código fuente' : 'Ver código Mermaid'}
          </button>
        </div>

        <MermaidViewer
          chart={design.mermaidDiagram || DEFAULT_MERMAID}
          title="Topología Arquitectónica en 4 Capas"
        />

        {showMermaidSource && (
          <pre className="p-3 bg-slate-950 text-emerald-400 rounded-xl font-mono text-xs overflow-x-auto border border-slate-800">
            {design.mermaidDiagram || DEFAULT_MERMAID}
          </pre>
        )}
      </div>

      {/* 2. Hierarchical Component Catalog by Layer */}
      <div className="space-y-4">
        <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
          <Layers className="w-4 h-4 text-indigo-600" />
          <span>2. Catálogo Jerárquico de Componentes ({components.length})</span>
        </h3>

        <div className="space-y-3">
          {Object.entries(layersConfig).map(([layerKey, config]) => {
            const layerComps = components.filter((c: any) => c.layer === layerKey);
            const isExpanded = !!expandedLayers[layerKey];
            const Icon = config.icon;

            return (
              <div
                key={layerKey}
                className="border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-900 overflow-hidden shadow-sm"
              >
                <button
                  type="button"
                  onClick={() =>
                    setExpandedLayers((prev) => ({ ...prev, [layerKey]: !prev[layerKey] }))
                  }
                  className="w-full flex items-center justify-between p-3.5 bg-slate-50 dark:bg-slate-900/80 hover:bg-slate-100 dark:hover:bg-slate-800/60 transition-colors text-left"
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className={`w-4 h-4 ${config.color}`} />
                    <span className="font-semibold text-xs text-slate-900 dark:text-white">
                      {config.label}
                    </span>
                    <span className="px-2 py-0.5 rounded-full text-[11px] font-mono font-bold bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                      {layerComps.length}
                    </span>
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-slate-500" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-500" />
                  )}
                </button>

                {isExpanded && (
                  <div className="p-4 divide-y divide-slate-100 dark:divide-slate-800 space-y-4">
                    {layerComps.length === 0 ? (
                      <div className="text-xs text-slate-400 italic py-2">
                        No hay componentes registrados en esta capa.
                      </div>
                    ) : (
                      layerComps.map((comp: any, cIdx: number) => (
                        <div key={cIdx} className={cIdx > 0 ? 'pt-4' : ''}>
                          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-bold text-xs text-blue-600 dark:text-blue-400">
                                {comp.name}
                              </span>
                              <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300">
                                {comp.stereotype}
                              </span>
                            </div>
                            <span className="font-mono text-[11px] text-slate-500">
                              {comp.packageName}
                            </span>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs bg-slate-50 dark:bg-slate-950/50 p-3 rounded-lg border border-slate-100 dark:border-slate-800/80">
                            <div>
                              <strong className="text-slate-700 dark:text-slate-300 block mb-1">
                                Responsabilidades:
                              </strong>
                              <ul className="list-disc list-inside space-y-0.5 text-slate-600 dark:text-slate-400">
                                {(comp.responsibilities || []).map((resp: string, rIdx: number) => (
                                  <li key={rIdx}>{resp}</li>
                                ))}
                              </ul>
                            </div>

                            <div className="space-y-2">
                              <div>
                                <strong className="text-slate-700 dark:text-slate-300 block mb-0.5">
                                  Dependencias de salida:
                                </strong>
                                <span className="font-mono text-[11px] text-slate-600 dark:text-slate-400">
                                  {(comp.dependencies || []).join(', ') || 'Ninguna (Hermético)'}
                                </span>
                              </div>

                              <div>
                                <strong className="text-slate-700 dark:text-slate-300 block mb-0.5">
                                  Historias BDD Mapeadas:
                                </strong>
                                <span className="font-mono text-[11px] text-indigo-600 dark:text-indigo-400 font-semibold">
                                  {(comp.mappedStories || []).join(', ') || 'Transversal'}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. REST Endpoint Catalog & DTO Contracts */}
      <div className="space-y-3">
        <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
          <Globe className="w-4 h-4 text-blue-600" />
          <span>3. Catálogo de Endpoints REST & Contratos DTO ({design.endpoints?.length || 0})</span>
        </h3>

        <div className="space-y-2.5">
          {(design.endpoints || []).map((ep: any, idx: number) => {
            const method = ep.method || 'GET';
            const badgeColor =
              method === 'GET'
                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                : method === 'POST'
                ? 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300'
                : method === 'DELETE'
                ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300';

            return (
              <div
                key={idx}
                className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-xs space-y-2.5 shadow-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2 font-mono">
                    <span className={`px-2 py-0.5 rounded font-bold text-[11px] ${badgeColor}`}>
                      {method}
                    </span>
                    <span className="font-bold text-slate-900 dark:text-white text-xs">
                      {ep.path}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 font-mono text-[11px]">
                    <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                      HTTP {ep.successStatus || 200}
                    </span>
                    {ep.errorStatuses && (
                      <span className="text-slate-400">
                        Errors: [{ep.errorStatuses.join(', ')}]
                      </span>
                    )}
                  </div>
                </div>

                <p className="text-slate-600 dark:text-slate-400">{ep.summary}</p>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 bg-slate-50 dark:bg-slate-950 p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 font-mono text-[11px]">
                  <div>
                    <strong className="text-slate-500 block">Request DTO:</strong>
                    <span className="text-indigo-600 dark:text-indigo-400 font-semibold">
                      {ep.requestDto || '—'}
                    </span>
                  </div>
                  <div>
                    <strong className="text-slate-500 block">Response DTO:</strong>
                    <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                      {ep.responseDto || '—'}
                    </span>
                  </div>
                  <div>
                    <strong className="text-slate-500 block">Criterio BDD:</strong>
                    <span className="text-slate-700 dark:text-slate-300 font-semibold">
                      {ep.mappedScenarioId || '—'}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 4. Export Artifacts and Pipeline Handoff */}
      <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4 shadow-sm">
        <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
          <Download className="w-4 h-4 text-blue-600" />
          <span>4. Exportación de Documentación y Transferencia al Pipeline</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <button
            onClick={handleDownloadOpenApi}
            className="flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-xs font-semibold text-slate-800 dark:text-slate-200 transition-colors shadow-sm"
          >
            <Download className="w-3.5 h-3.5 text-blue-600" />
            <span>Descargar openapi.yaml (Swagger / OpenAPI 3.0)</span>
          </button>

          <button
            onClick={handleDownloadArchitectureMd}
            className="flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-xs font-semibold text-slate-800 dark:text-slate-200 transition-colors shadow-sm"
          >
            <Download className="w-3.5 h-3.5 text-emerald-600" />
            <span>Descargar architecture.md (Markdown)</span>
          </button>
        </div>

        <div className="pt-2 border-t border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3">
          <button
            onClick={handleTransferDirectToGeneration}
            disabled={isGenerating}
            className="w-full sm:w-auto flex items-center justify-center gap-2 py-2 px-4 rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
          >
            <span>➡️ Transferir Directo a Generación</span>
          </button>

          <button
            onClick={handleGotoModelsSql}
            disabled={isGenerating}
            className="w-full sm:w-auto flex items-center justify-center gap-2 py-2.5 px-6 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 shadow-md transition-all"
          >
            <Database className="w-3.5 h-3.5" />
            <span>💾 Diseñar Modelos & SQL (Recomendado) →</span>
          </button>
        </div>
      </div>

      {/* SlideOverDrawer for Architecture Refinement */}
      <SlideOverDrawer
        isOpen={isRefining}
        onClose={() => setIsRefining(false)}
        title="Asistente de Refinamiento Arquitectónico con IA"
        subtitle="Agregue capas, reasigne dependencias o extraiga nuevos componentes de servicio"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Componente Objetivo
            </label>
            <select
              value={targetComponent}
              onChange={(e) => setTargetComponent(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="GLOBAL">Ajuste Global (Toda la Arquitectura)</option>
              {components.map((c: any) => (
                <option key={c.name} value={c.name}>
                  {c.name} ({c.stereotype})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Instrucción Semántica de Ajuste
            </label>
            <textarea
              rows={5}
              value={refinePrompt}
              onChange={(e) => setRefinePrompt(e.target.value)}
              placeholder="Ejemplo: Añade un componente de servicio AuditLogService para registrar eventos en la capa de servicio y conectar con OrderService..."
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
              <span>Aplicar Ajustes</span>
            </button>
          </div>
        </div>
      </SlideOverDrawer>
    </div>
  );
};
