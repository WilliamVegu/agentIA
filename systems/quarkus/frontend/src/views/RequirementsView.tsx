import React, { useState, useEffect } from 'react';
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
  AlertCircle,
} from 'lucide-react';
import { SingleRowCard } from '../components/common/SingleRowCard';
import { SlideOverDrawer } from '../components/common/SlideOverDrawer';
import { useStudio } from '../context/StudioContext';
import { useLlm } from '../context/LlmContext';
import { requirementsService } from '../services/requirementsService';
import { specService } from '../services/specService';
import { orchestratorService } from '../services/orchestratorService';
import apiClient from '../services/apiClient';
import { BddStory, BddScenario } from '../types';

interface EntityItem {
  name: string;
  tableName?: string;
  attributes?: any[];
}

const getEntityName = (ent: string | EntityItem | any): string => {
  if (!ent) return '';
  if (typeof ent === 'string') return ent;
  return ent.name || ent.tableName || String(ent);
};

const getEntityTableName = (ent: string | EntityItem | any): string | null => {
  if (!ent || typeof ent === 'string') return null;
  return ent.tableName || null;
};

const normalizeEntitiesForDraft = (rawEntities: (string | EntityItem | any)[], defaultServiceName?: string) => {
  const fallback = defaultServiceName
    ? defaultServiceName.replace(/[^a-zA-Z0-9]/g, '').replace(/^[0-9]+/, '') || 'Resource'
    : 'Resource';
  const list = rawEntities.length > 0 ? rawEntities : [fallback];
  return list.map((e) => {
    const name = getEntityName(e) || fallback;
    const tableName = (typeof e === 'object' && e?.tableName)
      ? e.tableName
      : `${name.toLowerCase()}s`;
    const attributes = (typeof e === 'object' && Array.isArray(e?.attributes) && e.attributes.length > 0)
      ? e.attributes
      : [
          {
            name: 'id',
            type: 'Long',
            nullable: false,
            isPrimaryKey: true,
            validationRules: [],
          },
        ];
    return { name, tableName, attributes };
  });
};

const mapIncomingStories = (rawStories: any[], fallbackEntities: (string | EntityItem | any)[]): BddStory[] => {
  if (!Array.isArray(rawStories)) return [];
  const entityNames = fallbackEntities.map(getEntityName).filter(Boolean);

  return rawStories.map((s: any, idx: number) => ({
    id: s.id || `US-${String(idx + 1).padStart(3, '0')}`,
    title: s.title || s.intent || s.feature || `Historia de Usuario ${idx + 1}`,
    role: s.role || 'Usuario',
    feature: s.feature || s.intent || 'Operación transaccional',
    benefit: s.benefit || 'Completar flujo de negocio',
    scenarios: (s.scenarios || []).map((sc: any, scIdx: number) => ({
      title: sc.title || sc.scenarioId || `Escenario ${scIdx + 1}`,
      given: sc.given || 'El microservicio está en ejecución',
      when: sc.when || 'Se recibe la solicitud con parámetros válidos',
      then: sc.then || 'Se procesa la transacción exitosamente',
    })),
    detected_entities: Array.isArray(s.detected_entities || s.detectedEntities)
      ? (s.detected_entities || s.detectedEntities).map((e: any) => getEntityName(e)).filter(Boolean)
      : entityNames.slice(0, 2),
  }));
};

