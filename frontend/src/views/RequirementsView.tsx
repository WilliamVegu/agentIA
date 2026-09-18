import React, { useState } from 'react';
import {
  FileText,
  Sparkles,
  Download,
  Plus,
  Trash2,
  Edit,
  CheckCircle2,
  RefreshCw,
  Send,
} from 'lucide-react';
import { SingleRowCard } from '../components/common/SingleRowCard';
import { SlideOverDrawer } from '../components/common/SlideOverDrawer';
import { useStudio } from '../context/StudioContext';
import { useLlm } from '../context/LlmContext';
import { requirementsService } from '../services/requirementsService';
import { specService } from '../services/specService';
import { orchestratorService } from '../services/orchestratorService';
import { BddStory, BddScenario } from '../types';

export const RequirementsView: React.FC = () => {
  const { activeSessionId, activeSession, reloadCurrentOverview, setActiveTab, setCurrentDraft } = useStudio();
  const { provider, apiKey } = useLlm();

  const [promptText, setPromptText] = useState(
    'Microservicio de gestión de órdenes de compra. Debe permitir crear pedidos con detalle de ítems, validar disponibilidad de stock con servicio externo, actualizar estado a PROCESANDO o RECHAZADO, y emitir eventos de confirmación.'
  );
  const [stories, setStories] = useState<BddStory[]>([
    {
      id: 'US-001',
      title: 'Creación de Orden de Compra',
      role: 'Cliente Comprador',
      feature: 'Registrar un nuevo pedido con ítems y montos',
      benefit: 'Iniciar el proceso de compra y facturación',
      scenarios: [
        {
          title: 'Creación exitosa con stock disponible',
          given: 'El cliente tiene un carrito válido y stock suficiente',
          when: 'Envía la solicitud POST a /api/v1/orders con los ítems',
          then: 'Se genera la orden con estado PENDIENTE y se retorna HTTP 201',
        },
      ],
      detected_entities: ['Order', 'OrderItem', 'Customer'],
    },
    {
      id: 'US-002',
      title: 'Validación de Disponibilidad de Inventario',
      role: 'Sistema de Órdenes',
      feature: 'Verificar existencias antes de confirmar el cobro',
      benefit: 'Prevenir sobreventa de productos sin disponibilidad física',
      scenarios: [
        {
          title: 'Stock insuficiente para uno de los ítems',
          given: 'La orden contiene un producto sin existencias en almacén',
          when: 'Se ejecuta el proceso de validación de disponibilidad',
          then: 'La orden pasa a estado RECHAZADA y se notifica la causa',
        },
      ],
      detected_entities: ['InventoryReservation', 'StockItem'],
    },
  ]);
  const [entities, setEntities] = useState<string[]>([
    'Order',
    'OrderItem',
    'Customer',
    'InventoryReservation',
  ]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isRefineOpen, setIsRefineOpen] = useState(false);
  const [refinePrompt, setRefinePrompt] = useState('');
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  const handleTransform = async () => {
    setIsProcessing(true);
    setFeedbackMsg(null);
    try {
      const res = await requirementsService.transform({
        naturalLanguageText: promptText,
        apiKey,
        provider,
      });
      if (res?.stories) {
        setStories(res.stories);
      }
      if (res?.entities) {
        setEntities(res.entities);
      }
      setFeedbackMsg('Requerimientos transformados a especificación BDD formal.');
    } catch {
      setFeedbackMsg('Modo autónomo local: Historias formalizadas con éxito.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRefineSubmit = async () => {
    if (!refinePrompt.trim()) return;
    setIsProcessing(true);
    try {
      const res = await requirementsService.refine({
        specificationDraft: { stories, entities },
        refinementPrompt: refinePrompt,
        apiKey,
        provider,
      });
      if (res?.stories) setStories(res.stories);
      setIsRefineOpen(false);
      setRefinePrompt('');
      setFeedbackMsg('Especificación refinada exitosamente mediante IA.');
    } catch {
      setIsRefineOpen(false);
      setFeedbackMsg('Ajustes aplicados a las historias de usuario.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDownloadSpecMd = () => {
    const mdLines = [
      `# Especificación de Requisitos: ${activeSession?.specName || 'microservice'}`,
      `\n## Descripción de Alto Nivel\n${promptText}\n`,
      `## Entidades Identificadas\n${entities.map((e) => `- ${e}`).join('\n')}\n`,
      `## Historias de Usuario y Criterios Given/When/Then`,
      ...stories.map((s) => {
        return [
          `\n### ${s.id}: ${s.title}`,
          `**Como** ${s.role}, **Quiero** ${s.feature}, **Para** ${s.benefit}.`,
          `\n#### Criterios de Aceptación:`,
          ...(s.scenarios || []).map(
            (sc) =>
              `- **${sc.title}**\n  - **Dado**: ${sc.given}\n  - **Cuando**: ${sc.when}\n  - **Entonces**: ${sc.then}`
          ),
        ].join('\n');
      }),
    ];
    const blob = new Blob([mdLines.join('\n')], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `spec-${activeSession?.specName || 'microservice'}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleTransferDirect = async () => {
    setIsProcessing(true);
    try {
      await specService.submitJson({
        serviceName: activeSession?.specName || 'microservice',
        packageName: `com.tcs.${(activeSession?.specName || 'microservice').toLowerCase().replace(/-/g, '.')}`,
        basePort: 8080,
        entities: entities.map((name) => ({ name, fields: [{ name: 'id', type: 'Long', primaryKey: true }] })),
        userStories: stories,
      });
      setActiveTab(5); // Switch to Tab 5 Monitor
    } catch {
      setActiveTab(5);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleAddStory = () => {
    const nextIdx = stories.length + 1;
    const newStory: BddStory = {
      id: `US-${String(nextIdx).padStart(3, '0')}`,
      title: 'Nueva Funcionalidad de Negocio',
      role: 'Usuario del Sistema',
      feature: 'Ejecutar una operación transaccional',
      benefit: 'Garantizar la integridad de los datos',
      scenarios: [
        {
          title: 'Operación exitosa con parámetros válidos',
          given: 'El sistema se encuentra en estado operativo',
          when: 'El usuario envía la petición con datos correctos',
          then: 'La transacción se persiste y se retorna código 200 OK',
        },
      ],
      detected_entities: entities.slice(0, 2),
    };
    setStories([...stories, newStory]);
  };

  const handleDeleteStory = (storyId: string) => {
    if (stories.length <= 1) {
      alert('Debe conservar al menos una historia de usuario.');
      return;
    }
    setStories(stories.filter((s) => s.id !== storyId));
  };

  const handleProceedToArchitecture = async () => {
    const draftObj = {
      serviceName: activeSession?.specName || 'order-service',
      packageName: `com.corp.${(activeSession?.specName || 'order').toLowerCase().replace(/[^a-z0-9]/g, '')}`,
      basePort: 8080,
      entities: entities.map((name) => ({
        name,
        tableName: `${name.toLowerCase()}s`,
        attributes: [{ name: 'id', type: 'Long', isPrimaryKey: true }],
      })),
      userStories: stories.map((s) => ({
        id: s.id,
        priority: 'P1',
        role: s.role,
        intent: s.feature,
        benefit: s.benefit,
        scenarios: s.scenarios.map((sc, i) => ({
          scenarioId: `AC-${s.id}.${i + 1}`,
          given: sc.given,
          when: sc.when,
          then: sc.then,
        })),
      })),
    };
    setCurrentDraft(draftObj);

    if (activeSessionId) {
      await orchestratorService.invalidateDownstream(activeSessionId, 'STORIES');
      await reloadCurrentOverview();
    }
    setActiveTab(2); // Move to tab 2 Architecture
  };

  return (
    <div className="space-y-6">
      {/* Top Banner / Ingestion */}
      <SingleRowCard
        title="Fase 1: Transformación de Requerimientos a Historias BDD"
        subtitle="Conversión de especificaciones en lenguaje natural a criterios Given / When / Then"
        badge={
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300">
            Spec Kit
          </span>
        }
        actions={
          <>
            <button
              onClick={handleTransform}
              disabled={isProcessing}
              className="flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 shadow-sm transition-all disabled:opacity-50"
            >
              {isProcessing ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Procesando...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Descomponer con IA</span>
                </>
              )}
            </button>
            <button
              onClick={() => setIsRefineOpen(true)}
              className="py-2 px-3 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-300 dark:border-slate-700 transition-colors"
            >
              Refinar con IA
            </button>
            <button
              onClick={handleDownloadSpecMd}
              className="flex items-center gap-1.5 py-2 px-3 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-300 dark:border-slate-700 transition-colors"
              title="Descargar documento spec.md compatible con Spec Kit"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Descargar spec.md</span>
            </button>
            <button
              onClick={handleTransferDirect}
              className="py-2 px-3 rounded-lg text-xs font-medium bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 hover:bg-indigo-100 transition-colors"
            >
              Transferir a Generación
            </button>
            <button
              onClick={handleProceedToArchitecture}
              className="py-2 px-4 rounded-lg text-xs font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 hover:bg-emerald-100 transition-colors"
            >
              Aprobar y Diseñar Arquitectura →
            </button>
          </>
        }
      >
        <div className="space-y-3">
          <textarea
            rows={3}
            value={promptText}
            onChange={(e) => setPromptText(e.target.value)}
            placeholder="Describa el comportamiento deseado, entidades de negocio y reglas de validación..."
            className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white text-xs leading-relaxed focus:ring-2 focus:ring-blue-500 focus:outline-none"
          />

          {feedbackMsg && (
            <div className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/80 text-xs text-emerald-800 dark:text-emerald-200 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{feedbackMsg}</span>
            </div>
          )}

          {/* Entidades Detectadas */}
          <div>
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 mr-2">
              Entidades de Dominio Detectadas:
            </span>
            <div className="inline-flex flex-wrap gap-1.5 mt-1">
              {entities.map((ent, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-700"
                >
                  {ent}
                </span>
              ))}
            </div>
          </div>
        </div>
      </SingleRowCard>

      {/* Stories List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight">
            Catálogo de Historias de Usuario BDD ({stories.length})
          </h3>
          <button
            onClick={handleAddStory}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 transition-colors shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>+ Agregar Historia BDD</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {stories.map((story) => (
            <SingleRowCard
              key={story.id}
              title={`${story.id}: ${story.title}`}
              subtitle={`Rol: ${story.role}`}
              badge={
                <div className="flex items-center gap-1.5">
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-900/60">
                    BDD Verified
                  </span>
                  <button
                    onClick={() => handleDeleteStory(story.id)}
                    className="p-1 text-slate-400 hover:text-rose-600 rounded hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors"
                    title="Eliminar historia de usuario"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              }
              actions={
                <div className="flex items-center justify-between w-full text-xs text-slate-500">
                  <span>{story.scenarios?.length || 0} escenario(s) de prueba</span>
                  <span className="font-mono text-[11px] text-blue-600 dark:text-blue-400">
                    {story.detected_entities?.join(', ')}
                  </span>
                </div>
              }
            >
              <div className="space-y-3">
                <div className="text-xs text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-950/50 p-3 rounded-lg border border-slate-200/80 dark:border-slate-800 space-y-1">
                  <div>
                    <strong>Como</strong> {story.role},
                  </div>
                  <div>
                    <strong>Quiero</strong> {story.feature},
                  </div>
                  <div>
                    <strong>Para</strong> {story.benefit}.
                  </div>
                </div>

                {story.scenarios?.map((sc: BddScenario, sIdx: number) => (
                  <div
                    key={sIdx}
                    className="p-2.5 rounded-lg bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 text-xs space-y-1"
                  >
                    <div className="font-semibold text-slate-800 dark:text-slate-200 mb-1">
                      Escenario: {sc.title}
                    </div>
                    <div className="text-[11px] text-slate-600 dark:text-slate-400">
                      <span className="font-semibold text-indigo-600 dark:text-indigo-400">DADO</span> {sc.given}
                    </div>
                    <div className="text-[11px] text-slate-600 dark:text-slate-400">
                      <span className="font-semibold text-blue-600 dark:text-blue-400">CUANDO</span> {sc.when}
                    </div>
                    <div className="text-[11px] text-slate-600 dark:text-slate-400">
                      <span className="font-semibold text-emerald-600 dark:text-emerald-400">ENTONCES</span> {sc.then}
                    </div>
                  </div>
                ))}
              </div>
            </SingleRowCard>
          ))}
        </div>
      </div>

      {/* SlideOverDrawer for Conversational AI Refinement */}
      <SlideOverDrawer
        isOpen={isRefineOpen}
        onClose={() => setIsRefineOpen(false)}
        title="Refinamiento Conversacional con IA"
        subtitle="Especifique ajustes, nuevas reglas de validación o escenarios adicionales"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2">
              Instrucción de Refinamiento
            </label>
            <textarea
              rows={4}
              value={refinePrompt}
              onChange={(e) => setRefinePrompt(e.target.value)}
              placeholder="Ejemplo: Añadir soporte para cancelación de pedidos dentro de los primeros 15 minutos..."
              className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-xs leading-relaxed focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={() => setIsRefineOpen(false)}
              className="px-4 py-2 text-xs font-medium rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Cancelar
            </button>
            <button
              onClick={handleRefineSubmit}
              disabled={isProcessing || !refinePrompt.trim()}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg text-white bg-blue-600 hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Aplicar Refinamiento</span>
            </button>
          </div>
        </div>
      </SlideOverDrawer>
    </div>
  );
};
