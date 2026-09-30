import React, { useState, useEffect } from 'react';
import {
  Server,
  Play,
  Square,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Clock,
  RefreshCw,
  Send,
  Plus,
  Trash2,
  Database,
  Terminal,
  FileCode,
  Globe,
  Boxes,
  Cpu,
  Layers,
  ExternalLink,
} from 'lucide-react';
import { SingleRowCard } from '../components/common/SingleRowCard';
import { CodeViewer } from '../components/common/CodeViewer';
import { useStudio } from '../context/StudioContext';
import { devopsService, LocalDeploymentSession, SmokeTestResult } from '../services/devopsService';
import { exportService } from '../services/exportService';



//: What to show when an artifact has not been generated. Names the file it looked for,
//: so "not generated" can never be mistaken for "generated differently".
const MissingArtifact: React.FC<{ path: string }> = ({ path }) => (
  <div className="rounded-lg border border-dashed border-slate-300 dark:border-slate-700 p-6 text-center">
    <p className="text-xs text-slate-500 dark:text-slate-400">
      No hay <span className="font-mono">{path}</span> en este workspace.
    </p>
    <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
      Pulse <strong>Generar Manifiestos DevOps</strong> para producirlo.
    </p>
  </div>
);

//: Which generated file each subtab shows. The keys are the filenames the API returns
//: under `kubernetesManifests`, so the tab and the generator cannot disagree.
const K8S_FILES: Record<string, string> = {
  deployment: 'deployment.yaml',
  service: 'service.yaml',
  configmap: 'configmap.yaml',
  ingress: 'ingress.yaml',
};

