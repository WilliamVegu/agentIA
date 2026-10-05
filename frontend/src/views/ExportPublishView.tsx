import React, { useState, useEffect, useRef } from 'react';
import { Download, GitBranch, GitPullRequest, CheckCircle2, AlertCircle, Share2, Send } from 'lucide-react';
import { SingleRowCard } from '../components/common/SingleRowCard';
import { useStudio } from '../context/StudioContext';
import { exportService, PublishResult } from '../services/exportService';
import { VerificationStatus } from '../components/common/VerificationStatus';

export const ExportPublishView: React.FC = () => {
  const { activeSessionId, activeSession } = useStudio();
  const scope = useRef({ id: activeSessionId, revision: 0 });
  if (scope.current.id !== activeSessionId) scope.current = { id: activeSessionId, revision: scope.current.revision + 1 };

  const [repoUrl, setRepoUrl] = useState('');
  const [branchName, setBranchName] = useState('');
  const [gitToken, setGitToken] = useState('');
  const [commitMsg, setCommitMsg] = useState('feat: generated microservice source');
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishResult, setPublishResult] = useState<PublishResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  useEffect(() => {
    setPublishResult(null); setErrorMsg(null); setIsPublishing(false); setGitToken('');
    setBranchName(activeSession?.specName ? `feature/001-${activeSession.specName.toLowerCase().replace(/[^a-z0-9-]/g, '-')}` : '');
  }, [activeSessionId]);

  useEffect(() => {
    if (activeSession?.specName && !branchName) {
      const sanitized = activeSession.specName.toLowerCase().replace(/[^a-z0-9-]/g, '-');
      setBranchName(`feature/001-${sanitized}`);
    }
  }, [activeSession?.specName]);

  const handleDownloadZip = () => {
    if (!activeSessionId) return;
    const url = exportService.getDownloadZipUrl(activeSessionId);
    window.open(url, '_blank');
  };

  const handlePublish = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeSessionId) return;
    const revision = scope.current.revision;
    setIsPublishing(true);
    setErrorMsg(null);
    try {
      const res = await exportService.publishToGit(activeSessionId, {
        repositoryUrl: repoUrl,
        branchName: branchName,
        gitToken: gitToken || undefined,
        commitMessage: commitMsg,
      });
      if (revision !== scope.current.revision) return;
      setPublishResult(res);
    } catch (err: any) {
      if (revision !== scope.current.revision) return;
      setErrorMsg(
        err.response?.data?.detail ||
          'Error durante la publicación atómica a Git. Verifique la URL y el token efímero.'
      );
    } finally {
      if (revision === scope.current.revision) setIsPublishing(false);
    }
  };

  return (
    <div className="space-y-6">
      <VerificationStatus session={activeSession} />
      {/* Top Banner */}
      <SingleRowCard
        title="Fase 7: Entrega Integral, Empaquetado ZIP y Publicación Git"
        subtitle="Entrega de fuentes sujeta a las validaciones de exportación del backend"
        badge={
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300">
            {activeSession?.verificationOutcome === 'PASSED' ? 'Pruebas aprobadas' : 'Entrega de fuentes'}
          </span>
        }
        actions={
          <button
            onClick={handleDownloadZip}
            disabled={!activeSessionId}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 px-5 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-all shadow-sm"
          >
            <Download className="w-4 h-4" />
            <span>Descargar Código Fuente Completo (ZIP)</span>
          </button>
        }
      >
        <p className="text-xs text-slate-600 dark:text-slate-400">
          El ZIP incluye los archivos disponibles del microservicio: código Java, configuración Maven o Gradle, pruebas generadas, migraciones y manifiestos cuando existan. El backend valida la entrega; generar pruebas o exportar fuentes no acredita su ejecución.
        </p>
      </SingleRowCard>

      {activeSession?.executionMode === 'DOCKER' && activeSession.verificationOutcome === 'PASSED' && activeSessionId && (
        <button type="button" className="px-4 py-2 border rounded-lg text-sm" onClick={() => window.open(exportService.getExecutableZipUrl(activeSessionId), '_blank')}>
          Descargar imagen ejecutable verificada (requiere despliegue saludable)
        </button>
      )}

      {/* Non-completed session warning */}
      {activeSession && activeSession.status !== 'COMPLETED' && (
        <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-900 text-xs text-amber-800 dark:text-amber-200 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
          <span>
            ⚠️ La sesión actual tiene estado <strong>`{activeSession.status}`</strong>. Se recomienda exportar únicamente sesiones con estado <strong>`COMPLETED`</strong>.
          </span>
        </div>
      )}

      {/* Git Publish Form */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 space-y-4 shadow-sm">
        <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-3">
          <GitBranch className="w-4 h-4 text-blue-600 dark:text-blue-400" />
          <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight">
            Publicación Atómica a Rama Git Corporativa
          </h3>
        </div>

        {errorMsg && (
          <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-700 dark:text-rose-300">
            {errorMsg}
          </div>
        )}

        {publishResult && (
          <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-900 dark:text-emerald-200 space-y-2">
            <div className="flex items-center gap-2 font-bold text-emerald-800 dark:text-emerald-300">
              <CheckCircle2 className="w-4 h-4" />
              <span>Publicación a Git exitosa</span>
            </div>
            <div>
              <strong>Rama Remota:</strong> {publishResult.branchName}
            </div>
            <div>
              <strong>Commit Hash:</strong> <span className="font-mono">{publishResult.commitHash}</span>
            </div>
            {publishResult.branchUrl && (
              <div>
                <a
                  href={publishResult.branchUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-600 underline font-semibold"
                >
                  Ver Rama en Repositorio →
                </a>
              </div>
            )}
          </div>
        )}

        <form onSubmit={handlePublish} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                URL del Repositorio Git Remoto
              </label>
              <input
                type="text"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/org/repo.git"
                required
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-900 dark:text-white font-mono focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Nombre de la Rama Dedicada
              </label>
              <input
                type="text"
                value={branchName}
                onChange={(e) => setBranchName(e.target.value)}
                placeholder="feature/001-microservice"
                required
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-900 dark:text-white font-mono focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Token de Acceso Personal Efímero (PAT)
              </label>
              <input
                type="password"
                value={gitToken}
                onChange={(e) => setGitToken(e.target.value)}
                placeholder="ghp_... o glpat-..."
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-900 dark:text-white font-mono focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
              <span className="text-[10px] text-slate-500">
                Se procesa en memoria efímera y no se almacena en disco.
              </span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Mensaje de Commit
              </label>
              <input
                type="text"
                value={commitMsg}
                onChange={(e) => setCommitMsg(e.target.value)}
                required
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={isPublishing || !activeSessionId}
              className="flex items-center gap-2 py-2 px-6 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-all shadow-sm"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{isPublishing ? 'Publicando a Rama...' : 'Publicar Rama a Git'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