export const RequirementsView: React.FC = () => {
  const {
    activeSessionId,
    activeSession,
    reloadCurrentOverview,
    setActiveTab,
    currentDraft,
    setCurrentDraft,
    setCurrentSpecId,
    setParsedSpec,
    refreshSessions,
    selectSession,
  } = useStudio();
  const { provider, apiKey, setProvider } = useLlm();

  const [revisionId, setRevisionId] = useState<string | null>(null);
  const [configurationVersion, setConfigurationVersion] = useState<number | undefined>();
  const [backupConfirmed, setBackupConfirmed] = useState(false);
  const [promptText, setPromptText] = useState('');
  const [stories, setStories] = useState<BddStory[]>([]);
  const [entities, setEntities] = useState<(string | EntityItem)[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isRefineOpen, setIsRefineOpen] = useState(false);
  const [refinePrompt, setRefinePrompt] = useState('');
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Manual Story Modal / Drawer State
  const [isStoryModalOpen, setIsStoryModalOpen] = useState(false);
  const [editingStoryId, setEditingStoryId] = useState<string | null>(null);
  const [storyForm, setStoryForm] = useState<BddStory>({
    id: 'US-001',
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
    detected_entities: [],
  });

  useEffect(() => {
    if (!activeSessionId) {
      setRevisionId(null);
      setConfigurationVersion(undefined);
      setBackupConfirmed(false);
      setPromptText('');
      setStories([]);
      setEntities([]);
      return;
    }

    let isMounted = true;
    requirementsService
      .getSessionRequirements(activeSessionId)
      .then((data) => {
        if (!isMounted || !data) return;
        setRevisionId(data.revisionId ?? null);
        setConfigurationVersion(data.configurationVersion);
        setBackupConfirmed(false);
        if (data.rawPrompt && data.rawPrompt.trim()) {
          setPromptText(data.rawPrompt);
        } else {
          setPromptText('');
        }
        if (data.hasDraft && data.draft) {
          setCurrentDraft(data.draft);
          if (data.draft.entities && Array.isArray(data.draft.entities)) {
            setEntities(data.draft.entities);
          } else {
            setEntities([]);
          }
          const incoming = data.draft.userStories || data.draft.stories;
          if (incoming && Array.isArray(incoming) && incoming.length > 0) {
            setStories(mapIncomingStories(incoming, data.draft.entities || []));
          } else {
            setStories([]);
          }
        } else {
          setEntities([]);
          setStories([]);
        }
      })
      .catch((err) => {
        console.warn('Could not load session requirements:', err);
      });

    return () => {
      isMounted = false;
    };
  }, [activeSessionId]);

  const handleTransform = async (overrideProvider?: any) => {
    setIsProcessing(true);
    setFeedbackMsg(null);
    setErrorMsg(null);
    const effectiveProvider = typeof overrideProvider === 'string' ? overrideProvider : provider;
    try {
      const res = await requirementsService.transform({
        naturalLanguageText: promptText,
        serviceName: activeSession?.specName || undefined,
        apiKey,
        provider: effectiveProvider,
      });

      let nextEntities = entities;
      if (res?.entities && Array.isArray(res.entities) && res.entities.length > 0) {
        nextEntities = res.entities;
        setEntities(res.entities);
      }

      const incomingStories = res?.userStories || res?.stories;
      if (incomingStories && Array.isArray(incomingStories) && incomingStories.length > 0) {
        setStories(mapIncomingStories(incomingStories, nextEntities));
      }

      setFeedbackMsg('Requerimientos transformados: Historias BDD generadas exitosamente (mínimo 3 historias).');
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message;
      if (err.response?.status === 401) {
        setErrorMsg(`Se requiere clave API para ${effectiveProvider.toUpperCase()}. Puedes configurarla en Ajustes (icono ⚙️) o activar el Modo Offline para continuar sin costo.`);
      } else {
        setErrorMsg(detail || 'Error al transformar requerimientos con IA.');
      }
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRefineSubmit = async () => {
    if (!refinePrompt.trim()) return;
    setIsProcessing(true);
    setErrorMsg(null);
    try {
      const rawServiceName = (activeSession?.specName || 'order-service')
        .toLowerCase()
        .replace(/[^a-z0-9-]/g, '-')
        .replace(/^-+|-+$/g, '') || 'order-service';
      const normalizedEntities = normalizeEntitiesForDraft(entities, rawServiceName);
      const normalizedStories = stories.map((s, idx) => ({
        id: s.id || `US-${idx + 1}`,
        priority: 'P1',
        role: s.role || 'Usuario',
        intent: s.feature || (s as any).intent || 'Operación de negocio',
        benefit: s.benefit || 'Completar operación',
        scenarios: (s.scenarios || []).map((sc, i) => ({
          scenarioId: (sc as any).scenarioId || `AC-${s.id}.${i + 1}`,
          given: sc.given || 'Precondición válida',
          when: sc.when || 'Operación ejecutada',
          then: sc.then || 'Resultado esperado obtenido',
        })),
      }));

      const res = await requirementsService.refine({
        specificationDraft: {
          serviceName: rawServiceName,
          packageName: `com.corp.${rawServiceName.replace(/[^a-z0-9]/g, '')}`,
          basePort: 8080,
          entities: normalizedEntities,
          userStories: normalizedStories,
        },
        refinementPrompt: refinePrompt,
        apiKey,
        provider,
      });

      let nextEntities = entities;
      if (res?.entities && Array.isArray(res.entities) && res.entities.length > 0) {
        nextEntities = res.entities;
        setEntities(res.entities);
      }

      const incomingStories = res?.userStories || res?.stories;
      if (incomingStories && Array.isArray(incomingStories) && incomingStories.length > 0) {
        setStories(mapIncomingStories(incomingStories, nextEntities));
      }

      setIsRefineOpen(false);
      setRefinePrompt('');
      setFeedbackMsg('Especificación refinada exitosamente mediante IA.');
    } catch (err: any) {
      setIsRefineOpen(false);
      setErrorMsg(err.response?.data?.detail || err.message || 'Error al refinar historias con IA.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDownloadSpecMd = () => {
    if (stories.length === 0) return;
    const mdLines = [
      `# Especificación de Requisitos: ${activeSession?.specName || 'microservice'}`,
      `\n## Descripción de Alto Nivel\n${promptText}\n`,
      `## Entidades Identificadas\n${entities.map((e) => `- ${getEntityName(e)}`).join('\n')}\n`,
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
    if (stories.length === 0) {
      setFeedbackMsg('Debe generar o agregar historias de usuario antes de transferir a generación.');
      return;
    }
    setIsProcessing(true);
    try {
      const rawServiceName = (activeSession?.specName || 'order-service').toLowerCase().replace(/[^a-z0-9-]/g, '-').replace(/^-+|-+$/g, '') || 'order-service';
      const cleanPackage = `com.tcs.${rawServiceName.replace(/[^a-z0-9]/g, '')}`;
      const normalizedEntities = normalizeEntitiesForDraft(entities, rawServiceName);

      const blueprintPayload = {
        serviceName: rawServiceName,
        packageName: cleanPackage,
        basePort: 8080,
        databaseMode: 'PostgreSQL',
        entities: normalizedEntities,
        userStories: stories.map((s, idx) => ({
          id: s.id || `US-${idx + 1}`,
          priority: 'P1',
          role: s.role || 'Usuario',
          intent: s.feature || (s as any).intent || 'Gestionar entidades de negocio',
          benefit: s.benefit || 'Completar flujo operacional',
          scenarios: (s.scenarios || []).map((sc, i) => ({
            scenarioId: (sc as any).scenarioId || `AC-${s.id}.${i + 1}`,
            given: sc.given || 'Precondición del sistema verificada',
            when: sc.when || 'Se invoca el endpoint REST',
            then: sc.then || 'Se retorna respuesta esperada',
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
      setActiveTab(5); // Switch to Tab 5 Monitor
    } catch (err) {
      console.error('Error al transferir a generación:', err);
      setActiveTab(5);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleOpenCreateStory = () => {
    const nextIdx = stories.length + 1;
    setEditingStoryId(null);
    setStoryForm({
      id: `US-${String(nextIdx).padStart(3, '0')}`,
      title: 'Nueva Funcionalidad de Negocio',
      role: 'Usuario del Sistema',
      feature: 'Ejecutar una operación transaccional',
      benefit: 'Garantizar la integridad de los datos',
      scenarios: [
        {
          title: 'Operación exitosa con parámetros válidos',
          given: 'El microservicio se encuentra en ejecución y la base de datos disponible',
          when: 'El usuario envía la petición con datos correctos',
          then: 'La transacción se persiste y se retorna código 201 Created',
        },
      ],
      detected_entities: entities.slice(0, 2).map(getEntityName),
    });
    setIsStoryModalOpen(true);
  };

  const handleOpenEditStory = (story: BddStory) => {
    setEditingStoryId(story.id);
    setStoryForm({
      id: story.id,
      title: story.title || '',
      role: story.role || 'Usuario',
      feature: story.feature || '',
      benefit: story.benefit || '',
      scenarios:
        story.scenarios && story.scenarios.length > 0
          ? story.scenarios.map((sc) => ({ ...sc }))
          : [
              {
                title: 'Operación exitosa',
                given: 'El sistema se encuentra en estado operativo',
                when: 'Se envía la solicitud con parámetros válidos',
                then: 'Se procesa la transacción exitosamente',
              },
            ],
      detected_entities: story.detected_entities ? [...story.detected_entities] : [],
    });
    setIsStoryModalOpen(true);
  };

  const handleSaveStory = () => {
    if (!storyForm.title.trim()) {
      setErrorMsg('Debe ingresar un título descriptivo para la historia de usuario.');
      return;
    }
    if (!storyForm.feature.trim()) {
      setErrorMsg('Debe ingresar la funcionalidad o deseo (Quiero...).');
      return;
    }

    if (editingStoryId) {
      setStories((prev) =>
        prev.map((s) => (s.id === editingStoryId ? { ...storyForm } : s))
      );
      setFeedbackMsg(`Historia de usuario ${storyForm.id} modificada exitosamente.`);
    } else {
      setStories((prev) => [...prev, { ...storyForm }]);
      setFeedbackMsg(`Historia de usuario ${storyForm.id} agregada exitosamente.`);
    }
    setIsStoryModalOpen(false);
    setEditingStoryId(null);
  };

  const handleAddScenario = () => {
    const scIdx = (storyForm.scenarios?.length || 0) + 1;
    setStoryForm((prev) => ({
      ...prev,
      scenarios: [
        ...(prev.scenarios || []),
        {
          title: `Escenario ${scIdx}: Caso de uso o validación`,
          given: 'El sistema valida las precondiciones necesarias',
          when: 'Se ejecuta la operación con los parámetros dados',
          then: 'Se procesa el resultado conforme a la regla de negocio',
        },
      ],
    }));
  };

  const handleUpdateScenario = (idx: number, field: keyof BddScenario, value: string) => {
    setStoryForm((prev) => {
      const nextScenarios = [...(prev.scenarios || [])];
      if (nextScenarios[idx]) {
        nextScenarios[idx] = { ...nextScenarios[idx], [field]: value };
      }
      return { ...prev, scenarios: nextScenarios };
    });
  };

  const handleRemoveScenario = (idx: number) => {
    if ((storyForm.scenarios?.length || 0) <= 1) return;
    setStoryForm((prev) => ({
      ...prev,
      scenarios: prev.scenarios.filter((_, i) => i !== idx),
    }));
  };

  const handleAddStory = handleOpenCreateStory;

  const handleDeleteStory = (storyId: string) => {
    setStories(stories.filter((s) => s.id !== storyId));
  };

  const handleProceedToArchitecture = async () => {
    if (stories.length === 0) {
      setFeedbackMsg('Debe generar o agregar al menos una historia de usuario antes de pasar a Arquitectura.');
      return;
    }
    const rawServiceName = (activeSession?.specName || 'order-service')
      .toLowerCase()
      .replace(/[^a-z0-9-]/g, '-')
      .replace(/^-+|-+$/g, '') || 'order-service';
    const cleanPackage = `com.corp.${rawServiceName.replace(/[^a-z0-9]/g, '')}`;
    const normalizedEntities = normalizeEntitiesForDraft(entities, rawServiceName);

    const draftObj = {
      ...(currentDraft || {}),
      serviceName: currentDraft?.serviceName || rawServiceName,
      packageName: currentDraft?.packageName || cleanPackage,
      basePort: currentDraft?.basePort ?? 8080,
      entities: normalizedEntities,
      userStories: stories.map((s, idx) => ({
        id: s.id || `US-${idx + 1}`,
        priority: 'P1',
        role: s.role,
        intent: s.feature || (s as any).intent || 'Gestionar entidades de negocio',
        benefit: s.benefit || 'Completar operaciones',
        scenarios: s.scenarios.map((sc, i) => ({
          scenarioId: (sc as any).scenarioId || `AC-${s.id}.${i + 1}`,
          given: sc.given,
          when: sc.when,
          then: sc.then,
        })),
      })),
    };
    setCurrentDraft(draftObj);

    if (activeSessionId) {
      try {
        const saved = await requirementsService.saveSessionRequirements(activeSessionId, draftObj, revisionId, configurationVersion);
        setRevisionId(saved.revisionId);
        setConfigurationVersion(saved.configurationVersion);
        await requirementsService.approveSessionRequirements(activeSessionId, saved.revisionId, saved.configurationVersion);
      } catch (err) {
        setFeedbackMsg('No se pudo aprobar: la revisión cambió o la operación está bloqueada. Recargue y revise el borrador.');
        return;
      }
      await orchestratorService.invalidateDownstream(activeSessionId, 'STORIES');
      await reloadCurrentOverview();
    }
    setActiveTab(2); // Move to tab 2 Architecture
  };

  const handlePrepareRegeneration = async () => {
    if (!activeSessionId || !revisionId || !backupConfirmed) return;
    setIsProcessing(true);
    try {
      const result = await requirementsService.prepareRegeneration(activeSessionId, revisionId);
      setFeedbackMsg(`Respaldo creado: ${result.backup}. Ya puede ejecutar la generación para esta revisión.`);
      setBackupConfirmed(false);
      await reloadCurrentOverview();
    } catch {
      setFeedbackMsg('No se pudo preparar la regeneración. Recargue la revisión y espere a que termine la operación activa.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="space-y-6">
      {activeSessionId && revisionId && (
        <div className="rounded-lg border border-amber-300 p-4 space-y-3">
          <p className="text-sm">Si cambió el borrador, prepare las fuentes generadas antes de volver a ejecutar el flujo. Se respaldan los archivos generados obsoletos; las ediciones manuales requieren revisión.</p>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={backupConfirmed} onChange={(event) => setBackupConfirmed(event.target.checked)} />
            Confirmo la regeneración de archivos obsoletos con respaldo previo.
          </label>
          <button type="button" disabled={isProcessing || !backupConfirmed} onClick={handlePrepareRegeneration}
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
            Preparar regeneración con respaldo
          </button>
        </div>
      )}
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
              onClick={() => handleTransform()}
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
              disabled={isProcessing || stories.length === 0}
              className="py-2 px-3 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-300 dark:border-slate-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Refinar con IA
            </button>
            <button
              onClick={handleDownloadSpecMd}
              disabled={stories.length === 0}
              className="flex items-center gap-1.5 py-2 px-3 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-300 dark:border-slate-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              title="Descargar documento spec.md compatible con Spec Kit"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Descargar spec.md</span>
            </button>
            <button
              onClick={handleTransferDirect}
              disabled={isProcessing || stories.length === 0}
              className="py-2 px-3 rounded-lg text-xs font-medium bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 hover:bg-indigo-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Transferir a Generación
            </button>
            <button
              onClick={handleProceedToArchitecture}
              disabled={isProcessing || stories.length === 0}
              className="py-2 px-4 rounded-lg text-xs font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 hover:bg-emerald-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
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

          {!apiKey && provider !== 'mock' && !errorMsg && (
            <div className="p-2.5 rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/80 text-xs text-blue-900 dark:text-blue-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-blue-600 shrink-0" />
                <span>Motor LLM actual: <strong className="uppercase">{provider}</strong> (requiere API Key en ⚙️ Ajustes o usar Modo Offline).</span>
              </div>
              <button
                type="button"
                onClick={() => {
                  setProvider('mock');
                  setErrorMsg(null);
                }}
                className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded text-[11px] font-medium shrink-0 transition-colors"
              >
                ⚡ Usar Modo Offline (Sin Costo)
              </button>
            </div>
          )}

          {errorMsg && (
            <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800/80 text-xs text-amber-900 dark:text-amber-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-sm">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5 sm:mt-0" />
                <span>{errorMsg}</span>
              </div>
              {provider !== 'mock' && (
                <button
                  onClick={() => {
                    setProvider('mock');
                    setErrorMsg(null);
                    handleTransform('mock');
                  }}
                  className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 active:bg-amber-800 text-white font-medium rounded-md text-xs shrink-0 transition-colors shadow-sm"
                >
                  ⚡ Activar Modo Offline y Generar
                </button>
              )}
            </div>
          )}

          {/* Entidades Detectadas */}
          <div>
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 mr-2">
              Entidades de Dominio Detectadas:
            </span>
            {entities.length === 0 ? (
              <span className="text-xs text-slate-400 italic">
                Ninguna aún. Ingrese el prompt funcional y presione "Descomponer con IA".
              </span>
            ) : (
              <div className="inline-flex flex-wrap gap-1.5 mt-1">
                {entities.map((ent, i) => {
                  const name = getEntityName(ent);
                  const tableName = getEntityTableName(ent);
                  return (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-700 inline-flex items-center gap-1"
                    >
                      <span>{name}</span>
                      {tableName && (
                        <span className="text-[10px] text-slate-400 dark:text-slate-500 font-normal">
                          ({tableName})
                        </span>
                      )}
                    </span>
                  );
                })}
              </div>
            )}
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

        {stories.length === 0 ? (
          <div className="p-8 rounded-xl border border-dashed border-slate-300 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30 text-center space-y-3">
            <div className="w-12 h-12 mx-auto rounded-full bg-blue-50 dark:bg-blue-950/60 flex items-center justify-center text-blue-600 dark:text-blue-400">
              <Sparkles className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                No hay historias de usuario en esta sesión
              </h4>
              <p className="text-xs text-slate-500 dark:text-slate-400 max-w-lg mx-auto">
                Escriba la descripción funcional del microservicio en el campo superior y presione{' '}
                <strong className="text-slate-700 dark:text-slate-300">"Descomponer con IA"</strong>{' '}
                para generar automáticamente un mínimo de 3 historias de usuario formalizadas con criterios Given / When / Then.
              </p>
            </div>
            <div className="pt-2 flex items-center justify-center gap-3">
              <button
                onClick={() => handleTransform()}
                disabled={isProcessing || !promptText.trim()}
                className="inline-flex items-center gap-2 py-2 px-4 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 shadow-sm transition-all disabled:opacity-50"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Descomponer con IA (Mínimo 3 Historias)</span>
              </button>
              <button
                onClick={handleAddStory}
                className="inline-flex items-center gap-1.5 py-2 px-3 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 hover:bg-slate-50 transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Crear Manualmente</span>
              </button>
            </div>
          </div>
        ) : (
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
                      onClick={() => handleOpenEditStory(story)}
                      className="p-1 text-slate-400 hover:text-blue-600 rounded hover:bg-blue-50 dark:hover:bg-blue-950/40 transition-colors"
                      title="Modificar historia de usuario"
                    >
                      <Edit className="w-3.5 h-3.5" />
                    </button>
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
                    <button
                      type="button"
                      onClick={() => handleOpenEditStory(story)}
                      className="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 hover:underline font-semibold"
                    >
                      <Edit className="w-3 h-3" />
                      <span>Modificar historia</span>
                    </button>
                    <span className="font-mono text-[11px] text-slate-500 dark:text-slate-400">
                      {story.scenarios?.length || 0} escenario(s) BDD
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
                        Escenario: {sc.title || (sc as any).scenarioId || `Escenario ${sIdx + 1}`}
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
        )}
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

      {/* SlideOverDrawer for Manual Story Creation & Modification */}
      <SlideOverDrawer
        isOpen={isStoryModalOpen}
        onClose={() => {
          setIsStoryModalOpen(false);
          setEditingStoryId(null);
        }}
        title={editingStoryId ? `Modificar Historia de Usuario (${storyForm.id})` : 'Nueva Historia de Usuario BDD (Manual)'}
        subtitle={editingStoryId ? 'Modifique los campos, el formato Connextra y los escenarios Given/When/Then' : 'Ingrese manualmente la historia de usuario y sus criterios de aceptación'}
        widthClass="max-w-2xl"
      >
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-1">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                ID de Historia
              </label>
              <input
                type="text"
                value={storyForm.id}
                onChange={(e) => setStoryForm({ ...storyForm, id: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-xs font-mono focus:ring-2 focus:ring-blue-500 focus:outline-none"
                placeholder="US-001"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Título Descriptivo
              </label>
              <input
                type="text"
                value={storyForm.title}
                onChange={(e) => setStoryForm({ ...storyForm, title: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
                placeholder="Ej: Registro de nueva orden de compra"
              />
            </div>
          </div>

          {/* Formato Connextra: Como / Quiero / Para */}
          <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 space-y-3">
            <h4 className="text-xs font-semibold text-slate-900 dark:text-white">
              Estructura Connextra / BDD
            </h4>
            <div>
              <label className="block text-[11px] font-medium text-slate-600 dark:text-slate-400 mb-1">
                <strong className="text-indigo-600 dark:text-indigo-400">COMO</strong> [Rol de usuario / actor]
              </label>
              <input
                type="text"
                value={storyForm.role}
                onChange={(e) => setStoryForm({ ...storyForm, role: e.target.value })}
                className="w-full px-2.5 py-1.5 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
                placeholder="Ej: Cliente autenticado, Administrador"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-600 dark:text-slate-400 mb-1">
                <strong className="text-blue-600 dark:text-blue-400">QUIERO</strong> [Funcionalidad o acción requerida]
              </label>
              <textarea
                rows={2}
                value={storyForm.feature}
                onChange={(e) => setStoryForm({ ...storyForm, feature: e.target.value })}
                className="w-full px-2.5 py-1.5 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
                placeholder="Ej: Registrar un pedido con múltiples ítems y calcular el total de la compra"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-600 dark:text-slate-400 mb-1">
                <strong className="text-emerald-600 dark:text-emerald-400">PARA</strong> [Beneficio o propósito de negocio]
              </label>
              <textarea
                rows={2}
                value={storyForm.benefit}
                onChange={(e) => setStoryForm({ ...storyForm, benefit: e.target.value })}
                className="w-full px-2.5 py-1.5 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
                placeholder="Ej: Adquirir los productos seleccionados y mantener actualizado el inventario"
              />
            </div>
          </div>

          {/* Criterios de Aceptación / Escenarios BDD */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-slate-900 dark:text-white">
                Criterios de Aceptación Given / When / Then ({storyForm.scenarios?.length || 0})
              </h4>
              <button
                type="button"
                onClick={handleAddScenario}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 font-semibold"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>+ Añadir Escenario</span>
              </button>
            </div>

            {storyForm.scenarios?.map((sc, sIdx) => (
              <div
                key={sIdx}
                className="p-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/80 space-y-2.5 text-xs shadow-sm"
              >
                <div className="flex items-center justify-between">
                  <input
                    type="text"
                    value={sc.title}
                    onChange={(e) => handleUpdateScenario(sIdx, 'title', e.target.value)}
                    className="font-semibold text-slate-800 dark:text-slate-200 bg-transparent border-b border-dashed border-slate-300 dark:border-slate-600 focus:outline-none pb-0.5 w-3/4"
                    placeholder={`Escenario ${sIdx + 1}: Título o descripción corta`}
                  />
                  {storyForm.scenarios.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveScenario(sIdx)}
                      className="text-slate-400 hover:text-rose-500 p-1 rounded transition-colors"
                      title="Eliminar este escenario"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="w-20 text-[10px] font-bold text-indigo-600 dark:text-indigo-400 uppercase shrink-0">
                      DADO QUE
                    </span>
                    <input
                      type="text"
                      value={sc.given}
                      onChange={(e) => handleUpdateScenario(sIdx, 'given', e.target.value)}
                      className="flex-1 px-2.5 py-1.5 rounded border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-white text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                      placeholder="Precondición válida del microservicio o base de datos"
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-20 text-[10px] font-bold text-blue-600 dark:text-blue-400 uppercase shrink-0">
                      CUANDO
                    </span>
                    <input
                      type="text"
                      value={sc.when}
                      onChange={(e) => handleUpdateScenario(sIdx, 'when', e.target.value)}
                      className="flex-1 px-2.5 py-1.5 rounded border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-white text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                      placeholder="El usuario envía la solicitud o ejecuta la acción"
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-20 text-[10px] font-bold text-emerald-600 dark:text-emerald-400 uppercase shrink-0">
                      ENTONCES
                    </span>
                    <input
                      type="text"
                      value={sc.then}
                      onChange={(e) => handleUpdateScenario(sIdx, 'then', e.target.value)}
                      className="flex-1 px-2.5 py-1.5 rounded border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-white text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                      placeholder="Resultado esperado, persistencia y código HTTP (ej. 200 OK / 201 Created)"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Botones de acción */}
          <div className="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
            <button
              type="button"
              onClick={() => {
                setIsStoryModalOpen(false);
                setEditingStoryId(null);
              }}
              className="px-4 py-2 text-xs font-medium rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleSaveStory}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg text-white bg-blue-600 hover:bg-blue-700 transition-colors shadow-sm"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{editingStoryId ? 'Guardar Cambios' : 'Guardar Historia'}</span>
            </button>
          </div>
        </div>
      </SlideOverDrawer>
    </div>
  );
};
