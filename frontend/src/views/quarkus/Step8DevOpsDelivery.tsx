import React, { useState } from 'react';
import {
  GitPullRequest,
  Download,
  Terminal,
  Server,
  CheckCircle2,
  FileCode,
  ExternalLink,
  GitBranch,
  Send,
  AlertCircle,
  Loader2,
  Lock
} from 'lucide-react';
import { useQuarkus } from '../../context/QuarkusContext';
import { quarkusFactoryService } from '../../services/quarkusFactoryService';
import { PublishQuarkusGitResponse } from '../../types/quarkusFactory';

export const Step8DevOpsDelivery: React.FC = () => {
  const { currentOrder, setActiveStep, publishToGit } = useQuarkus();

  const artifacts = currentOrder?.devops_artifacts || {};
  const [activeTab, setActiveTab] = useState<'jenkins' | 'docker' | 'pr'>('pr');

  const [repoUrl, setRepoUrl] = useState(
    currentOrder?.control_2_approval_info?.target_git_repo ||
      (currentOrder ? `https://github.com/empresa/${currentOrder.basic_data?.service_name || 'microservice'}.git` : '')
  );
  const [branchName, setBranchName] = useState(
    currentOrder?.control_2_approval_info?.branch_name ||
      (currentOrder ? `feat/quarkus-${currentOrder.basic_data?.service_name || 'service'}` : 'feat/quarkus-service')
  );
  const [gitToken, setGitToken] = useState(
    currentOrder?.control_2_approval_info?.git_token || ''
  );
  const [commitMsg, setCommitMsg] = useState(
    currentOrder?.control_2_approval_info?.commit_message ||
      (currentOrder
        ? `feat(quarkus): microservicio ${currentOrder.basic_data?.service_name || 'service'} generado y verificado`
        : 'feat(quarkus): microservicio generado y verificado')
  );
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishResult, setPublishResult] = useState<PublishQuarkusGitResponse | null>(
    (currentOrder?.control_2_approval_info as any)?.git_result || null
  );
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!currentOrder || Object.keys(artifacts).length === 0) {
    return (
      <div className="text-center p-8 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
        <p className="text-sm text-slate-500">
          Los artefactos DevOps aún no han sido preparados. Completa el Control Humano 2 primero.
        </p>
        <button
          onClick={() => setActiveStep(5)}
          className="mt-3 px-4 py-2 bg-red-600 text-white rounded-lg text-xs font-semibold"
        >
          Ir al Control 2 (Paso 6)
        </button>
      </div>
    );
  }

  const zipUrl = quarkusFactoryService.getExportZipUrl(currentOrder.id);

  const handlePublishGit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentOrder) return;
    setIsPublishing(true);
    setErrorMsg(null);
    try {
      const res = await publishToGit({
        repository_url: repoUrl,
        branch_name: branchName,
        git_token: gitToken || undefined,
        commit_message: commitMsg
      });
      setPublishResult(res);
    } catch (err: any) {
      setErrorMsg(
        err.response?.data?.detail ||
          err.message ||
          'Error durante la publicación a Git. Verifique la URL y el token efímero.'
      );
    } finally {
      setIsPublishing(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Banner de Entrega Exitosa */}
      <div className="bg-gradient-to-r from-emerald-600/15 via-emerald-500/5 to-transparent border-l-4 border-emerald-600 p-4 rounded-r-xl flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-emerald-600 text-white shrink-0 mt-0.5 shadow-sm">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <span>Paso 7: Entrega Exitosa a DevOps, Git & Descarga Directa ZIP</span>
              <span className="text-xs bg-emerald-600 text-white px-2 py-0.5 rounded-full font-bold">
                ESTADO: ENTREGADO
              </span>
            </h3>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 leading-relaxed">
              El <strong>Agente DevOps</strong> ha preparado el repositorio, configurado el pipeline corporativo de Jenkins,
              generado los contenedores Docker herméticos y habilitado la publicación atómica a ramas Git.
            </p>
          </div>
        </div>

        {/* Botón de Descarga Directa ZIP */}
        <a
          href={zipUrl}
          download
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-700 text-white font-bold text-xs shadow-lg hover:shadow-red-600/30 transition-all shrink-0"
        >
          <Download className="w-4 h-4" />
          <span>Descargar .ZIP Completo</span>
        </a>
      </div>

      {/* Tabs DevOps */}
      <div className="flex gap-2">
        <button
          onClick={() => setActiveTab('pr')}
          className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 border ${
            activeTab === 'pr'
              ? 'bg-blue-600 text-white border-blue-700 shadow-sm'
              : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800'
          }`}
        >
          <GitPullRequest className="w-4 h-4" />
          <span>Publicación a Git & Pull Request</span>
        </button>

        <button
          onClick={() => setActiveTab('jenkins')}
          className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 border ${
            activeTab === 'jenkins'
              ? 'bg-blue-600 text-white border-blue-700 shadow-sm'
              : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800'
          }`}
        >
          <Terminal className="w-4 h-4" />
          <span>Jenkinsfile Corporativo</span>
        </button>

        <button
          onClick={() => setActiveTab('docker')}
          className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 border ${
            activeTab === 'docker'
              ? 'bg-blue-600 text-white border-blue-700 shadow-sm'
              : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800'
          }`}
        >
          <Server className="w-4 h-4" />
          <span>Dockerfile (JVM & UBI)</span>
        </button>
      </div>

      {/* Contenido según Tab */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
        {activeTab === 'jenkins' && (
          <div>
            <div className="px-4 py-2 bg-slate-100 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center text-xs">
              <span className="font-mono font-bold text-slate-700 dark:text-slate-300">Jenkinsfile</span>
              <span className="text-[11px] text-slate-500">Pipeline Declarativo con 5 Etapas</span>
            </div>
            <pre className="p-4 font-mono text-xs bg-slate-950 text-slate-200 overflow-x-auto max-h-[450px] leading-relaxed">
              <code>{artifacts['Jenkinsfile']}</code>
            </pre>
          </div>
        )}

        {activeTab === 'docker' && (
          <div>
            <div className="px-4 py-2 bg-slate-100 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center text-xs">
              <span className="font-mono font-bold text-slate-700 dark:text-slate-300">Dockerfile.jvm</span>
              <span className="text-[11px] text-slate-500">Base Red Hat UBI 8 Minimal OpenJDK 21</span>
            </div>
            <pre className="p-4 font-mono text-xs bg-slate-950 text-slate-200 overflow-x-auto max-h-[450px] leading-relaxed">
              <code>{artifacts['Dockerfile.jvm']}</code>
            </pre>
          </div>
        )}

        {activeTab === 'pr' && (
          <div className="p-6 space-y-6">
            {/* Banner de Resultado de Publicación a Git */}
            {publishResult && (
              <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-900 dark:text-emerald-200 space-y-2.5">
                <div className="flex items-center gap-2 font-bold text-emerald-800 dark:text-emerald-300 text-sm">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                  <span>¡Código Publicado Exitosamente en Git!</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1 font-mono text-[11px]">
                  <div>
                    <span className="text-slate-500">Rama Remota:</span>{' '}
                    <strong className="text-emerald-700 dark:text-emerald-400">{publishResult.branchName}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500">Commit SHA:</span>{' '}
                    <span className="text-slate-800 dark:text-slate-200">{publishResult.commitHash}</span>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-4 pt-2 border-t border-emerald-200/60 dark:border-emerald-800/60">
                  {publishResult.branchUrl && (
                    <a
                      href={publishResult.branchUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 text-blue-600 dark:text-blue-400 hover:underline font-semibold"
                    >
                      <GitBranch className="w-3.5 h-3.5" />
                      <span>Ver Rama en Repositorio</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                  {publishResult.pullRequestUrl && (
                    <a
                      href={publishResult.pullRequestUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400 hover:underline font-semibold"
                    >
                      <GitPullRequest className="w-3.5 h-3.5" />
                      <span>Crear / Ver Pull Request</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              </div>
            )}

            {/* Error banner si falló la publicación */}
            {errorMsg && (
              <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-700 dark:text-rose-300 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <div>
                  <strong>Error al publicar en Git:</strong> {errorMsg}
                </div>
              </div>
            )}

            {/* Tarjeta de Metadatos del Pull Request Aprobado */}
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs px-2.5 py-0.5 rounded-full font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                  LISTO PARA FUSIÓN
                </span>
                <span className="text-xs font-mono text-slate-500">
                  Rama: {currentOrder.control_2_approval_info?.branch_name || branchName}
                </span>
              </div>

              <h4 className="text-sm font-bold text-slate-900 dark:text-white">
                feat({currentOrder.basic_data.service_name}): Entrega de Microservicio Quarkus 3.x
              </h4>

              <p className="text-xs text-slate-600 dark:text-slate-400">
                {currentOrder.control_2_approval_info?.comments || 'Código, pruebas Mockito y artefactos aprobados en Control 2.'}
              </p>

              <div className="text-[11px] text-slate-500 pt-2 border-t border-slate-200 dark:border-slate-700 flex flex-wrap gap-4">
                <div>• Responsable: <strong>{currentOrder.control_2_approval_info?.approved_by || 'DevOps Agent'}</strong></div>
                <div>• Rama Base Destino: <strong>main</strong></div>
                <div>• Repositorio: <code className="font-mono">{currentOrder.control_2_approval_info?.target_git_repo || repoUrl}</code></div>
              </div>
            </div>

            {/* Formulario de Publicación Atómica en Vivo a Git */}
            <form onSubmit={handlePublishGit} className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4">
              <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-2">
                <GitBranch className="w-4 h-4 text-blue-600" />
                <h4 className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
                  Publicación Atómica a Repositorio Git Corporativo
                </h4>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    URL del Repositorio Git Remoto (HTTPS)
                  </label>
                  <input
                    type="text"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    placeholder="https://github.com/organizacion/repositorio.git"
                    required
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white font-mono focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Nombre de la Rama Dedicada (Branch)
                  </label>
                  <input
                    type="text"
                    value={branchName}
                    onChange={(e) => setBranchName(e.target.value)}
                    placeholder="feat/quarkus-microservice"
                    required
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white font-mono focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
                    <Lock className="w-3.5 h-3.5 text-slate-400" />
                    <span>Personal Access Token (PAT Efímero)</span>
                  </label>
                  <input
                    type="password"
                    value={gitToken}
                    onChange={(e) => setGitToken(e.target.value)}
                    placeholder="ghp_... o glpat-..."
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white font-mono focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                  <p className="text-[10px] text-slate-500 mt-1">
                    Token efímero en memoria para GitHub/GitLab. Sin persistencia en disco ni logs.
                  </p>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Mensaje de Commit
                  </label>
                  <input
                    type="text"
                    value={commitMsg}
                    onChange={(e) => setCommitMsg(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  disabled={isPublishing}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-md hover:shadow-blue-600/30 transition-all disabled:opacity-50"
                >
                  {isPublishing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Empujando fuentes a Git...</span>
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4" />
                      <span>Publicar Código Fuente a Git Ahora</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};

