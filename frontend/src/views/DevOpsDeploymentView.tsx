import React, { useState, useEffect, useRef } from 'react';
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
import { devopsService, LocalDeploymentSession, SmokeTestResult, DockerCapabilityReport } from '../services/devopsService';
import { exportService } from '../services/exportService';
import { sessionService } from '../services/sessionService';
import { subscribeDeploymentLogs, LogConnection } from '../services/deploymentLogStream';



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
  const { activeSessionId, activeSession, projectOverview, reloadCurrentOverview, refreshSessions } = useStudio();

  const [deployment, setDeployment] = useState<LocalDeploymentSession | null>(null);
  const currentDeployment = useRef<LocalDeploymentSession | null>(null);
  currentDeployment.current = deployment;
  const [diagnostics, setDiagnostics] = useState<DockerCapabilityReport | null>(null);
  const [isDiagnosing, setIsDiagnosing] = useState(false);
  const sessionRef = useRef(activeSessionId);
  const sessionRevision = useRef(0);
  if (sessionRef.current !== activeSessionId) sessionRevision.current += 1;
  sessionRef.current = activeSessionId;
  const runtimeRef = useRef('');
  const statusVersion = useRef(0);
  runtimeRef.current = `${activeSessionId}|${deployment?.containerId}|${deployment?.hostPort}`;
  const requestScope = (checkRuntime = false) => {
    statusVersion.current += 1;
    const revision = sessionRevision.current;
    const runtime = runtimeRef.current;
    return () => revision === sessionRevision.current && (!checkRuntime || runtime === runtimeRef.current);
  };

  const [hostPort, setHostPort] = useState<number>(8080);
  const [projectConfiguration, setProjectConfiguration] = useState<{ databaseEngine: string; hostPort: number; buildTool: string; buildDirectory: string } | null>(null);
  const configurationLoaded = useRef(false);
  const portEdited = useRef(false);
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
  const [isCancelling, setIsCancelling] = useState(false);
  const [deleteDataConfirmed, setDeleteDataConfirmed] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [isRequesting, setIsRequesting] = useState(false);
  const [smokeResult, setSmokeResult] = useState<SmokeTestResult | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [terminalLogs, setTerminalLogs] = useState<string[]>([]);
  const [logConnection, setLogConnection] = useState<LogConnection>('connecting');

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
    const isCurrent = requestScope();
    if (!activeSessionId) {
      setDeployment(null);
      setTerminalLogs([]);
      return;
    }
    try {
      const s = await devopsService.getDeploymentStatus(activeSessionId);
      if (!isCurrent()) return;
      if (s) {
        setDeployment(s);
        if (s.hostPort && (s.containerId || !configurationLoaded.current) && !portEdited.current) setHostPort(s.hostPort);
      } else {
        setDeployment(null);
      }
    } catch {
      if (isCurrent()) setDeployment(null);
    }
  };

  useEffect(() => {
    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    setDeployment(null);
    setHostPort(8080);
    setProjectConfiguration(null);
    configurationLoaded.current = false;
    portEdited.current = false;
    setTerminalLogs([]);
    setLogConnection('connecting');
    setSmokeResult(null);
    setFeedback(null);
    setDiagnostics(null);
    setIsDiagnosing(false);
    setIsGenerating(false);
    setIsDeploying(false);
    setIsStopping(false);
    setIsCancelling(false);
    setDeleteDataConfirmed(false);
    setIsTesting(false);
    setIsRequesting(false);
    setOrders([]);
    setFieldValues({});
    setCrudPath('');
    setAvailableResources([]);
    setModelEntities([]);
    setDevopsFiles({});
    setK8sManifests({});
    setRestResponse(null);
    setRestLatency(null);
    setRestStatusCode(null);
    setReqEndpoint('/actuator/health');
    setReqBody('{}');
    if (!activeSessionId) return;
    if (typeof devopsService.getConfiguration === 'function') {
      devopsService.getConfiguration(activeSessionId).then(config => {
        if (cancelled || !config) return;
        setProjectConfiguration(config);
        configurationLoaded.current = true;
        const running = currentDeployment.current?.containerId && ['RUNNING', 'HEALTHY', 'DEGRADED'].includes(currentDeployment.current.status);
        if (!portEdited.current && !running) setHostPort(config.hostPort);
      }).catch(error => {
        if (!cancelled) setFeedback(error?.response?.data?.detail || 'No se pudo leer la configuración local del proyecto.');
      });
    }
    const poll = async () => {
      const version = statusVersion.current;
      try {
        const status = await devopsService.getDeploymentStatus(activeSessionId);
        if (!cancelled && version === statusVersion.current) {
          setDeployment(status);
          if ((status.containerId || !configurationLoaded.current) && !portEdited.current) setHostPort(status.hostPort);
        }
      } catch { if (!cancelled && version === statusVersion.current) setDeployment(null); }
      if (!cancelled) pollTimer = setTimeout(poll, 3000);
    };
    poll();
    const unsubscribe = subscribeDeploymentLogs(activeSessionId, setTerminalLogs, setLogConnection);
    return () => { cancelled = true; clearTimeout(pollTimer); unsubscribe(); };
  }, [activeSessionId]);

  useEffect(() => {
    setOrders([]);
    setRestResponse(null);
    setRestLatency(null);
    setRestStatusCode(null);
    setSmokeResult(null);
    setIsRequesting(false);
  }, [activeSessionId, deployment?.containerId, deployment?.hostPort]);

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
    if (!activeSessionId || isBusy) return;
    const isCurrent = requestScope();
    setIsGenerating(true);
    setFeedback(null);
    try {
      // The response was previously discarded -- `await` with no assignment -- which is
      // how the Kubernetes tab ended up rendering samples instead of these files.
      const bundle = await devopsService.generateManifests(activeSessionId, projectConfiguration?.databaseEngine, portEdited.current ? hostPort : undefined);
      if (!isCurrent()) return;
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
      if (!isCurrent()) return;
      setFeedback(err.response?.data?.detail || 'Error al generar manifiestos DevOps.');
    } finally {
      if (isCurrent()) setIsGenerating(false);
    }
  };

  const handleDeployLocal = async () => {
    if (!activeSessionId || isBusy || isSourceOnly) return;
    const isCurrent = requestScope();
    setIsDeploying(true);
    setFeedback(null);
    try {
      const res = await devopsService.deployLocal(activeSessionId, portEdited.current ? hostPort : undefined, true);
      if (!isCurrent()) return;
      setSmokeResult(null);
      setDeployment(res);
      setHostPort(res.hostPort);
      setFeedback(res.errorMessage || `Estado del despliegue: ${res.status}. Puerto efectivo: ${res.hostPort}.`);
      await reloadCurrentOverview();
    } catch (err: any) {
      if (isCurrent()) setFeedback(err.response?.data?.detail || err.message || 'No se pudo confirmar el despliegue. Consulte el estado y reintente.');
    } finally {
      if (isCurrent()) setIsDeploying(false);
    }
  };

  const handleStopContainers = async () => {
    if (!activeSessionId || isBusy || !hasRuntime) return;
    const isCurrent = requestScope();
    setIsStopping(true);
    try {
      const res = await devopsService.stopContainers(activeSessionId);
      if (!isCurrent()) return;
      setDeployment(res);
      setSmokeResult(null);
      setRestResponse(null);
      setOrders([]);
      setFeedback(res.status === 'STOPPED' ? 'Contenedores detenidos. Datos conservados.' : res.errorMessage || `Estado: ${res.status}`);
      await reloadCurrentOverview();
    } catch (err: any) {
      if (!isCurrent()) return;
      // Report the real outcome. This used to say "Contenedores detenidos." even
      // when the stop request failed, so the UI claimed a state the host was not in.
      setFeedback(
        `No se pudieron detener los contenedores: ${err?.message || String(err)}. ` +
        `El estado mostrado puede no reflejar el host.`,
      );
    } finally {
      if (isCurrent()) setIsStopping(false);
    }
  };

  const handleSmokeTest = async () => {
    if (!activeSessionId || isBusy || !hasRuntime) return;
    const isCurrent = requestScope();
    setIsTesting(true);
    try {
      const res = await devopsService.runSmokeTest(activeSessionId, hostPort);
      if (!isCurrent()) return;
      setSmokeResult(res);
      await fetchStatus();
    } catch (err) {
      if (!isCurrent()) return;
      // SKIPPED, not SUCCESS. This used to fabricate a pass -- status 'SUCCESS',
      // httpStatusCode 200, latencyMs 14, "Endpoint de salud verificado" -- on any
      // failure, so pressing "Ejecutar Smoke Test" reported a healthy service that
      // was never contacted. It is the same three-state discipline the diagnostics
      // use: *verified*, *verified with findings*, and *not evaluable* must never be
      // conflated, and "the check could not run" is the third one.
      setSmokeResult({
        passed: false, statusCode: 0, testUrl: '',
        sessionId: activeSessionId,
        endpointTested: `http://localhost:${hostPort}/actuator/health`,
        status: 'SKIPPED',
        message:
          `Smoke test NO ejecutado: ${err instanceof Error ? err.message : String(err)}. ` +
          `No se contactó ningún endpoint, así que esto no dice nada sobre el servicio ` +
          `(ni bueno ni malo). Comprueba que el contenedor está desplegado.`,
      });
      await fetchStatus();
    } finally {
      if (isCurrent()) setIsTesting(false);
    }
  };

  const handleLifecycle = async (cleanup: boolean) => {
    if (!activeSessionId || isSourceOnly || isBusy || (cleanup && !deleteDataConfirmed)) return;
    const isCurrent = requestScope();
    setIsDeploying(true);
    setSmokeResult(null); setRestResponse(null); setOrders([]);
    try {
      const result = cleanup ? await devopsService.cleanupLocal(activeSessionId, true) : await devopsService.restartLocal(activeSessionId);
      if (!isCurrent()) return;
      setDeployment(result); setHostPort(result.hostPort);
      setFeedback(result.errorMessage || result.message || `Estado: ${result.status}`);
      setDeleteDataConfirmed(false);
      await reloadCurrentOverview();
    } catch (err: any) {
      if (isCurrent()) setFeedback(err.response?.data?.detail || err.message || 'Operación no confirmada. Consulte el estado.');
    } finally { if (isCurrent()) setIsDeploying(false); }
  };

  const handleCancelOperation = async () => {
    if (!activeSessionId || isSourceOnly || !deployment?.operationId || deployment.finishedAt || deployment.cancelRequested || isCancelling) return;
    const isCurrent = requestScope();
    setIsCancelling(true);
    try {
      const result = await devopsService.cancelLocal(activeSessionId, deployment.operationId);
      if (!isCurrent()) return;
      setDeployment(result);
      setFeedback(result.errorMessage || result.message || 'Cancelación solicitada; espere el estado final.');
    } catch (err: any) {
      if (isCurrent()) setFeedback(err.response?.data?.detail || err.message || 'Cancelación no confirmada. Consulte el estado.');
    } finally { if (isCurrent()) setIsCancelling(false); }
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

  //: Java time types, and the input control that can produce a value for each.
  //:
  //: These were plain text boxes. An `Instant` field is `@NotNull` on the generated entity,
  //: so it genuinely has to be sent, and Jackson rejects anything that is not ISO-8601 --
  //: typing "11" produced a 500 with no explanation of what was wrong. A picker cannot
  //: produce an unparseable value, which removes the trap rather than documenting it.
  const temporalInputType = (javaType: string): 'datetime-local' | 'date' | null => {
    if (javaType === 'Instant' || javaType === 'LocalDateTime' || javaType === 'OffsetDateTime') {
      return 'datetime-local';
    }
    if (javaType === 'LocalDate') return 'date';
    return null;
  };

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
    if (temporalInputType(t)) {
      // `datetime-local` yields "2026-09-30T12:00" with no zone. Instant is an instant on
      // the timeline, so it needs one; LocalDateTime is not, so it must not gain one.
      const parsed = new Date(raw);
      if (Number.isNaN(parsed.getTime())) {
        throw new Error(`${attr.name} debe ser una fecha válida`);
      }
      if (t === 'LocalDateTime') {
        return raw.length === 16 ? `${raw}:00` : raw;
      }
      return parsed.toISOString();
    }
    return raw;
  };

  const handleCreateRecordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeSessionId || isBusy || !hasRuntime) return;
    const isCurrent = requestScope(true);
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
    setIsRequesting(true);
    try {
      // Through the platform, not the browser: a direct cross-origin call is rejected
      // by the generated service (no CORS), and `crudPath` is the path its controllers
      // actually expose rather than a hardcoded /api/v1/orders.
      const result = await devopsService.proxyPlayground(activeSessionId, {
        method: 'POST',
        path: crudPath,
        body: payload,
      });
      if (!isCurrent()) return;
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
    } catch (err: any) {
      if (!isCurrent()) return;
      // The platform refuses an undeployed session with a 400 and a reason. Reading only
      // `err.message` reduced that to "Request failed with status code 400" and threw the
      // explanation away -- which is the whole reason the platform now states it.
      const detail = err?.response?.data?.detail;
      failure =
        (typeof detail === 'string' ? detail : detail?.message) ||
        (err instanceof Error ? err.message : String(err));
    } finally {
      if (isCurrent()) setIsRequesting(false);
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
    if (!activeSessionId || isBusy || !hasRuntime) return;
    const isCurrent = requestScope(true);
    setIsRequesting(true);
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
      if (!isCurrent()) return;
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
            '// No se recibió una respuesta confirmada; la operación podría haberse ejecutado.',
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
      if (!isCurrent()) return;
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
          '// No se recibió una respuesta confirmada; la operación podría haberse ejecutado.',
          `// Comprueba que el contenedor está en marcha en el puerto ${hostPort}`,
          '// (pestaña DevOps: "Desplegar Localmente") y que la ruta existe.',
        ].join('\n'),
      );
    } finally {
      if (isCurrent()) setIsRequesting(false);
    }
  };

  const currentStatus = deployment?.status || 'IDLE';
  const isRunning = currentStatus === 'RUNNING' || currentStatus === 'HEALTHY';
  const isSourceOnly = activeSession?.executionMode === 'SOURCE_ONLY' || currentStatus === 'SKIPPED_BY_CHOICE';
  const isDockerUnavailable = !isSourceOnly && (currentStatus === 'DOCKER_UNAVAILABLE' || (!deployment && activeSession?.verificationOutcome === 'ENVIRONMENT_UNAVAILABLE'));
  const isBusy = !activeSessionId || isGenerating || isDeploying || isStopping || isCancelling || isTesting || isDiagnosing || isRequesting || currentStatus === 'BUILDING' || Boolean(deployment?.operationKind && !deployment.finishedAt);
  const hasRuntime = !isSourceOnly && (isRunning || currentStatus === 'DEGRADED');

  const handleExecutionChoice = async (mode: 'SOURCE_ONLY' | 'DOCKER') => {
    if (!activeSessionId || isBusy) return;
    const isCurrent = requestScope();
    setIsTesting(true);
    try {
      await sessionService.changeExecutionMode(activeSessionId, mode);
      if (!isCurrent()) return;
      const result = await sessionService.verify(activeSessionId);
      if (!isCurrent()) return;
      setFeedback(result.status === 'COMPLETED' ? (mode === 'SOURCE_ONLY' ? 'Fuentes disponibles; ejecución omitida por elección.' : 'Verificación completada.') : 'Verificación pendiente. Consulte el estado de la sesión.');
      await Promise.all([fetchStatus(), refreshSessions(), reloadCurrentOverview()]);
    } catch (err: any) { if (isCurrent()) setFeedback(err.response?.data?.detail || err.message); }
    finally { if (isCurrent()) setIsTesting(false); }
  };

  return (
    <div className="space-y-6">
      {!isSourceOnly && deployment?.operationKind && <div role="status" className="p-3 border rounded text-sm">
        Operación: {deployment.operationKind} · Etapa: {deployment.operationPhase || 'Pendiente'}
        {deployment.finishedAt ? ' · Finalizada' : ' · En curso'}
        {!deployment.finishedAt && <button className="ml-3 underline" disabled={isCancelling || deployment.cancelRequested}
          onClick={handleCancelOperation}>{deployment.cancelRequested ? 'Cancelación solicitada' : 'Cancelar operación local'}</button>}
        {deployment.cancelRequested && <p>La solicitud no confirma que las tareas de Docker hayan terminado. Consulte el resultado final.</p>}
      </div>}
      {isDockerUnavailable && <div role="status" className="p-4 rounded-xl border border-amber-200 bg-amber-50 text-amber-900 dark:bg-amber-950/30 dark:text-amber-200 text-sm">
        Despliegue no ejecutado: Docker no está disponible. Puede generar los manifiestos y continuar con la entrega del código; el servicio y las pruebas de ejecución no se muestran como aprobados.
        <div className="flex gap-3 mt-3">
          <button disabled={isBusy} onClick={() => handleExecutionChoice('DOCKER')}>Reintentar</button>
          <button disabled={isBusy} onClick={() => handleExecutionChoice('SOURCE_ONLY')}>Continuar sin Docker</button>
        </div>
      </div>}
      {isSourceOnly && <div role="status" className="p-4 border rounded">{activeSession?.verificationOutcome === 'FAILED' ? 'Entrega de fuentes sin nueva ejecución. Las pruebas anteriores fallaron y su resultado se conserva.' : 'Sesión sin Docker: no se solicita ejecución. Puede exportar las fuentes auditadas; consulte el estado de verificación para conocer resultados anteriores.'}
        <button className="ml-3 underline" disabled={isBusy} onClick={() => handleExecutionChoice('DOCKER')}>Activar Docker y verificar</button>
      </div>}
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
            <label className="text-xs">Puerto local
              <input aria-label="Puerto local" type="number" min={1024} max={65535} value={hostPort}
                disabled={isBusy || hasRuntime} className="ml-2 w-24 rounded border p-1"
                onChange={event => { portEdited.current = true; setHostPort(Number(event.target.value)); }} />
            </label>
            {projectConfiguration && <span className="text-xs text-slate-500">
              Build: {projectConfiguration.buildTool} · BD configurada: {projectConfiguration.databaseEngine}
            </span>}
            <button disabled={isSourceOnly || isBusy} onClick={async () => {
              if (!activeSessionId) return;
              const identity = activeSessionId;
              const isCurrent = requestScope();
              setIsDiagnosing(true);
              try {
                const result = await devopsService.getDiagnostics(identity);
                if (isCurrent()) setDiagnostics(result);
              } catch {
                if (isCurrent()) setFeedback('No se pudo consultar el diagnóstico Docker. Reintente.');
              } finally {
                if (isCurrent()) setIsDiagnosing(false);
              }
            }} className="py-2 px-3 border rounded text-xs">{isDiagnosing ? 'Consultando entorno...' : 'Diagnosticar Docker'}</button>
            {diagnostics?.sessionId === activeSessionId && <div className="text-xs space-y-2" aria-label="Diagnóstico Docker">
              {diagnostics.checks.map((check, index) => <p key={index}>{check.status === 'AVAILABLE' ? '✓' : '•'} {check.detail}</p>)}
              <p>Este diagnóstico no sustituye la compilación ni las pruebas offline del microservicio.</p>
            </div>}
            <button disabled={isSourceOnly || isBusy} onClick={async () => {
              if (!activeSessionId) return;
              const isCurrent = requestScope();
              setIsDeploying(true);
              try { const result = await devopsService.prepareLocal(activeSessionId); if (!isCurrent()) return; setDeployment(result); setFeedback(result.errorMessage || result.message || 'Preparación inicial solicitada.'); }
              catch (err: any) { if (isCurrent()) setFeedback(err.response?.data?.detail || err.message); }
              finally { if (isCurrent()) setIsDeploying(false); }
            }} className="py-2 px-3 border rounded text-xs">Preparar Docker con conexión</button>
            <button disabled={isSourceOnly || isBusy} onClick={() => handleExecutionChoice('DOCKER')} className="py-2 px-3 border rounded text-xs">Verificar fuentes con Docker</button>
            <button
              onClick={handleGenerateManifests}
              disabled={isBusy}
              className="py-2 px-3.5 rounded-lg text-xs font-semibold bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-700 hover:bg-slate-50 transition-colors shadow-sm"
            >
              ⚙️ Generar Manifiestos DevOps
            </button>
            <button
              onClick={handleDeployLocal}
              disabled={isBusy || isSourceOnly}
              className="py-2 px-4 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-all shadow-sm flex items-center gap-1.5"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>{isDeploying ? 'Desplegando...' : '🚀 Desplegar Localmente'}</span>
            </button>
            <button
              onClick={handleSmokeTest}
              disabled={isBusy || !hasRuntime}
              className="py-2 px-3.5 rounded-lg text-xs font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 hover:bg-emerald-100 transition-colors"
            >
              🧪 Ejecutar Smoke Test
            </button>
            <button
              onClick={handleStopContainers}
              disabled={isBusy || !hasRuntime}
              className="py-2 px-3.5 rounded-lg text-xs font-semibold text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-800 hover:bg-rose-100 transition-colors"
            >
              🛑 Detener
            </button>
            <button disabled={isBusy || isSourceOnly || isDockerUnavailable || !deployment?.containerId}
              onClick={() => handleLifecycle(false)} className="py-2 px-3 border rounded text-xs">Reiniciar conservando datos</button>
          </div>
        }
      >
        <div className="flex flex-wrap items-center gap-4 text-xs text-slate-600 dark:text-slate-400">
          {deployment?.message && <span>{deployment.message}</span>}
          {deployment?.errorMessage && <span role="alert">{deployment.errorMessage}</span>}
          <span>{isSourceOnly ? 'Despliegue omitido por elección.' : currentStatus === 'BUILDING' ? 'Operación en curso; aún no aprobada.' : currentStatus === 'HEALTHY' ? 'Salud del servicio aprobada.' : currentStatus === 'FAILED' ? 'Despliegue fallido.' : currentStatus === 'DEGRADED' ? 'Servicio degradado; consulte salud y logs.' : 'Despliegue pendiente o detenido.'}</span>
          <span>
            Puerto Mapeado: <strong className="text-slate-900 dark:text-white">{deployment ? `${hostPort}:8080` : '—'}</strong>
          </span>
          <span>•</span>
          <span>
            Estado Actuator: <strong className={`font-mono ${isRunning ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-500'}`}>{deployment?.healthStatus || 'NO INICIADO'}</strong>
          </span>
          <span>•</span>
          <span>
            Base de Datos: <strong className="text-slate-900 dark:text-white">{deployment?.dbEngine || 'No confirmado'}</strong>
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

        {!isSourceOnly && activeSessionId && <div className="mt-3 space-y-2 text-xs">
          <label className="flex gap-2 items-center">
            <input type="checkbox" checked={deleteDataConfirmed} disabled={isBusy}
              onChange={event => setDeleteDataConfirmed(event.target.checked)} />
            Confirmo eliminar los datos y recursos Docker de esta sesión.
          </label>
          <button disabled={isBusy || !deleteDataConfirmed || isDockerUnavailable}
            onClick={() => handleLifecycle(true)} className="py-2 px-3 border rounded text-rose-700">Eliminar datos y recursos de esta sesión</button>
        </div>}

        {smokeResult && (
          // Styled by outcome. This was unconditional emerald with a check, so a FAILURE
          // or the SKIPPED the catch now sets both rendered as a green pass -- and
          // SKIPPED carries no latency, so it printed "undefinedms".
          <div
            className={`mt-2.5 p-2.5 rounded-lg border text-xs flex items-center justify-between ${
              smokeResult.passed
                ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200'
                : smokeResult.status === 'SKIPPED'
                  ? 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-200'
                  : 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200'
            }`}
          >
            <div className="flex items-center gap-2">
              {smokeResult.passed ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 shrink-0" />
              )}
              <span>{smokeResult.details || smokeResult.message}</span>
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
                ? `Aplicación ${currentStatus} · BD ${deployment?.dbEngine || 'no confirmada'}`
                : `Sin conexión verificada — estado: ${currentStatus}`}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Gestor Visual de Órdenes */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4 shadow-sm">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              📋 Crear registro{targetEntity ? ` · ${targetEntity.name}` : ''} (CRUD)
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
                        {String(attr.javaType || attr.type) === 'Instant' && (
                          <span className="block text-[10px] text-slate-400 font-normal">
                            se envía como ISO-8601 UTC
                          </span>
                        )}
                      </label>
                      <input
                        type={
                          temporalInputType(String(attr.javaType || attr.type)) ??
                          (['Long', 'Integer', 'int', 'long', 'BigDecimal', 'Double', 'double', 'Float'].includes(
                            String(attr.javaType || attr.type),
                          )
                            ? 'number'
                            : 'text')
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
                disabled={createFields.length === 0 || isBusy || !hasRuntime}
                className="w-full py-2 rounded text-xs font-semibold bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white shadow-sm transition-colors"
              >
                💾 Guardar registro
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
                disabled={isBusy || !hasRuntime}
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
          <span>3. Registro de Despliegue</span>
        </h3>
        <p role="status" className="text-xs text-slate-500">
          {!activeSessionId ? 'Selecciona una sesión para consultar su registro.' : logConnection === 'connected' ? 'Conectado al registro de despliegue.' :
            logConnection === 'recovering' ? 'Recuperando conexión e historial…' : 'Conectando al registro…'}
        </p>

        <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs text-slate-300 h-48 overflow-y-auto space-y-1 shadow-inner">
          {terminalLogs.length === 0 ? (
            <div className="text-slate-500 italic py-2">
              No hay mensajes de despliegue registrados para esta sesión.
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
                        filename="docker-compose.yml" maxHeight="max-h-80" />
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
