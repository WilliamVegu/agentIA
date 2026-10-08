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
import { sessionService,ExecutionMode } from '../services/sessionService';
import { ExecutionModeSelector } from '../components/common/ExecutionModeSelector';
import { devopsService, LocalDeploymentSession, SmokeTestResult, ManifestBundle } from '../services/devopsService';

export const DevOpsDeploymentView: React.FC = () => {
  const { activeSessionId, activeSession, refreshSessions, reloadCurrentOverview, projectOverview } = useStudio();
  const mode = activeSession?.executionMode || projectOverview?.executionMode;
  const runtimeAllowed = mode === 'DOCKER';
  const [isVerifying,setIsVerifying]=useState(false);

  const [manifests, setManifests] = useState<ManifestBundle | null>(null);
  const [deployment, setDeployment] = useState<LocalDeploymentSession | null>(null);

  const [hostPort, setHostPort] = useState<number>(0);
  const [activeManifestTab, setActiveManifestTab] = useState<'docker' | 'compose' | 'cicd' | 'k8s'>('docker');
  const [activeCicdSubtab, setActiveCicdSubtab] = useState<'github' | 'gitlab'>('github');
  const [activeK8sSubtab, setActiveK8sSubtab] = useState<'deployment' | 'service' | 'configmap' | 'ingress'>('deployment');

  const [isGenerating, setIsGenerating] = useState(false);
  const [isDeploying, setIsDeploying] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [smokeResult, setSmokeResult] = useState<SmokeTestResult | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [terminalLogs, setTerminalLogs] = useState<string[]>([]);

  // REST Console State
  const [reqMethod, setReqMethod] = useState<'GET' | 'POST' | 'DELETE'>('GET');
  const [reqEndpoint, setReqEndpoint] = useState('/q/health');
  const [reqBody, setReqBody] = useState('{}');
  const [restResponse, setRestResponse] = useState<string | null>(null);
  const [restLatency, setRestLatency] = useState<number | null>(null);
  const [restStatusCode, setRestStatusCode] = useState<number | null>(null);

  const currentSession = useRef(activeSessionId);
  currentSession.current = activeSessionId;
  const fetchStatus = async () => {
    const requestedSession = activeSessionId;
    if (!activeSessionId) {
      setDeployment(null);
      setTerminalLogs([]);
      return;
    }
    try {
      const s = await devopsService.getDeploymentStatus(activeSessionId);
      if (currentSession.current !== requestedSession) return;
      if (s) {
        setDeployment(s);
        if (s.hostPort) setHostPort(s.hostPort);
      } else {
        setDeployment(null);
      }
      const logs = await devopsService.getLogs(activeSessionId);
      if (currentSession.current !== requestedSession) return;
      if (logs && logs.length > 0) {
        setTerminalLogs(logs);
      }
    } catch {
      if (currentSession.current === requestedSession) setDeployment(null);
    }
  };

  useEffect(() => {
    let cancelled = false;
    setHostPort(0); setManifests(null); setSmokeResult(null); setRestResponse(null); setDeployment(null); setTerminalLogs([]);
    if (activeSessionId) {
      fetchStatus();
      devopsService.getConfiguration(activeSessionId).then(config => { if (!cancelled && config.hostPort) setHostPort(config.hostPort); }).catch(() => {});
      devopsService.getManifests(activeSessionId).then(result => { if (!cancelled) setManifests(result); }).catch(() => {});
    }
    return () => { cancelled = true; };
  }, [activeSessionId]);

  useEffect(() => {
    if (!activeSessionId || !['BUILDING','STARTING'].includes(deployment?.status || '')) return;
    const timer = window.setInterval(() => { void fetchStatus(); }, 2000);
    return () => window.clearInterval(timer);
  }, [activeSessionId, deployment?.status]);

  const handleModeChange = async (next: ExecutionMode) => {
    if (!activeSessionId) return;
    try {
      await sessionService.changeExecutionMode(activeSessionId,next);
      await Promise.all([refreshSessions(),reloadCurrentOverview()]);
      setFeedback('Modo de ejecución guardado.');
    } catch (error:any) { setFeedback(error.response?.data?.detail || error.message); }
  };

  const handleVerifyExisting = async () => {
    if (!activeSessionId) return;
    setIsVerifying(true);
    try {
      const result=await sessionService.verifySession(activeSessionId);
      setFeedback(result.metrics?.verificationSkipped ? 'Fuentes auditadas; pruebas de ejecución no realizadas por elección.' : 'Verificación: '+result.status);
      await Promise.all([refreshSessions(),reloadCurrentOverview(),fetchStatus()]);
    } catch (error:any) { setFeedback(error.response?.data?.detail || error.message); }
    finally { setIsVerifying(false); }
  };

  const handleGenerateManifests = async () => {
    if (!activeSessionId) return;
    setIsGenerating(true);
    setFeedback(null);
    try {
      const generated = await devopsService.generateManifests(activeSessionId);
      setManifests(generated);
      setFeedback('✅ Manifiestos DevOps (Dockerfile, Compose, CI/CD y Kubernetes) generados exitosamente.');
      await fetchStatus();
    } catch (err: any) {
      setFeedback(err.response?.data?.detail || 'Error al generar manifiestos DevOps.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDeployLocal = async () => {
    if (!activeSessionId || !hostPort) return;
    setIsDeploying(true);
    setFeedback(null);
    try {
      const res = await devopsService.deployLocal(activeSessionId, hostPort, true);
      setDeployment(res);
      setFeedback(res.message || 'Despliegue iniciado; esperando la salud del runtime propio.');
      await reloadCurrentOverview();
    } catch (err: any) {
      setFeedback(err.response?.data?.detail || err.message || 'No se pudo iniciar el despliegue.');
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
      setFeedback(res.errorMessage || (res.status === 'STOPPED' ? 'Contenedores detenidos; datos conservados.' : 'Estado: ' + res.status));
      await reloadCurrentOverview();
    } catch (err: any) {
      setFeedback(err.response?.data?.detail || err.message || 'No se pudo confirmar la parada.');
    } finally {
      setIsStopping(false);
    }
  };

  const handleCleanup = async () => {
    if (!activeSessionId || isStopping || isDeploying) return;
    setIsStopping(true);
    try {
      const preview = await devopsService.cleanupPreview(activeSessionId);
      if (!window.confirm('Eliminar definitivamente los recursos y datos de esta sesión: ' + JSON.stringify(preview.resources))) return;
      const result = await devopsService.cleanupLocal(activeSessionId, true, preview.confirmationToken);
      setDeployment(result);
      setFeedback(result.errorMessage || 'Limpieza explícita terminada; fuentes e historial conservados.');
      await reloadCurrentOverview();
    } catch (err: any) {
      setFeedback(err.response?.data?.detail || err.message || 'La limpieza no se pudo confirmar.');
    } finally { setIsStopping(false); }
  };

  const handleSmokeTest = async () => {
    if (!activeSessionId) return;
    setIsTesting(true);
    try {
      const res = await devopsService.runSmokeTest(activeSessionId, hostPort);
      setSmokeResult(res);
    } catch (error: any) {
      setSmokeResult({sessionId: activeSessionId, endpointTested: '', status: 'FAILURE', message: error.response?.data?.detail || 'No se pudo comprobar la salud del runtime.'});
    } finally {
      setIsTesting(false);
    }
  };

  const handleSendCustomRest = async () => {
    if (!activeSessionId) return;
    setRestResponse(null); setRestStatusCode(null); setRestLatency(null);
    try {
      const body = reqMethod === 'POST' && reqBody.trim() ? JSON.parse(reqBody) : undefined;
      const observed = await devopsService.proxyRequest(activeSessionId, reqMethod, reqEndpoint, body);
      setRestStatusCode(observed.statusCode); setRestLatency(observed.latencyMs);
      setRestResponse(observed.error || JSON.stringify(observed.body, null, 2));
    } catch (error: any) {
      setRestResponse(error.response?.data?.detail || error.message || 'Petición no completada.');
    }
  };

  const currentStatus = deployment?.status || 'UNKNOWN';
  const isRunning = currentStatus === 'RUNNING' || currentStatus === 'HEALTHY';
  const isDockerUnavailable = currentStatus === 'DOCKER_UNAVAILABLE';

  return (
    <div className="space-y-6">
      {activeSessionId && <div className="rounded-xl border p-4 space-y-3">
        {mode ? <ExecutionModeSelector value={mode} onChange={handleModeChange}/> : <span>Modo de ejecución sin declarar.</span>}
        <button onClick={handleVerifyExisting} disabled={isVerifying} className="rounded border px-3 py-2 text-xs">{isVerifying ? 'Comprobando fuentes…' : 'Comprobar fuentes existentes'}</button>
      </div>}
      {/* 1. Status Banner & Metrics */}
      <SingleRowCard
        title="Fase 8: DevOps, Contenerización & Despliegue Multi-Stage"
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
              disabled={!runtimeAllowed || isVerifying || isDeploying || isDockerUnavailable || !hostPort || currentStatus === 'BUILDING' || currentStatus === 'STARTING'}
              className="py-2 px-4 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-all shadow-sm flex items-center gap-1.5"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>{isDeploying ? 'Desplegando...' : '🚀 Desplegar Localmente'}</span>
            </button>
            <button
              onClick={handleSmokeTest}
              disabled={!runtimeAllowed || isTesting || !isRunning}
              className="py-2 px-3.5 rounded-lg text-xs font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 hover:bg-emerald-100 transition-colors"
            >
              🧪 Ejecutar Smoke Test
            </button>
            <button
              onClick={handleStopContainers}
              disabled={!runtimeAllowed || isStopping || !isRunning}
              className="py-2 px-3.5 rounded-lg text-xs font-semibold text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-800 hover:bg-rose-100 transition-colors"
            >
              🛑 Detener
            </button>
            <button onClick={handleCleanup} disabled={!runtimeAllowed || isStopping || isDeploying} className="py-2 px-3.5 rounded-lg text-xs font-semibold text-rose-700 border border-rose-300">
              Eliminar recursos y datos…
            </button>
          </div>
        }
      >
        <div className="flex flex-wrap items-center gap-4 text-xs text-slate-600 dark:text-slate-400">
          <span>
            Puerto Mapeado: <strong className="text-slate-900 dark:text-white">{deployment?.hostPort ? `${deployment.hostPort}:8080` : '—'}</strong>
          </span>
          <span>•</span>
          <span>
            Salud Quarkus: <strong className={`font-mono ${isRunning ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-500'}`}>{deployment?.healthStatus || 'NO INICIADO'}</strong>
          </span>
          <span>•</span>
          <span>
            Base de Datos: <strong className="text-slate-900 dark:text-white">{deployment?.dbEngine || projectOverview?.databaseEngine || 'Sin configuración'}</strong>
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
          <div className={`mt-2.5 p-2.5 rounded-lg border text-xs flex items-center justify-between ${smokeResult.status === 'SUCCESS' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'}`}>
            <div className="flex items-center gap-2">
              {smokeResult.status === 'SUCCESS' ? <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" /> : <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />}
              <span>{smokeResult.message}</span>
            </div>
            <span className="font-mono font-bold">{smokeResult.latencyMs == null ? '—' : `${smokeResult.latencyMs}ms`}</span>
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
            <span className="text-xs px-2.5 py-1 rounded-lg font-semibold bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
              {isRunning ? 'Runtime propio disponible' : 'Runtime no confirmado'}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
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
                disabled={!runtimeAllowed || !isRunning}
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
          <span>3. Terminal de Despliegue en Vivo (Docker & Quarkus Logs)</span>
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
            <CodeViewer
              code={manifests?.dockerfileContent || 'Manifiesto todavía no generado.'}
              language="dockerfile"
              filename="Dockerfile (Multi-Stage Fast-Jar Quarkus 3 / Java 21)"
              maxHeight="max-h-72"
            />
            <CodeViewer
              code={manifests?.dockerignoreContent || 'Manifiesto todavía no generado.'}
              language="text"
              filename=".dockerignore"
              maxHeight="max-h-40"
            />
          </div>
        )}

        {activeManifestTab === 'compose' && (
          <CodeViewer
            code={manifests?.dockerComposeContent || 'Manifiesto todavía no generado.'}
            language="yaml"
            filename="docker-compose.yml (Quarkus + PostgreSQL)"
            maxHeight="max-h-80"
          />
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
              <CodeViewer
                code={manifests?.githubActionsWorkflow || 'Manifiesto todavía no generado.'}
                language="yaml"
                filename=".github/workflows/ci-cd.yml"
                maxHeight="max-h-72"
              />
            ) : (
              <CodeViewer
                code={manifests?.gitlabCiWorkflow || 'Manifiesto todavía no generado.'}
                language="yaml"
                filename=".gitlab-ci.yml"
                maxHeight="max-h-72"
              />
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

            {activeK8sSubtab === 'deployment' && (
              <CodeViewer
                code={manifests?.kubernetesManifests?.['deployment.yaml'] || 'Manifiesto todavía no generado.'}
                language="yaml"
                filename="k8s/deployment.yaml"
                maxHeight="max-h-72"
              />
            )}
            {activeK8sSubtab === 'service' && (
              <CodeViewer
                code={manifests?.kubernetesManifests?.['service.yaml'] || 'Manifiesto todavía no generado.'}
                language="yaml"
                filename="k8s/service.yaml"
                maxHeight="max-h-72"
              />
            )}
            {activeK8sSubtab === 'configmap' && (
              <CodeViewer
                code={manifests?.kubernetesManifests?.['configmap.yaml'] || 'Manifiesto todavía no generado.'}
                language="yaml"
                filename="k8s/configmap.yaml"
                maxHeight="max-h-72"
              />
            )}
            {activeK8sSubtab === 'ingress' && (
              <CodeViewer
                code={manifests?.kubernetesManifests?.['ingress.yaml'] || 'Manifiesto todavía no generado.'}
                language="yaml"
                filename="k8s/ingress.yaml"
                maxHeight="max-h-72"
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
};
