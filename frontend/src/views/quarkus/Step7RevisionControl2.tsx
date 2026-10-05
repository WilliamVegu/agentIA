import React, { useState } from 'react';
import {
  CheckCircle2,
  FileCode,
  FolderTree,
  Coins,
  ShieldCheck,
  RotateCcw,
  GitPullRequest,
  Check,
  ChevronRight
} from 'lucide-react';
import { useQuarkus } from '../../context/QuarkusContext';

export const Step7RevisionControl2: React.FC = () => {
  const { currentOrder, approveDelivery, isLoading, setActiveStep } = useQuarkus();

  const [approvedBy, setApprovedBy] = useState(currentOrder?.control_1_approval_info?.approved_by || '');
  const [comments, setComments] = useState('Código Java 21, pruebas unitarias y artefactos revisados. Aprobado.');
  const [gitRepo, setGitRepo] = useState(
    currentOrder ? `https://github.com/empresa/${currentOrder.basic_data?.service_name || 'microservice'}.git` : ''
  );
  const [branchName, setBranchName] = useState(
    currentOrder ? `feat/quarkus-${currentOrder.basic_data?.service_name || 'service'}` : 'feat/quarkus-service'
  );

  const files = currentOrder?.generated_files || {};
  const fileKeys = Object.keys(files);

  const [selectedFile, setSelectedFile] = useState<string>(fileKeys[0] || '');

  const isApproved = currentOrder?.control_2_approved;
  const tokens = currentOrder?.tokens_audit;

  const handleApprove = async (e: React.FormEvent) => {
    e.preventDefault();
    await approveDelivery(approvedBy, comments, gitRepo, branchName);
  };

  if (!currentOrder || fileKeys.length === 0) {
    return (
      <div className="text-center p-8 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
        <p className="text-sm text-slate-500">
          No hay archivos de código generados aún. Completa el Paso 4 de Construcción primero.
        </p>
        <button
          onClick={() => setActiveStep(3)}
          className="mt-3 px-4 py-2 bg-red-600 text-white rounded-lg text-xs font-semibold"
        >
          Ir al Paso 4: Construcción & QA
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Banner de Control Humano 2 */}
      <div className="bg-gradient-to-r from-amber-500/15 via-amber-500/5 to-transparent border-l-4 border-amber-500 p-4 rounded-r-xl flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-amber-500 text-white shrink-0 mt-0.5 shadow-sm">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Control Humano 2: Revisión Final de Código, Code Review y Pruebas
              </h3>
              <span className="text-[10px] bg-amber-500 text-white px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">
                Compuerta Obligatoria
              </span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 leading-relaxed">
              El usuario inspecciona el árbol de archivos Java, los reportes de Code Review y pruebas unitarias Mockito/RestAssured antes de dar la autorización final para DevOps y empaquetado.
            </p>
          </div>
        </div>

        {isApproved && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 text-xs font-bold shrink-0">
            <Check className="w-4 h-4 text-emerald-600" />
            <span>ENTREGA APROBADA</span>
          </div>
        )}
      </div>

      {/* REPORTE DE CODE REVIEW */}
      {currentOrder?.code_review_report && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <h4 className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
                Auditoría de Calidad y Buenas Prácticas (Code Review)
              </h4>
            </div>
            <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
              Puntuación: {currentOrder.code_review_report.score}/100 · {currentOrder.code_review_report.verdict}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
            {currentOrder.code_review_report.checks?.map((chk: any, idx: number) => (
              <div key={idx} className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-bold text-slate-800 dark:text-slate-200">{chk.name}</span>
                  <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400">{chk.status}</span>
                </div>
                <p className="text-[11px] text-slate-500">{chk.notes}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 1. AUDITORÍA DETALLADA DE TOKENS (Sección 6 y 10 del documento) */}
      {tokens && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
            <div className="flex items-center gap-2">
              <Coins className="w-4 h-4 text-amber-500" />
              <h4 className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
                Auditoría de Consumo de Tokens por Agente
              </h4>
            </div>
            <span className="text-xs font-mono font-bold text-amber-700 dark:text-amber-400">
              Total: {tokens.total_consumed.toLocaleString()} tokens
              <span className="text-slate-500 font-normal ml-1">
                (Estimado: {(tokens.estimated_range[0] / 1000).toFixed(0)}k - {(tokens.estimated_range[1] / 1000).toFixed(0)}k)
              </span>
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 text-center text-xs">
            {Object.entries(tokens.by_agent).map(([agent, count]) => (
              <div key={agent} className="p-2 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200/60 dark:border-slate-800">
                <span className="block capitalize font-semibold text-slate-700 dark:text-slate-300 text-[11px] truncate">
                  {agent}
                </span>
                <span className="text-xs font-mono font-bold text-slate-900 dark:text-white">
                  {count.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 2. EXPLORADOR DEL ÁRBOL DE CÓDIGO GENERADO */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="px-4 py-2.5 bg-slate-100 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center text-xs">
          <span className="font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-2">
            <FolderTree className="w-4 h-4 text-amber-500" />
            <span>Árbol de Archivos Generados ({fileKeys.length} archivos)</span>
          </span>
          <span className="font-mono text-[11px] text-slate-500">{selectedFile}</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-slate-200 dark:divide-slate-800">
          {/* Lista de Archivos */}
          <div className="p-2 space-y-1 max-h-[420px] overflow-y-auto text-xs">
            {fileKeys.map((f) => {
              const isSelected = selectedFile === f;
              const isJava = f.endsWith('.java');
              const isConfig = f.endsWith('.properties') || f.endsWith('.xml') || f.endsWith('.gradle');

              return (
                <button
                  key={f}
                  onClick={() => setSelectedFile(f)}
                  className={`w-full text-left px-2.5 py-1.5 rounded-md text-xs font-mono transition-all flex items-center justify-between ${
                    isSelected
                      ? 'bg-red-600 text-white font-semibold'
                      : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300'
                  }`}
                >
                  <span className="truncate">{f.split('/').pop()}</span>
                  <span className="text-[10px] opacity-75 shrink-0 ml-1">
                    {isJava ? 'Java' : isConfig ? 'Config' : 'Doc'}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Visor de Código */}
          <div className="md:col-span-2">
            <pre className="p-4 font-mono text-xs bg-slate-950 text-slate-200 overflow-x-auto max-h-[420px] leading-relaxed">
              <code>{files[selectedFile] || '// Selecciona un archivo del árbol'}</code>
            </pre>
          </div>
        </div>
      </div>

      {/* 3. FORMULARIO DE APROBACIÓN CONTROL 2 */}
      {!isApproved ? (
        <form onSubmit={handleApprove} className="bg-amber-500/5 border border-amber-500/30 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-amber-500/20 pb-2">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-amber-600" />
              <h4 className="text-sm font-bold text-slate-900 dark:text-white">
                Veredicto del Control 2: Aprobación de Entrega
              </h4>
            </div>
            <button
              type="button"
              onClick={() => setActiveStep(4)}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 dark:hover:text-white"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Solicitar Ajustes (Volver a Paso 5)</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">Aprobado por</label>
              <input
                type="text"
                value={approvedBy}
                onChange={(e) => setApprovedBy(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-amber-500 outline-none"
                required
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">Comentarios / Veredicto</label>
              <input
                type="text"
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-amber-500 outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">Repositorio Git Objetivo</label>
              <input
                type="text"
                value={gitRepo}
                onChange={(e) => setGitRepo(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white font-mono focus:ring-2 focus:ring-amber-500 outline-none"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">Rama de Entrega (Feature Branch)</label>
              <input
                type="text"
                value={branchName}
                onChange={(e) => setBranchName(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white font-mono focus:ring-2 focus:ring-amber-500 outline-none"
              />
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={isLoading}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-bold text-sm shadow-lg hover:shadow-amber-600/30 transition-all disabled:opacity-50"
            >
              {isLoading ? (
                <span>Preparando artefactos DevOps y Pull Request...</span>
              ) : (
                <>
                  <GitPullRequest className="w-4 h-4" />
                  <span>Aprobar Entrega a Git y Activar Agente DevOps</span>
                </>
              )}
            </button>
          </div>
        </form>
      ) : (
        <div className="flex justify-between items-center p-4 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-xl">
          <div className="text-xs text-emerald-800 dark:text-emerald-300">
            <strong>Entrega Aprobada por:</strong> {currentOrder.control_2_approval_info?.approved_by}
          </div>
          <button
            onClick={() => setActiveStep(7)}
            className="flex items-center gap-1.5 px-4 py-2 bg-red-600 text-white rounded-lg text-xs font-semibold shadow hover:bg-red-700"
          >
            <span>Ir al Paso 8: Entrega DevOps</span>
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
};

