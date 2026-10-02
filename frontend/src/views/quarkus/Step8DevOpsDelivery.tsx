import React, { useState } from 'react';
import {
  GitPullRequest,
  Download,
  Terminal,
  Server,
  CheckCircle2,
  FileCode,
  ExternalLink
} from 'lucide-react';
import { useQuarkus } from '../../context/QuarkusContext';
import { quarkusFactoryService } from '../../services/quarkusFactoryService';

export const Step8DevOpsDelivery: React.FC = () => {
  const { currentOrder, setActiveStep } = useQuarkus();

  const artifacts = currentOrder?.devops_artifacts || {};
  const [activeTab, setActiveTab] = useState<'jenkins' | 'docker' | 'pr'>('jenkins');

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
              <span>Paso 7: Entrega Exitosa a DevOps & Descarga Directa ZIP</span>
              <span className="text-xs bg-emerald-600 text-white px-2 py-0.5 rounded-full font-bold">
                ESTADO: ENTREGADO
              </span>
            </h3>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 leading-relaxed">
              El <strong>Agente DevOps</strong> ha preparado el repositorio, configurado el pipeline corporativo de Jenkins,
              generado los contenedores Docker herméticos y simulado el Pull Request.
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

        <button
          onClick={() => setActiveTab('pr')}
          className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 border ${
            activeTab === 'pr'
              ? 'bg-blue-600 text-white border-blue-700 shadow-sm'
              : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800'
          }`}
        >
          <GitPullRequest className="w-4 h-4" />
          <span>Pull Request a Git</span>
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
          <div className="p-6 space-y-4">
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                  OPEN
                </span>
                <span className="text-xs font-mono text-slate-500">
                  Branch: {currentOrder.control_2_approval_info?.branch_name || `feat/quarkus-${currentOrder.basic_data?.service_name || 'service'}`}
                </span>
              </div>

              <h4 className="text-sm font-bold text-slate-900 dark:text-white">
                feat({currentOrder.basic_data.service_name}): Entrega inicial microservicio Quarkus 3.x
              </h4>

              <p className="text-xs text-slate-600 dark:text-slate-400">
                {currentOrder.control_2_approval_info?.comments || 'Aprobado en revisión técnica.'}
              </p>

              <div className="text-[11px] text-slate-500 pt-2 border-t border-slate-200 dark:border-slate-700 flex flex-wrap gap-4">
                <div>• Creado por: <strong>Agente DevOps</strong></div>
                <div>• Destino: <strong>main</strong></div>
                <div>• Repositorio: <code className="font-mono">{currentOrder.control_2_approval_info?.target_git_repo}</code></div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