export const DevOpsDeploymentView: React.FC = () => {
  const { activeSessionId, reloadCurrentOverview } = useStudio();

  const [deployment, setDeployment] = useState<LocalDeploymentSession | null>(null);

  const [hostPort, setHostPort] = useState<number>(8080);
  const [activeManifestTab, setActiveManifestTab] = useState<'docker' | 'compose' | 'cicd' | 'k8s'>('docker');
  // filename -> content, exactly as the API returns it. Empty until something generates
  // it or the workspace is read, and the tab says so rather than inventing a manifest.
  const [k8sManifests, setK8sManifests] = useState<Record<string, string>>({});
  // The generated DevOps files, by workspace-relative path. Same reasoning as the
  // Kubernetes manifests: the constants these replaced were samples from another
  // service, so every tab showed a plausible artifact whether or not one existed.
  const [devopsFiles, setDevopsFiles] = useState<Record<string, string>>({});
  const [activeCicdSubtab, setActiveCicdSubtab] = useState<'github' | 'gitlab'>('github');
  const [activeK8sSubtab, setActiveK8sSubtab] = useState<'deployment' | 'service' | 'configmap' | 'ingress'>('deployment');

  const [isGenerating, setIsGenerating] = useState(false);
  const [isDeploying, setIsDeploying] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [smokeResult, setSmokeResult] = useState<SmokeTestResult | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [terminalLogs, setTerminalLogs] = useState<string[]>([]);

  // Live Playground State: Dynamic CRUD
  const [orders, setOrders] = useState<any[]>([]);
  // The collection path this service actually exposes, read from its controllers.
  // It used to be a hardcoded `/api/v1/orders`, which is wrong for every blueprint
  // without an Order entity -- so the form posted to a path that did not exist and the
  // old silent fallback hid the 404. Empty until discovery answers; the form refuses
  // to submit rather than guessing.
  const [crudPath, setCrudPath] = useState('');
  const [availableResources, setAvailableResources] = useState<string[]>([]);
  // The entities this service actually declares, from its own domain_model.json. The form
  // below used to be hardcoded to an Orders shape (customerEmail, totalAmount, status)
  // and posted it to whichever path discovery found -- so on any other blueprint it sent
  // fields the target entity does not have and the service rejected it.
  const [modelEntities, setModelEntities] = useState<any[]>([]);
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});

  // REST Console State
  const [reqMethod, setReqMethod] = useState<'GET' | 'POST' | 'DELETE'>('GET');
  const [reqEndpoint, setReqEndpoint] = useState('/actuator/health');
  const [reqBody, setReqBody] = useState('{}');
  const [restResponse, setRestResponse] = useState<string | null>(null);
  const [restLatency, setRestLatency] = useState<number | null>(null);
  const [restStatusCode, setRestStatusCode] = useState<number | null>(null);

  const fetchStatus = async () => {
    if (!activeSessionId) {
      setDeployment(null);
      setTerminalLogs([]);
      return;
    }
    try {
      const s = await devopsService.getDeploymentStatus(activeSessionId);
      if (s) {
        setDeployment(s);
        if (s.hostPort) setHostPort(s.hostPort);
      } else {
        setDeployment(null);
      }
      const logs = await devopsService.getLogs(activeSessionId);
      if (logs && logs.length > 0) {
        setTerminalLogs(logs);
      }
    } catch {
      setDeployment(null);
    }
  };

  useEffect(() => {
    if (activeSessionId) {
      fetchStatus();
    }
  }, [activeSessionId]);

  useEffect(() => {
    // Read whatever is already on disk, so the tab is correct after a reload and not
    // only immediately after pressing "Generar Manifiestos".
    if (!activeSessionId) {
      setK8sManifests({});
      return;
    }
    let cancelled = false;
    const wanted = [
      ...Object.values(K8S_FILES).map((f) => `k8s/${f}`),
      'Dockerfile',
      '.dockerignore',
      'docker-compose.yml',
      '.github/workflows/ci-cd.yml',
      '.gitlab-ci.yml',
      'domain_model.json',
    ];
    // Guarded: a missing or throwing reader must not take the whole view down. It did --
    // the first version called this unguarded and the view crashed on mount in any test
    // whose `exportService` mock lacked the method, so the page rendered nothing at all.
    const read = (path: string): Promise<readonly [string, string] | null> => {
      try {
        const fn = (exportService as { getArtifactContent?: (id: string, p: string) => Promise<string> })
          .getArtifactContent;
        if (typeof fn !== 'function') return Promise.resolve(null);
        return fn(activeSessionId, path).then((content) => [path, content] as const);
      } catch {
        return Promise.resolve(null);
      }
    };
    Promise.all(wanted.map((path) => read(path).catch(() => null))).then((entries) => {
      if (cancelled) return;
      const found = Object.fromEntries(entries.filter(Boolean) as [string, string][]);
      setK8sManifests(
        Object.fromEntries(Object.entries(found).filter(([p]) => p.startsWith('k8s/')).map(([p, c]) => [p.slice(4), c])),
      );
      setDevopsFiles(
        Object.fromEntries(
          Object.entries(found).filter(([p]) => !p.startsWith('k8s/') && p !== 'domain_model.json'),
        ),
      );
      try {
        const model = JSON.parse(found['domain_model.json'] || '{}');
        setModelEntities(Array.isArray(model.entities) ? model.entities : []);
      } catch {
        // Absent or unparseable: the form falls back to a JSON body, which is honest.
        setModelEntities([]);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [activeSessionId]);

  useEffect(() => {
    if (!activeSessionId) {
      setCrudPath('');
      setAvailableResources([]);
      return;
    }
    let cancelled = false;
    // Guarded for the same reason as the artifact reader below: this is a new dependency
    // and an unmocked or older service object would otherwise throw on mount and blank
    // the entire screen. Discovery failing should leave the form empty, not break the tab.
    const discover = (devopsService as {
      getPlaygroundResources?: (id: string) => Promise<{ resources?: string[]; defaultResource?: string | null }>;
    }).getPlaygroundResources;
    if (typeof discover !== 'function') {
      setAvailableResources([]);
      setCrudPath('');
      return () => {
        cancelled = true;
      };
    }
    discover(activeSessionId)
      .then((res) => {
        if (cancelled) return;
        setAvailableResources(res.resources || []);
        setCrudPath(res.defaultResource || '');
      })
      .catch(() => {
        if (cancelled) return;
        setAvailableResources([]);
        setCrudPath('');
      });
    return () => {
      cancelled = true;
    };
  }, [activeSessionId]);

  const handleGenerateManifests = async () => {
    if (!activeSessionId) return;
    setIsGenerating(true);
    setFeedback(null);
    try {
      // The response was previously discarded -- `await` with no assignment -- which is
      // how the Kubernetes tab ended up rendering samples instead of these files.
      const bundle = await devopsService.generateManifests(activeSessionId, 'POSTGRESQL', hostPort);
      setK8sManifests(bundle.kubernetesManifests || {});
      setDevopsFiles({
        Dockerfile: bundle.dockerfileContent,
        '.dockerignore': bundle.dockerignoreContent,
        'docker-compose.yml': bundle.dockerComposeContent,
        '.github/workflows/ci-cd.yml': bundle.githubActionsWorkflow,
        '.gitlab-ci.yml': bundle.gitlabCiWorkflow,
      });
      setFeedback('✅ Manifiestos DevOps (Dockerfile, Compose, CI/CD y Kubernetes) generados exitosamente.');
      await fetchStatus();
    } catch (err: any) {
      setFeedback(err.response?.data?.detail || 'Error al generar manifiestos DevOps.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDeployLocal = async () => {
    if (!activeSessionId) return;
    setIsDeploying(true);
    setFeedback(null);
    try {
      const res = await devopsService.deployLocal(activeSessionId, hostPort, true);
      setDeployment(res);
      setFeedback(res.message || '🚀 Contenedor levantado localmente en http://localhost:' + hostPort);
      await reloadCurrentOverview();
    } catch (err: any) {
      setFeedback(err.response?.data?.detail || 'Modo degradado: Docker local no disponible. Manifiestos exportables listos.');
    } finally {
      setIsDeploying(false);
    }
  };

  const handleStopContainers = async () => {
    if (!activeSessionId) return;
    setIsStopping(true);
    try {
      const res = await devopsService.stopContainers(activeSessionId);
      setDeployment(res);
      setFeedback('Contenedores y redes detenidos correctamente.');
      await reloadCurrentOverview();
    } catch (err: any) {
      // Report the real outcome. This used to say "Contenedores detenidos." even
      // when the stop request failed, so the UI claimed a state the host was not in.
      setFeedback(
        `No se pudieron detener los contenedores: ${err?.message || String(err)}. ` +
        `El estado mostrado puede no reflejar el host.`,
      );
    } finally {
      setIsStopping(false);
    }
  };

  const handleSmokeTest = async () => {
    if (!activeSessionId) return;
    setIsTesting(true);
    try {
      const res = await devopsService.runSmokeTest(activeSessionId, hostPort);
      setSmokeResult(res);
    } catch (err) {
      // SKIPPED, not SUCCESS. This used to fabricate a pass -- status 'SUCCESS',
      // httpStatusCode 200, latencyMs 14, "Endpoint de salud verificado" -- on any
      // failure, so pressing "Ejecutar Smoke Test" reported a healthy service that
      // was never contacted. It is the same three-state discipline the diagnostics
      // use: *verified*, *verified with findings*, and *not evaluable* must never be
      // conflated, and "the check could not run" is the third one.
      setSmokeResult({
        sessionId: activeSessionId,
        endpointTested: `http://localhost:${hostPort}/actuator/health`,
        status: 'SKIPPED',
        message:
          `Smoke test NO ejecutado: ${err instanceof Error ? err.message : String(err)}. ` +
          `No se contactó ningún endpoint, así que esto no dice nada sobre el servicio ` +
          `(ni bueno ni malo). Comprueba que el contenedor está desplegado.`,
      });
    } finally {
      setIsTesting(false);
    }
  };

  // The entity behind the selected resource path. Paths are the pluralised table name
  // (`/api/v1/customers` -> `customers`), which is how the emitted controllers are built.
  const pathTail = (crudPath.split('/').filter(Boolean).pop() || '').toLowerCase();
  const targetEntity = modelEntities.find(
    (e: any) =>
      String(e.tableName || '').toLowerCase() === pathTail ||
      `${String(e.name || '').toLowerCase()}s` === pathTail,
  );
  // The primary key is generated by the service, so it is never an input.
  const createFields: any[] = targetEntity
    ? (targetEntity.attributes || []).filter((a: any) => !a.isPrimaryKey)
    : [];

  const coerceField = (attr: any, raw: string): any => {
    const t = String(attr.javaType || attr.type || 'String');
    if (t.startsWith('List')) {
      try {
        return JSON.parse(raw);
      } catch {
        throw new Error(`${attr.name} debe ser una lista JSON, por ejemplo ["a","b"]`);
      }
    }
    if (t === 'Boolean' || t === 'boolean') return raw.toLowerCase() === 'true';
    if (['Long', 'Integer', 'int', 'long', 'BigDecimal', 'Double', 'double', 'Float'].includes(t)) {
      const n = Number(raw);
      if (Number.isNaN(n)) throw new Error(`${attr.name} debe ser numérico`);
      return n;
    }
    return raw;
  };

  const handleCreateRecordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeSessionId) return;
    if (!crudPath) {
      setFeedback(
        'No se ha detectado ninguna ruta REST en este servicio todavía. ' +
        'Despliega el servicio y vuelve a intentarlo, o usa la consola REST de la derecha.',
      );
      return;
    }

    // Built from the target entity's own attributes. The previous payload was an Orders
    // template with `totalAmount: parseFloat(x) || 99.99` -- an amount invented on the
    // user's behalf -- plus `status: 'CONFIRMED'` and two timestamps the entity may not
    // declare. Sending fields a service does not have is why the call failed.
    if (createFields.length === 0) {
      setFeedback(
        `No se han podido determinar los campos de ${crudPath || 'la ruta seleccionada'}. ` +
        'Comprueba que la entidad existe en el modelo de dominio del servicio.',
      );
      return;
    }
    const payload: Record<string, any> = {};
    try {
      for (const attr of createFields) {
        const raw = (fieldValues[attr.name] ?? '').trim();
        if (raw === '') {
          if (attr.nullable) continue; // genuinely optional: omit rather than invent
          setFeedback(`El campo ${attr.name} es obligatorio.`);
          return;
        }
        payload[attr.name] = coerceField(attr, raw);
      }
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : String(err));
      return;
    }

    // The record is only real if the service accepted it. This used to swallow the
    // failure, invent an id (`orders.length + 101`), default the status to
    // 'CONFIRMED' and then append a log line claiming `201 CREATED` -- so the table
    // showed a record and the log showed a success whether or not anything had been
    // called. On a workspace whose generated service does not expose /api/v1/orders
    // the form targeted a non-existent endpoint and the fallback hid the 404.
    let createdId: number | string | null = null;
    let actualStatus: string | null = null;
    let createdHttp: number | null = null;
    let failure: string | null = null;

    try {
      // Through the platform, not the browser: a direct cross-origin call is rejected
      // by the generated service (no CORS), and `crudPath` is the path its controllers
      // actually expose rather than a hardcoded /api/v1/orders.
      const result = await devopsService.proxyPlayground(activeSessionId, {
        method: 'POST',
        path: crudPath,
        body: payload,
      });
      if (result.error) {
        failure = result.error;
      } else if (result.statusCode && result.statusCode < 300) {
        createdHttp = result.statusCode;
        const data = result.body as { id?: number | string; status?: string } | null;
        if (data?.id) createdId = data.id;
        if (data?.status) actualStatus = data.status;
      } else {
        failure = `HTTP ${result.statusCode}`;
      }
    } catch (err) {
      failure = err instanceof Error ? err.message : String(err);
    }

    if (failure) {
      setTerminalLogs((prev) => [
        ...prev,
        `[http] POST ${crudPath} FAILED (${failure}) — el servicio no aceptó el registro`,
      ]);
      setFeedback(
        `No se pudo crear el registro: ${failure}. ` +
        `La ruta ${crudPath} se consulta a través del backend de la plataforma — ` +
        `verifica que el contenedor está en ejecución y que la entidad existe.`,
      );
      return;
    }

    const newOrd = {
      id: createdId,
      status: actualStatus,
      createdAt: new Date().toLocaleTimeString(),
      submitted: payload,
    };
    setOrders([newOrd, ...orders]);
    setFieldValues({});
    setTerminalLogs((prev) => [
      ...prev,
      `[http] POST ${crudPath} ${createdHttp ?? '—'} ${JSON.stringify(payload)}`,
    ]);
  };

  const handleSendCustomRest = async () => {
    if (!activeSessionId) return;
    const t0 = performance.now();
    const cleanEndpoint = reqEndpoint.startsWith('/') ? reqEndpoint : `/${reqEndpoint}`;

    try {
      let parsedBody: unknown;
      if (reqMethod === 'POST' && reqBody.trim()) {
        try {
          parsedBody = JSON.parse(reqBody);
        } catch {
          parsedBody = reqBody;
        }
      }

      const result = await devopsService.proxyPlayground(activeSessionId, {
        method: reqMethod,
        path: cleanEndpoint,
        body: parsedBody,
      });
      setRestLatency(result.latencyMs ?? Math.round(performance.now() - t0));

      if (result.error) {
        // The platform reports what actually happened; it never invents a status.
        setRestStatusCode(null);
        setRestResponse(
          [
            '// NO HUBO RESPUESTA DEL SERVICIO',
            `// ${reqMethod} ${result.url || cleanEndpoint}`,
            `// ${result.error}`,
            '',
            '// Nada se ejecutó en el contenedor. Esto NO es una respuesta del API.',
          ].join('\n'),
        );
        return;
      }

      setRestStatusCode(result.statusCode ?? null);
      if (typeof result.body === 'string') {
        setRestResponse(result.body);
      } else {
        setRestResponse(JSON.stringify(result.body, null, 2));
      }
      if (result.truncated) {
        setRestResponse((prev) => `${prev}\n\n// (respuesta truncada por el proxy)`);
      }
    } catch (err) {
      // A console that invents a response is worse than one that shows nothing: the
      // operator reads `HTTP 200` and a JSON body and concludes the service answered.
      // This block used to fabricate 200/201/204 with canned bodies on ANY failure
      // (container down, wrong port, CORS, DNS), which is precisely the class of
      // dishonesty feature 012 removed from the verifier.
      const t1 = performance.now();
      setRestLatency(Math.round(t1 - t0));
      setRestStatusCode(null);
      setRestResponse(
        [
          '// NO HUBO RESPUESTA DEL SERVICIO',
          `// ${reqMethod} ${cleanEndpoint}`,
          `// ${err instanceof Error ? err.message : String(err)}`,
          '',
          '// Nada se ejecutó en el contenedor. Esto NO es una respuesta del API.',
          `// Comprueba que el contenedor está en marcha en el puerto ${hostPort}`,
          '// (pestaña DevOps: "Desplegar Localmente") y que la ruta existe.',
        ].join('\n'),
      );
    }
  };

  const currentStatus = deployment?.status || 'STOPPED';
  const isRunning = currentStatus === 'RUNNING' || currentStatus === 'HEALTHY';
  const isDockerUnavailable = currentStatus === 'DOCKER_UNAVAILABLE';

  return (
    <div className="space-y-6">
      {/* 1. Status Banner & Metrics */}
      <SingleRowCard
        title="Fase 6: DevOps, Contenerización & Despliegue Multi-Stage"
        subtitle="Dockerfile multi-stage hermético, Compose con base de datos, pipelines de CI/CD (GitHub Actions / GitLab CI) y Kubernetes"
        badge={
          <span
            className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
              isRunning
                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                : isDockerUnavailable
                ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
            }`}
          >
            {currentStatus}
          </span>
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleGenerateManifests}
              disabled={isGenerating}
              className="py-2 px-3.5 rounded-lg text-xs font-semibold bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-700 hover:bg-slate-50 transition-colors shadow-sm"
            >
              ⚙️ Generar Manifiestos DevOps
            </button>
            <button
              onClick={handleDeployLocal}
              disabled={isDeploying || isDockerUnavailable}
              className="py-2 px-4 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-all shadow-sm flex items-center gap-1.5"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>{isDeploying ? 'Desplegando...' : '🚀 Desplegar Localmente'}</span>
            </button>
            <button
              onClick={handleSmokeTest}
              disabled={isTesting || !isRunning}
              className="py-2 px-3.5 rounded-lg text-xs font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 hover:bg-emerald-100 transition-colors"
            >
              🧪 Ejecutar Smoke Test
            </button>
            <button
              onClick={handleStopContainers}
              disabled={isStopping || !isRunning}
              className="py-2 px-3.5 rounded-lg text-xs font-semibold text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-800 hover:bg-rose-100 transition-colors"
            >
              🛑 Detener
            </button>
          </div>
        }
      >
        <div className="flex flex-wrap items-center gap-4 text-xs text-slate-600 dark:text-slate-400">
          <span>
            Puerto Mapeado: <strong className="text-slate-900 dark:text-white">{deployment ? `${hostPort}:8080` : '—'}</strong>
          </span>
          <span>•</span>
          <span>
            Estado Actuator: <strong className={`font-mono ${isRunning ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-500'}`}>{deployment?.healthStatus || 'NO INICIADO'}</strong>
          </span>
          <span>•</span>
          <span>
            Base de Datos: <strong className="text-slate-900 dark:text-white">{deployment?.dbEngine || 'POSTGRESQL'}</strong>
          </span>
        </div>

        {feedback && (
          <div className="mt-2.5 p-2.5 rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 text-xs text-blue-800 dark:text-blue-200 flex items-center justify-between">
            <span>{feedback}</span>
            {isRunning && (
              <a
                href={`http://localhost:${hostPort}`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 font-semibold text-blue-600 dark:text-blue-400 hover:underline shrink-0 ml-2"
              >
                <span>Abrir en navegador</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            )}
          </div>
        )}

        {smokeResult && (
          // Styled by outcome. This was unconditional emerald with a check, so a FAILURE
          // or the SKIPPED the catch now sets both rendered as a green pass -- and
          // SKIPPED carries no latency, so it printed "undefinedms".
          <div
            className={`mt-2.5 p-2.5 rounded-lg border text-xs flex items-center justify-between ${
              smokeResult.status === 'SUCCESS'
                ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200'
                : smokeResult.status === 'SKIPPED'
                  ? 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-200'
                  : 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200'
            }`}
          >
            <div className="flex items-center gap-2">
              {smokeResult.status === 'SUCCESS' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 shrink-0" />
              )}
              <span>{smokeResult.message}</span>
            </div>
            {typeof smokeResult.latencyMs === 'number' && (
              <span className="font-mono font-bold">{smokeResult.latencyMs}ms</span>
            )}
          </div>
        )}
      </SingleRowCard>

      {/* 2. Interactive API & Database Playground */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
            <Database className="w-4 h-4 text-blue-600" />
            <span>2. Probador Visual de API & Base de Datos (Live Playground)</span>
          </h3>
          <div className="flex items-center gap-2">
            {isRunning && (
              <a
                href={`http://localhost:${hostPort}`}
                target="_blank"
                rel="noreferrer"
                className="text-xs px-2.5 py-1 rounded-lg font-semibold bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-300 dark:border-blue-800 hover:bg-blue-100 dark:hover:bg-blue-900 transition-colors flex items-center gap-1.5"
                title="Abrir página raíz y catálogo de APIs del microservicio"
              >
                <span>🌐 http://localhost:{hostPort}</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
            {/* Was unconditional literal text: "PostgreSQL + Spring Boot 3 Conectados"
                rendered green no matter what, including while the page simultaneously
                showed `Estado Actuator: NO INICIADO`. It happened to be true on the run
                that exposed it, which is exactly what makes a static claim dangerous --
                it is right often enough to be believed. It now reports the state the
                rest of the page is reporting, so the two cannot disagree on screen. */}
            <span
              className={`text-xs px-2.5 py-1 rounded-lg font-semibold border ${
                isRunning
                  ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800'
                  : 'bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-800'
              }`}
              title="Derivado del estado de despliegue, no de una comprobación propia"
            >
              {isRunning
                ? `PostgreSQL + Spring Boot 3 conectados (${currentStatus})`
                : `Sin conexión verificada — estado: ${currentStatus}`}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Gestor Visual de Órdenes */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4 shadow-sm">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              📋 Crear registro{targetEntity ? ` · ${targetEntity.name}` : ''} (CRUD en PostgreSQL)
            </h4>

            {/* The resource is chosen, not assumed: discovery lists what the service
                exposes and the fields come from that entity's own definition. */}
            {availableResources.length > 0 && (
              <div>
                <label className="block text-[11px] font-medium text-slate-500 mb-1">
                  Recurso
                </label>
                <select
                  value={crudPath}
                  onChange={(e) => {
                    setCrudPath(e.target.value);
                    setFieldValues({});
                  }}
                  className="w-full px-2.5 py-1.5 rounded border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 text-xs text-slate-900 dark:text-white focus:outline-none"
                >
                  {availableResources.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>
            )}

            <form onSubmit={handleCreateRecordSubmit} className="space-y-2">
              {createFields.length === 0 ? (
                <p className="text-[11px] text-amber-600 dark:text-amber-400">
                  {crudPath
                    ? `No se han podido determinar los campos de ${crudPath}.`
                    : 'Despliega el servicio para descubrir sus recursos.'}
                </p>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  {createFields.map((attr) => (
                    <div key={attr.name}>
                      <label className="block text-[11px] font-medium text-slate-500 mb-1">
                        {attr.name}
                        <span className="text-slate-400 font-normal">
                          {' '}({attr.javaType || attr.type})
                          {attr.nullable ? '' : ' *'}
                        </span>
                      </label>
                      <input
                        type={
                          ['Long', 'Integer', 'int', 'long', 'BigDecimal', 'Double', 'double', 'Float'].includes(
                            String(attr.javaType || attr.type),
                          )
                            ? 'number'
                            : 'text'
                        }
                        step={['BigDecimal', 'Double', 'double', 'Float'].includes(String(attr.javaType || attr.type)) ? '0.01' : undefined}
                        value={fieldValues[attr.name] ?? ''}
                        onChange={(e) =>
                          setFieldValues((prev) => ({ ...prev, [attr.name]: e.target.value }))
                        }
                        required={!attr.nullable}
                        className="w-full px-2.5 py-1.5 rounded border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 text-xs text-slate-900 dark:text-white focus:outline-none"
                      />
                    </div>
                  ))}
                </div>
              )}

              <button
                type="submit"
                disabled={createFields.length === 0}
                className="w-full py-2 rounded text-xs font-semibold bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white shadow-sm transition-colors"
              >
                💾 Guardar en PostgreSQL
              </button>
            </form>

            <div className="space-y-1.5 max-h-56 overflow-y-auto">
              <div className="text-[11px] text-slate-400 font-semibold px-1">
                Registros en Base de Datos ({orders.length}):
              </div>
              {orders.map((ord) => (
                <div
                  key={ord.id}
                  className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 text-xs flex items-center justify-between"
                >
                  <div className="min-w-0">
                    <div className="font-semibold text-slate-900 dark:text-white font-mono">
                      #{ord.id}
                    </div>
                    {/* Was `ord.totalAmount.toFixed(2)`, which throws on any record whose
                        entity has no `totalAmount` -- i.e. every service but the sample. */}
                    <div className="text-[11px] text-slate-500 truncate">
                      {JSON.stringify(ord.submitted ?? {})} · {ord.createdAt}
                    </div>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                    {ord.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Consola de Peticiones REST */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4 shadow-sm">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              🧪 Consola de Peticiones REST (Estilo Postman / Swagger)
            </h4>

            <div className="flex gap-2">
              <select
                value={reqMethod}
                onChange={(e) => setReqMethod(e.target.value as any)}
                className="px-2.5 py-1.5 rounded border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 text-xs font-mono font-bold text-slate-900 dark:text-white focus:outline-none"
              >
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="DELETE">DELETE</option>
              </select>
              <input
                type="text"
                value={reqEndpoint}
                onChange={(e) => setReqEndpoint(e.target.value)}
                className="flex-1 px-2.5 py-1.5 rounded border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 text-xs font-mono text-slate-900 dark:text-white focus:outline-none"
              />
              <button
                type="button"
                onClick={handleSendCustomRest}
                className="px-4 py-1.5 rounded text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-sm transition-colors flex items-center gap-1.5"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Enviar</span>
              </button>
            </div>

            {reqMethod === 'POST' && (
              <textarea
                rows={3}
                value={reqBody}
                onChange={(e) => setReqBody(e.target.value)}
                className="w-full p-2.5 rounded border border-slate-300 dark:border-slate-700 bg-slate-950 text-slate-100 font-mono text-xs focus:outline-none"
              />
            )}

            <div className="rounded-lg bg-slate-950 p-3 text-xs font-mono text-slate-200 h-44 overflow-y-auto">
              <div className="flex items-center justify-between text-[11px] text-slate-500 border-b border-slate-800 pb-1 mb-2">
                <span>
                  HTTP Status:{' '}
                  {restStatusCode ? (
                    <strong className="text-emerald-400 font-bold">{restStatusCode}</strong>
                  ) : (
                    '—'
                  )}
                </span>
                {restLatency && <span>Latencia: {restLatency}ms</span>}
              </div>
              <pre className="whitespace-pre leading-relaxed text-emerald-400">
                {restResponse || '// Presiona "Enviar" para ejecutar la petición REST'}
              </pre>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Live Terminal View (Logs) */}
      <div className="space-y-2">
        <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
          <Terminal className="w-4 h-4 text-slate-600" />
          <span>3. Terminal de Despliegue en Vivo (Docker & Spring Logs)</span>
        </h3>

        <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs text-slate-300 h-48 overflow-y-auto space-y-1 shadow-inner">
          {terminalLogs.length === 0 ? (
            <div className="text-slate-500 italic py-2">
              [system] Esperando inicio del contenedor. Presione "🚀 Desplegar Localmente" para compilar la imagen Docker y lanzar los logs del contenedor.
            </div>
          ) : (
            terminalLogs.map((line, idx) => (
              <div key={idx} className="hover:bg-slate-900/50 py-0.5">
                {line}
              </div>
            ))
          )}
        </div>
      </div>

      {/* 4. Manifest Inspector Accordion Tabs */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
            <FileCode className="w-4 h-4 text-blue-600" />
            <span>4. Inspección de Manifiestos Generados</span>
          </h3>

          <div className="flex flex-wrap gap-1 bg-slate-200 dark:bg-slate-800 p-1 rounded-lg text-xs font-semibold">
            <button
              onClick={() => setActiveManifestTab('docker')}
              className={`px-3 py-1 rounded-md transition-all ${
                activeManifestTab === 'docker'
                  ? 'bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm'
                  : 'text-slate-600 dark:text-slate-400'
              }`}
            >
              🐳 Dockerfile & Ignore
            </button>
            <button
              onClick={() => setActiveManifestTab('compose')}
              className={`px-3 py-1 rounded-md transition-all ${
                activeManifestTab === 'compose'
                  ? 'bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm'
                  : 'text-slate-600 dark:text-slate-400'
              }`}
            >
              🐙 Docker Compose
            </button>
            <button
              onClick={() => setActiveManifestTab('cicd')}
              className={`px-3 py-1 rounded-md transition-all ${
                activeManifestTab === 'cicd'
                  ? 'bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm'
                  : 'text-slate-600 dark:text-slate-400'
              }`}
            >
              🔄 CI/CD Pipelines
            </button>
            <button
              onClick={() => setActiveManifestTab('k8s')}
              className={`px-3 py-1 rounded-md transition-all ${
                activeManifestTab === 'k8s'
                  ? 'bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm'
                  : 'text-slate-600 dark:text-slate-400'
              }`}
            >
              ☸️ Kubernetes Producción
            </button>
          </div>
        </div>

        {activeManifestTab === 'docker' && (
          <div className="space-y-3">
            {devopsFiles['Dockerfile'] ? (
              <CodeViewer code={devopsFiles['Dockerfile']} language="dockerfile"
                          filename="Dockerfile (Multi-Stage JRE 21 LTS)" maxHeight="max-h-72" />
            ) : (
              <MissingArtifact path="Dockerfile" />
            )}
            {devopsFiles['.dockerignore'] ? (
              <CodeViewer code={devopsFiles['.dockerignore']} language="text"
                          filename=".dockerignore" maxHeight="max-h-40" />
            ) : (
              <MissingArtifact path=".dockerignore" />
            )}
          </div>
        )}

        {activeManifestTab === 'compose' && (
          devopsFiles['docker-compose.yml'] ? (
            <CodeViewer code={devopsFiles['docker-compose.yml']} language="yaml"
                        filename="docker-compose.yml (Spring Boot + PostgreSQL)" maxHeight="max-h-80" />
          ) : (
            <MissingArtifact path="docker-compose.yml" />
          )
        )}

        {activeManifestTab === 'cicd' && (
          <div className="space-y-3">
            <div className="flex gap-2 text-xs font-semibold">
              <button
                onClick={() => setActiveCicdSubtab('github')}
                className={`py-1 px-3 rounded-md ${
                  activeCicdSubtab === 'github'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                }`}
              >
                GitHub Actions (.github/workflows/ci-cd.yml)
              </button>
              <button
                onClick={() => setActiveCicdSubtab('gitlab')}
                className={`py-1 px-3 rounded-md ${
                  activeCicdSubtab === 'gitlab'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                }`}
              >
                GitLab CI (.gitlab-ci.yml)
              </button>
            </div>

            {activeCicdSubtab === 'github' ? (
              devopsFiles['.github/workflows/ci-cd.yml'] ? (
                <CodeViewer code={devopsFiles['.github/workflows/ci-cd.yml']} language="yaml"
                            filename=".github/workflows/ci-cd.yml" maxHeight="max-h-72" />
              ) : (
                <MissingArtifact path=".github/workflows/ci-cd.yml" />
              )
            ) : devopsFiles['.gitlab-ci.yml'] ? (
              <CodeViewer code={devopsFiles['.gitlab-ci.yml']} language="yaml"
                          filename=".gitlab-ci.yml" maxHeight="max-h-72" />
            ) : (
              <MissingArtifact path=".gitlab-ci.yml" />
            )}
          </div>
        )}

        {activeManifestTab === 'k8s' && (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2 text-xs font-semibold">
              <button
                onClick={() => setActiveK8sSubtab('deployment')}
                className={`py-1 px-3 rounded-md ${
                  activeK8sSubtab === 'deployment'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                }`}
              >
                deployment.yaml
              </button>
              <button
                onClick={() => setActiveK8sSubtab('service')}
                className={`py-1 px-3 rounded-md ${
                  activeK8sSubtab === 'service'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                }`}
              >
                service.yaml
              </button>
              <button
                onClick={() => setActiveK8sSubtab('configmap')}
                className={`py-1 px-3 rounded-md ${
                  activeK8sSubtab === 'configmap'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                }`}
              >
                configmap.yaml
              </button>
              <button
                onClick={() => setActiveK8sSubtab('ingress')}
                className={`py-1 px-3 rounded-md ${
                  activeK8sSubtab === 'ingress'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                }`}
              >
                ingress.yaml
              </button>
            </div>

            {k8sManifests[K8S_FILES[activeK8sSubtab]] ? (
              <CodeViewer
                code={k8sManifests[K8S_FILES[activeK8sSubtab]]}
                language="yaml"
                filename={`k8s/${K8S_FILES[activeK8sSubtab]}`}
                maxHeight="max-h-72"
              />
            ) : (
              // Was four hardcoded SAMPLE_K8S_* constants, from an unrelated
              // `order-service`: the tab showed a canned manifest whatever the session
              // contained, while the real files sat on disk. A viewer that cannot tell
              // "not generated" from "generated differently" is worse than an empty one.
              <div className="rounded-lg border border-dashed border-slate-300 dark:border-slate-700 p-6 text-center">
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  No hay <span className="font-mono">k8s/{K8S_FILES[activeK8sSubtab]}</span> en
                  este workspace.
                </p>
                <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                  Pulse <strong>Generar Manifiestos DevOps</strong> para producirlo.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
