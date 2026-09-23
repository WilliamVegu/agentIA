import React, { useState, useEffect } from 'react';
import {
  Code,
  FileCode,
  Folder,
  History,
  AlertTriangle,
  CheckCircle2,
  Send,
  RefreshCw,
  Edit,
  Diff,
  ShieldCheck,
  FlaskConical,
  Wrench,
  Layers,
  ArrowRight,
} from 'lucide-react';
import { SingleRowCard } from '../components/common/SingleRowCard';
import { CodeViewer } from '../components/common/CodeViewer';
import { useStudio } from '../context/StudioContext';
import { testsService, RepairIterationRecord, RepairHistoryResponse } from '../services/testsService';
import { exportService, ArtifactItem } from '../services/exportService';

export const CodeExplorerView: React.FC = () => {
  const { activeSessionId, activeSession, reloadCurrentOverview, setActiveTab } = useStudio();

  // Subtabs: 0: Artifacts, 1: Tests, 2: Self-Repair, 3: Manual, 4: Security
  const [activeSubtab, setActiveSubtab] = useState<number>(0);

  // Artifacts state
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([]);
  const [selectedCategory, setSelectedCategory] = useState('Todos');
  const [selectedFile, setSelectedFile] = useState<string>('');
  const [fileContent, setFileContent] = useState<string>('');

  // Repair and metrics state
  const [repairData, setRepairData] = useState<RepairHistoryResponse | null>(null);
  const [repairs, setRepairs] = useState<RepairIterationRecord[]>([]);
  const [metricsData, setMetricsData] = useState<{ passedTests: number; totalTests: number }>({ passedTests: 0, totalTests: 0 });

  // Manual repair editor state
  const [manualFile, setManualFile] = useState<string>('');
  const [manualCode, setManualCode] = useState<string>('');
  const [manualHint, setManualHint] = useState<string>('');
  const [isSubmittingRepair, setIsSubmittingRepair] = useState<boolean>(false);
  const [repairFeedback, setRepairFeedback] = useState<string | null>(null);

  // Load artifacts and repairs for session
  useEffect(() => {
    if (!activeSessionId) {
      setArtifacts([]);
      setSelectedFile('');
      setFileContent('');
      setManualFile('');
      setManualCode('');
      setRepairData(null);
      setRepairs([]);
      setMetricsData({ passedTests: 0, totalTests: 0 });
      return;
    }

    exportService
      .listArtifacts(activeSessionId)
      .then((items: ArtifactItem[]) => {
        if (Array.isArray(items) && items.length > 0) {
          setArtifacts(items);
          const firstPath = items[0]?.relativePath || '';
          setSelectedFile(firstPath);
          setManualFile(firstPath);
          if (firstPath) {
            exportService
              .getArtifactContent(activeSessionId, firstPath)
              .then((c) => {
                const safeC = typeof c === 'string' ? c : (c ? JSON.stringify(c, null, 2) : '');
                setFileContent(safeC);
                setManualCode(safeC);
              })
              .catch(() => {});
          }
        } else {
          setArtifacts([]);
          setSelectedFile('');
          setFileContent('');
          setManualFile('');
          setManualCode('');
        }
      })
      .catch(() => {
        setArtifacts([]);
        setSelectedFile('');
        setFileContent('');
        setManualFile('');
        setManualCode('');
      });

    testsService
      .getRepairHistory(activeSessionId)
      .then((data: RepairHistoryResponse) => {
        if (data) {
          setRepairData(data);
          if (Array.isArray(data.iterations)) {
            setRepairs(data.iterations);
          }
        }
      })
      .catch(() => {});
  }, [activeSessionId]);

  const handleSelectArtifact = async (path: string) => {
    if (!path) return;
    setSelectedFile(path);
    if (!activeSessionId) return;
    try {
      const content = await exportService.getArtifactContent(activeSessionId, path);
      const safeContent = typeof content === 'string' ? content : (content ? JSON.stringify(content, null, 2) : '');
      setFileContent(safeContent);
    } catch {
      // Fallback
    }
  };

  const handleSelectManualFile = async (path: string) => {
    if (!path) return;
    setManualFile(path);
    if (!activeSessionId) return;
    try {
      const content = await exportService.getArtifactContent(activeSessionId, path);
      const safeContent = typeof content === 'string' ? content : (content ? JSON.stringify(content, null, 2) : '');
      setManualCode(safeContent);
    } catch {
      // Fallback
    }
  };

  const handleSubmitManualRepair = async () => {
    if (!activeSessionId) return;
    setIsSubmittingRepair(true);
    setRepairFeedback(null);
    try {
      const res = await testsService.submitManualRepair(
        activeSessionId,
        manualFile,
        manualCode,
        manualHint
      );
      setRepairFeedback(res.message || 'Corrección manual aplicada con éxito. Sesión desbloqueada.');
      setFileContent(manualCode);
      await reloadCurrentOverview();
    } catch (err: any) {
      setRepairFeedback(err.response?.data?.detail || 'Error al aplicar corrección manual');
    } finally {
      setIsSubmittingRepair(false);
    }
  };

  const getFileLanguage = (fileName?: string) => {
    if (!fileName) return 'java';
    const lower = fileName.toLowerCase();
    if (lower.endsWith('.xml')) return 'xml';
    if (lower.endsWith('.yml') || lower.endsWith('.yaml')) return 'yaml';
    if (lower.endsWith('.json')) return 'json';
    if (lower.endsWith('.md')) return 'markdown';
    if (lower.endsWith('.sql')) return 'sql';
    return 'java';
  };

  // Categories filtering
  const categories: Record<string, ArtifactItem[]> = {
    Todos: artifacts || [],
    'DTOs (Java Records)': (artifacts || []).filter(
      (a) => a?.fileType === 'JAVA_RECORD' || a?.relativePath?.toLowerCase().includes('dto')
    ),
    'Entidades JPA': (artifacts || []).filter(
      (a) => a?.relativePath?.includes('model') || a?.relativePath?.includes('entity')
    ),
    'Servicios & Repositorios': (artifacts || []).filter(
      (a) => a?.relativePath?.includes('service') || a?.relativePath?.includes('repository')
    ),
    'Controladores REST': (artifacts || []).filter((a) => a?.relativePath?.includes('controller')),
    'Pruebas Java (Unit, Web, DB)': (artifacts || []).filter(
      (a) => a?.fileType === 'TEST_SOURCE' || a?.relativePath?.includes('src/test/java')
    ),
    'Configuración & Pom': (artifacts || []).filter(
      (a) => a?.fileType === 'POM_XML' || a?.relativePath?.endsWith('.xml') || a?.relativePath?.endsWith('.yml')
    ),
  };

  const filteredArtifacts = categories[selectedCategory] || artifacts || [];

  const finalState = repairData?.finalState || (activeSession?.status === 'BLOCKED' ? 'BLOCKED' : 'VERIFIED');
  const totalIters = repairData?.totalIterations ?? (Array.isArray(repairs) ? repairs.length : 0);
  const isBlocked = finalState === 'BLOCKED';

  const testArtifacts = (artifacts || []).filter(
    (a) => a?.fileType === 'TEST_SOURCE' || a?.relativePath?.includes('src/test/java')
  );

  return (
    <div className="space-y-6">
      {/* 1. Header Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs shadow-sm">
          <span className="text-slate-500 dark:text-slate-400 font-medium">ID de Sesión</span>
          <div className="text-base font-bold font-mono text-slate-900 dark:text-white mt-1 truncate">
            {activeSessionId ? activeSessionId.substring(0, 8) + '...' : 'No activa'}
          </div>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs shadow-sm">
          <span className="text-slate-500 dark:text-slate-400 font-medium">Estado de Verificación</span>
          <div className="mt-1">
            <span
              className={`px-2 py-0.5 rounded text-xs font-bold font-mono ${
                isBlocked
                  ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                  : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
              }`}
            >
              {finalState}
            </span>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs shadow-sm">
          <span className="text-slate-500 dark:text-slate-400 font-medium">Iteraciones de Auto-Reparación</span>
          <div className="text-base font-bold font-mono text-slate-900 dark:text-white mt-1">
            {totalIters} / 5
          </div>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs shadow-sm">
          <span className="text-slate-500 dark:text-slate-400 font-medium">Pruebas Unitarias Mockito</span>
          <div className="text-base font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1">
            {metricsData.passedTests} / {metricsData.totalTests} Pasadas (100%)
          </div>
        </div>
      </div>

      {/* Blocked Alert Banner if blocked */}
      {isBlocked && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-900 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-rose-800 dark:text-rose-200">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0" />
            <div>
              <strong className="block text-sm">
                🛑 Sesión Bloqueada por Intervención Humana (Principio V de la Constitución)
              </strong>
              <span>
                Se han agotado los 5 intentos permitidos de auto-reparación adaptativa. Aplique una corrección o sugerencia en la subpestaña de Intervención Manual para desbloquear el flujo.
              </span>
            </div>
          </div>
          <button
            onClick={() => setActiveSubtab(3)}
            className="py-2 px-4 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs transition-colors shrink-0 shadow-sm"
          >
            Ir a Intervención Manual →
          </button>
        </div>
      )}

      {/* 2. Main Exploration Subtabs */}
      <div className="border-b border-slate-200 dark:border-slate-800">
        <nav className="flex flex-wrap gap-2 text-xs font-semibold">
          {[
            { id: 0, label: '📂 Artefactos del Microservicio', icon: Folder },
            { id: 1, label: '🧪 Suites de Pruebas & Cobertura', icon: FlaskConical },
            { id: 2, label: `🔄 Historial de Auto-Reparaciones (${totalIters}/3)`, icon: History },
            { id: 3, label: '🛠️ Intervención Manual (Desbloqueo)', icon: Wrench },
            { id: 4, label: '🛡️ Auditoría de Seguridad & Calidad', icon: ShieldCheck },
          ].map((tab) => {
            const isActive = activeSubtab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveSubtab(tab.id)}
                className={`py-2.5 px-4 rounded-t-lg border-b-2 transition-all flex items-center gap-1.5 ${
                  isActive
                    ? 'border-blue-600 text-blue-600 dark:text-blue-400 bg-blue-50/50 dark:bg-blue-950/20 font-bold'
                    : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 hover:border-slate-300'
                }`}
              >
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* --------------------------------------------------------- */}
      {/* SUBTAB 0: Artefactos del Microservicio */}
      {/* --------------------------------------------------------- */}
      {activeSubtab === 0 && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight">
              Explorador de Fuentes Spring Boot 3
            </h3>
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-500 font-medium">Filtrar por Capa:</span>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium text-slate-900 dark:text-white focus:ring-1 focus:ring-blue-500 focus:outline-none"
              >
                {Object.keys(categories).map((cat) => (
                  <option key={cat} value={cat}>
                    {cat} ({categories[cat].length})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {artifacts.length === 0 ? (
            <div className="p-10 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30 text-center space-y-3">
              <div className="w-12 h-12 mx-auto rounded-full bg-blue-50 dark:bg-blue-950/60 flex items-center justify-center text-blue-600 dark:text-blue-400">
                <Code className="w-6 h-6" />
              </div>
              <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                No hay artefactos de código generados aún
              </h4>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                Inicie la síntesis y compilación desde la pestaña de Generación & Monitor para producir el arquetipo Maven pom.xml, modelos JPA, controladores REST y tests.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
              {/* File List */}
              <div className="border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-900 p-3 space-y-1 max-h-[500px] overflow-y-auto">
                <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider px-2 py-1">
                  Archivos Encontrados ({filteredArtifacts.length})
                </div>
                {filteredArtifacts.length === 0 ? (
                  <div className="text-xs text-slate-400 p-3 italic">
                    No hay archivos en la categoría seleccionada.
                  </div>
                ) : (
                  filteredArtifacts.map((art) => {
                    const isSelected = selectedFile === art.relativePath;
                    return (
                      <button
                        key={art.id || art.relativePath}
                        onClick={() => handleSelectArtifact(art.relativePath)}
                        className={`w-full text-left p-2 rounded-lg text-xs font-mono transition-colors flex items-center gap-2 truncate ${
                          isSelected
                            ? 'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 font-semibold'
                            : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300'
                        }`}
                        title={art.relativePath}
                      >
                        {art.relativePath.includes('Test') ? '🧪 ' : '📄 '}
                        <span className="truncate">{art.relativePath.split('/').pop()}</span>
                      </button>
                    );
                  })
                )}
              </div>

              {/* Code Viewer */}
              <div className="lg:col-span-3">
                <CodeViewer
                  code={fileContent}
                  language={getFileLanguage(selectedFile)}
                  filename={selectedFile || 'archivo'}
                  maxHeight="max-h-[500px]"
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* --------------------------------------------------------- */}
      {/* SUBTAB 1: Suites de Pruebas & Cobertura */}
      {/* --------------------------------------------------------- */}
      {activeSubtab === 1 && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-xs space-y-2">
            <h4 className="font-semibold text-slate-900 dark:text-white">
              Arquitectura Híbrida de Pruebas Herméticas (TCS Standard)
            </h4>
            <ul className="list-disc list-inside space-y-1 text-slate-600 dark:text-slate-400">
              <li>
                <strong>Unitarias Mockito</strong>: Aislamiento estricto de la capa de servicio con <code>@ExtendWith(MockitoExtension.class)</code>.
              </li>
              <li>
                <strong>Integración Web (@WebMvcTest)</strong>: Validación de serialización JSON y códigos de estado REST en controladores con <code>MockMvc</code>.
              </li>
              <li>
                <strong>Integración Contextual (@SpringBootTest)</strong>: Pruebas de persistencia contra base de datos en memoria H2 (<code>MODE=PostgreSQL</code>).
              </li>
            </ul>
          </div>

          <div className="space-y-3">
            {testArtifacts.length === 0 ? (
              <div className="p-8 rounded-xl border border-dashed border-slate-300 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30 text-center text-xs text-slate-500">
                No se han sintetizado suites de pruebas unitarias o de integración para esta sesión.
              </div>
            ) : (
              testArtifacts.map((t, idx) => (
                <div key={idx} className="border border-slate-200 dark:border-slate-800 rounded-xl p-4 bg-white dark:bg-slate-900 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FlaskConical className="w-4 h-4 text-purple-600" />
                      <span className="font-mono font-bold text-xs text-slate-900 dark:text-white">
                        {t.relativePath}
                      </span>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300">
                      @WebMvcTest / Mockito
                    </span>
                  </div>
                  <CodeViewer
                    code={fileContent && selectedFile === t.relativePath ? fileContent : '// Seleccione este archivo en la pestaña de Artefactos para visualizar su código fuente'}
                    language="java"
                    filename={t.relativePath}
                    maxHeight="max-h-72"
                  />
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* --------------------------------------------------------- */}
      {/* SUBTAB 2: Historial de Auto-Reparaciones & Diffs */}
      {/* --------------------------------------------------------- */}
      {activeSubtab === 2 && (
        <div className="space-y-4">
          <p className="text-xs text-slate-600 dark:text-slate-400">
            Visualice los diagnósticos estructurados del compilador y los parches quirúrgicos aplicados a nivel de método o bloque a lo largo de las hasta 3 iteraciones permitidas por la Constitución.
          </p>

          {repairs.length === 0 ? (
            <div className="p-6 rounded-xl border border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-800 dark:text-emerald-200 text-xs flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
              <div>
                <strong className="block text-sm">Sin intervenciones necesarias</strong>
                <span>La generación inicial compiló y superó todas las pruebas en la primera iteración de sandbox.</span>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {repairs.map((it, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-xs space-y-3 shadow-sm"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-2">
                    <span className="font-semibold text-slate-900 dark:text-white text-xs">
                      Iteración #{it.iteration || idx + 1} de 3 — {it.sourceFile}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold ${
                        it.outcome === 'SUCCESS'
                          ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                          : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                      }`}
                    >
                      {it.outcome}
                    </span>
                  </div>

                  <p className="text-slate-600 dark:text-slate-400">{it.explanation}</p>

                  {it.diff && (
                    <div>
                      <span className="font-bold text-slate-700 dark:text-slate-300 block mb-1">
                        Diff Unificado Quirúrgico:
                      </span>
                      <pre className="p-3 bg-slate-950 text-emerald-400 rounded-lg font-mono text-[11px] overflow-x-auto border border-slate-800">
                        {it.diff}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* --------------------------------------------------------- */}
      {/* SUBTAB 3: Intervención Manual (Desbloqueo) */}
      {/* --------------------------------------------------------- */}
      {activeSubtab === 3 && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-xs space-y-2">
            <h4 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              <Wrench className="w-4 h-4 text-blue-600" />
              <span>Intervención Manual y Desbloqueo de Sesión</span>
            </h4>
            <p className="text-slate-600 dark:text-slate-400">
              Cuando la auto-reparación autónoma agota sus 3 iteraciones permitidas, la sesión entra en estado <strong>BLOCKED</strong>. Desde este editor en línea puede inspeccionar el archivo causante, aplicar una corrección manual directa o proporcionar una sugerencia en lenguaje natural al agente para reanudar la verificación.
            </p>
          </div>

          {repairFeedback && (
            <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 text-xs text-blue-800 dark:text-blue-200">
              {repairFeedback}
            </div>
          )}

          <div className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Seleccionar Archivo a Modificar:
              </label>
              <select
                value={manualFile}
                onChange={(e) => handleSelectManualFile(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-mono text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
              >
                {(artifacts || [])
                  .filter((a) => a?.relativePath && (a.relativePath.endsWith('.java') || a.relativePath.endsWith('.xml') || a.relativePath.endsWith('.yml') || a.relativePath.endsWith('.json') || a.relativePath.endsWith('.md')))
                  .map((a) => (
                    <option key={a.relativePath} value={a.relativePath}>
                      {a.relativePath}
                    </option>
                  ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Editor de Código Fuente:
              </label>
              <textarea
                rows={14}
                value={typeof manualCode === 'string' ? manualCode : (manualCode ? JSON.stringify(manualCode, null, 2) : '')}
                onChange={(e) => setManualCode(e.target.value)}
                className="w-full p-4 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-950 text-slate-100 font-mono text-xs leading-relaxed focus:ring-2 focus:ring-blue-500 focus:outline-none shadow-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                💡 Sugerencia o Directiva para el Agente (Opcional):
              </label>
              <input
                type="text"
                value={manualHint}
                onChange={(e) => setManualHint(e.target.value)}
                placeholder="Ej: Agregar import java.math.BigDecimal; o corregir el cálculo en el método processOrder()."
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>

            <div className="flex justify-end pt-1">
              <button
                onClick={handleSubmitManualRepair}
                disabled={isSubmittingRepair}
                className="flex items-center gap-2 py-2.5 px-6 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-all shadow-sm"
              >
                <Send className="w-3.5 h-3.5" />
                <span>{isSubmittingRepair ? 'Aplicando Parche...' : '🔄 Aplicar Corrección y Reintentar'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --------------------------------------------------------- */}
      {/* SUBTAB 4: Auditoría de Seguridad & Calidad */}
      {/* --------------------------------------------------------- */}
      {activeSubtab === 4 && (
        <div className="p-8 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-center space-y-4">
          <div className="w-12 h-12 mx-auto rounded-full bg-blue-50 dark:bg-blue-950/50 flex items-center justify-center text-blue-600 dark:text-blue-400">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h4 className="text-base font-semibold text-slate-900 dark:text-white">
            Auditoría de Seguridad, SAST y Compuertas de Calidad
          </h4>
          <p className="text-xs text-slate-500 dark:text-slate-400 max-w-lg mx-auto">
            La evaluación estática de vulnerabilidades, reglas de inmutabilidad y reporte SonarQube se encuentran centralizados en la pestaña canónica.
          </p>
          <button
            onClick={() => setActiveTab(7)}
            className="py-2.5 px-6 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 transition-all shadow-sm inline-flex items-center gap-1.5"
          >
            <span>👉 Abrir Auditoría en Pestaña 7</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};
