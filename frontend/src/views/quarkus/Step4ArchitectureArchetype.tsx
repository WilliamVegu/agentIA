import React, { useState } from 'react';
import {
  Layers,
  Box,
  Check,
  Code2,
  FolderTree,
  Terminal,
  Cpu,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  Package,
  Plus,
  Trash2,
  RefreshCw,
  Edit2,
  AlertTriangle
} from 'lucide-react';
import { useQuarkus } from '../../context/QuarkusContext';
import { ArchitecturePattern, BuildTool, QuarkusExtensionItem } from '../../types/quarkusFactory';

export const Step4ArchitectureArchetype: React.FC = () => {
  const { currentOrder, selectArchitecture, generateSkeleton, isLoading, setActiveStep, error } = useQuarkus();

  const proposal = currentOrder?.architecture_proposal;

  const [selectedPattern, setSelectedPattern] = useState<ArchitecturePattern>(
    (currentOrder?.chosen_architecture?.pattern as ArchitecturePattern) ||
      proposal?.selected_option ||
      'layered'
  );

  const [selectedBuildTool, setSelectedBuildTool] = useState<BuildTool>(
    (currentOrder?.chosen_architecture?.build_tool as BuildTool) ||
      currentOrder?.basic_data?.build_tool ||
      'maven'
  );

  // Estado para gestión interactiva de Extensiones Quarkus y sus Versiones
  const [extensions, setExtensions] = useState<QuarkusExtensionItem[]>(() => {
    if (currentOrder?.quarkus_extensions && currentOrder.quarkus_extensions.length > 0) {
      return currentOrder.quarkus_extensions;
    }
    return proposal?.quarkus_extensions || [];
  });

  const [newExtId, setNewExtId] = useState('');
  const [newExtName, setNewExtName] = useState('');
  const [newExtVersion, setNewExtVersion] = useState('3.15.1');
  const [newExtCategory, setNewExtCategory] = useState('Personalizada');
  const [isAddingExt, setIsAddingExt] = useState(false);

  // Pestaña de visualización de arquetipo (Maven o Gradle)
  const [activeArchetypeTab, setActiveArchetypeTab] = useState<BuildTool>(selectedBuildTool);

  const handleToggleExtension = (id: string) => {
    setExtensions((prev) =>
      prev.map((ext) => (ext.id === id ? { ...ext, is_selected: !ext.is_selected } : ext))
    );
  };

  const handleVersionChange = (id: string, newVersion: string) => {
    setExtensions((prev) =>
      prev.map((ext) => (ext.id === id ? { ...ext, version: newVersion } : ext))
    );
  };

  const handleAddCustomExtension = () => {
    if (!newExtId.trim()) return;
    const item: QuarkusExtensionItem = {
      id: newExtId.trim(),
      name: newExtName.trim() || newExtId.trim(),
      version: newExtVersion.trim() || '3.15.1',
      category: newExtCategory,
      description: 'Extensión añadida manualmente por el usuario.',
      is_selected: true,
      is_mandatory: false
    };
    setExtensions((prev) => [...prev, item]);
    setNewExtId('');
    setNewExtName('');
    setIsAddingExt(false);
  };

  const handleRemoveExtension = (id: string) => {
    setExtensions((prev) => prev.filter((ext) => ext.id !== id));
  };

  const handleConfirmAndGenerate = async () => {
    await selectArchitecture(selectedPattern, selectedBuildTool, extensions);
    await generateSkeleton();
  };

  if (!currentOrder || !proposal) {
    return (
      <div className="text-center p-8 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
        <p className="text-sm text-slate-500">
          La propuesta de arquitectura aún no está disponible. Revisa y aprueba el contrato en el Paso 2 primero.
        </p>
        <button
          onClick={() => setActiveStep(1)}
          className="mt-3 px-4 py-2 bg-red-600 text-white rounded-lg text-xs font-semibold"
        >
          Ir al Paso 2: Contrato OpenAPI
        </button>
      </div>
    );
  }

  const activePreview =
    activeArchetypeTab === 'maven' ? proposal.maven_preview : proposal.gradle_preview;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Banner del Agente Arquitecto */}
      <div className="bg-gradient-to-r from-blue-600/10 via-blue-500/5 to-transparent border-l-4 border-blue-600 p-4 rounded-r-xl">
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          <h3 className="text-sm font-bold text-slate-900 dark:text-white">
            Paso 3: Arquitectura, Extensiones Quarkus y Previsualizador de Arquetipo
          </h3>
          <span className="text-xs bg-blue-600 text-white px-2 py-0.5 rounded-full font-semibold">
            Modo: {currentOrder.ai_mode.mode}
          </span>
        </div>
        <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
          El Agente Arquitecto analizó el contrato OpenAPI revisado. Selecciona tu <strong>patrón arquitectónico</strong>,{' '}
          <strong>aprueba o reemplaza las extensiones de Quarkus 3.x con sus versiones exactas</strong>, y previsualiza el arquetipo antes de generar código.
        </p>
      </div>

      {/* 1. SELECCIÓN DE LAS 3 OPCIONES DE ARQUITECTURA */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
            1. Opciones de Arquitectura para tu Microservicio:
          </h4>
          <span className="text-xs text-slate-500">Escoge una opción antes de generar</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {proposal.options.map((opt) => {
            const isSelected = selectedPattern === opt.id;
            return (
              <div
                key={opt.id}
                onClick={() => setSelectedPattern(opt.id)}
                className={`p-4 rounded-xl border-2 cursor-pointer transition-all flex flex-col justify-between ${
                  isSelected
                    ? 'border-blue-600 bg-blue-50/50 dark:bg-blue-950/30 shadow-md ring-2 ring-blue-300 dark:ring-blue-900'
                    : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-white dark:bg-slate-900'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-mono font-bold text-blue-600 dark:text-blue-400">
                      {opt.id.toUpperCase()}
                    </span>
                    {opt.is_recommended && (
                      <span className="flex items-center gap-1 text-[10px] bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-bold px-2 py-0.5 rounded-full">
                        <Sparkles className="w-3 h-3 text-emerald-600" />
                        Recomendado
                      </span>
                    )}
                  </div>
                  <h5 className="text-sm font-bold text-slate-900 dark:text-white mb-1.5">{opt.title}</h5>
                  <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed mb-3">
                    {opt.description}
                  </p>

                  <div className="space-y-1 mb-3">
                    <span className="text-[11px] font-semibold text-slate-500">Capas del proyecto:</span>
                    <ul className="text-[11px] font-mono text-slate-600 dark:text-slate-400 space-y-0.5">
                      {opt.structure_layers.map((layer, i) => (
                        <li key={i} className="truncate">• {layer}</li>
                      ))}
                    </ul>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
                  <span className="text-[11px] text-slate-500">{opt.recommended_for}</span>
                  {isSelected && <Check className="w-5 h-5 text-blue-600 shrink-0" />}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 2. GESTIÓN Y APROBACIÓN DE EXTENSIONES QUARKUS CON VERSIONES */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Package className="w-4 h-4 text-red-600" />
            <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
              2. Extensiones Quarkus 3.x: Mencionar, Aprobar o Reemplazar Versiones
            </h4>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">
              {extensions.filter((e) => e.is_selected).length} de {extensions.length} extensiones seleccionadas
            </span>
            <button
              type="button"
              onClick={() => setIsAddingExt(!isAddingExt)}
              className="flex items-center gap-1 text-xs px-2.5 py-1 rounded bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-700 dark:text-slate-300 font-semibold"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Añadir / Reemplazar</span>
            </button>
          </div>
        </div>

        {/* Formulario para añadir/reemplazar extensión personalizada */}
        {isAddingExt && (
          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 grid grid-cols-1 md:grid-cols-4 gap-2 text-xs">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">Coordenadas Maven (id):</label>
              <input
                type="text"
                placeholder="io.quarkus:quarkus-nombre"
                value={newExtId}
                onChange={(e) => setNewExtId(e.target.value)}
                className="w-full px-2 py-1.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-white"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">Nombre amigable:</label>
              <input
                type="text"
                placeholder="Ej. Quarkus Mailer"
                value={newExtName}
                onChange={(e) => setNewExtName(e.target.value)}
                className="w-full px-2 py-1.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-white"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">Versión Quarkus:</label>
              <input
                type="text"
                value={newExtVersion}
                onChange={(e) => setNewExtVersion(e.target.value)}
                className="w-full px-2 py-1.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-white font-mono"
              />
            </div>
            <div className="flex items-end gap-2">
              <button
                type="button"
                onClick={handleAddCustomExtension}
                className="w-full py-1.5 px-3 rounded bg-red-600 hover:bg-red-700 text-white font-bold"
              >
                Guardar Extensión
              </button>
            </div>
          </div>
        )}

        {/* Tabla/Lista de extensiones Quarkus con control de versiones */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500 font-semibold">
                <th className="py-2 px-2 w-10 text-center">Estado</th>
                <th className="py-2 px-2">Extensión / Artefacto</th>
                <th className="py-2 px-2">Categoría</th>
                <th className="py-2 px-2 w-28">Versión</th>
                <th className="py-2 px-2">Propósito</th>
                <th className="py-2 px-2 w-16 text-center">Acción</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {extensions.map((ext) => (
                <tr
                  key={ext.id}
                  className={`hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-colors ${
                    !ext.is_selected ? 'opacity-50' : ''
                  }`}
                >
                  <td className="py-2 px-2 text-center">
                    <input
                      type="checkbox"
                      checked={ext.is_selected}
                      onChange={() => handleToggleExtension(ext.id)}
                      disabled={ext.is_mandatory}
                      className="rounded text-red-600 focus:ring-red-500 cursor-pointer"
                    />
                  </td>
                  <td className="py-2 px-2 font-mono text-[11px] font-bold text-slate-800 dark:text-slate-200">
                    <div>{ext.name}</div>
                    <div className="text-[10px] text-slate-500 font-normal">{ext.id}</div>
                  </td>
                  <td className="py-2 px-2">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                      {ext.category}
                    </span>
                  </td>
                  <td className="py-2 px-2">
                    <input
                      type="text"
                      value={ext.version}
                      onChange={(e) => handleVersionChange(ext.id, e.target.value)}
                      className="w-24 px-1.5 py-0.5 text-[11px] font-mono rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200"
                    />
                  </td>
                  <td className="py-2 px-2 text-slate-600 dark:text-slate-400 text-[11px]">
                    {ext.description}
                  </td>
                  <td className="py-2 px-2 text-center">
                    {!ext.is_mandatory && (
                      <button
                        type="button"
                        onClick={() => handleRemoveExtension(ext.id)}
                        className="p-1 text-slate-400 hover:text-red-600 rounded transition-colors"
                        title="Eliminar o descartar extensión"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 3. PREVISUALIZADOR DEL ARQUETIPO: MAVEN vs GRADLE */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
          <div>
            <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
              3. Previsualizador Interactivo del Arquetipo (Maven vs Gradle)
            </h4>
            <p className="text-xs text-slate-500">
              Examina el archivo de configuración y la estructura de carpetas antes de la generación
            </p>
          </div>

          <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg">
            <button
              type="button"
              onClick={() => {
                setActiveArchetypeTab('maven');
                setSelectedBuildTool('maven');
              }}
              className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
                activeArchetypeTab === 'maven'
                  ? 'bg-white dark:bg-slate-900 text-red-600 shadow-sm'
                  : 'text-slate-600 dark:text-slate-400'
              }`}
            >
              Maven (pom.xml)
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveArchetypeTab('gradle');
                setSelectedBuildTool('gradle');
              }}
              className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
                activeArchetypeTab === 'gradle'
                  ? 'bg-white dark:bg-slate-900 text-red-600 shadow-sm'
                  : 'text-slate-600 dark:text-slate-400'
              }`}
            >
              Gradle (build.gradle)
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                <Code2 className="w-4 h-4 text-blue-500" />
                <span>Archivo de Configuración ({activePreview.config_file_name}):</span>
              </span>
              <span className="font-mono text-[10px] text-slate-400">Java {currentOrder.basic_data.java_version} LTS</span>
            </div>
            <pre className="p-3 rounded-lg bg-slate-950 text-slate-200 font-mono text-[11px] overflow-auto max-h-80 border border-slate-800">
              {activePreview.config_file_content}
            </pre>
          </div>

          <div className="space-y-4">
            <div>
              <span className="font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5 mb-2">
                <FolderTree className="w-4 h-4 text-amber-500" />
                <span>Estructura de Carpetas Proyectada:</span>
              </span>
              <div className="p-2.5 rounded-lg bg-slate-950 text-slate-300 font-mono text-[11px] space-y-0.5 overflow-x-auto">
                {activePreview.folder_tree.map((line, idx) => (
                  <div key={idx} className="whitespace-pre">{line}</div>
                ))}
              </div>
            </div>

            <div>
              <span className="font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5 mb-2">
                <Terminal className="w-4 h-4 text-emerald-500" />
                <span>Comandos de Ejecución:</span>
              </span>
              <div className="space-y-1.5 font-mono text-[11px]">
                <div className="p-2 rounded bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200">
                  <span className="text-slate-500"># Dev Live Coding:</span>
                  <div>{activePreview.command_dev}</div>
                </div>
                <div className="p-2 rounded bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200">
                  <span className="text-slate-500"># Pruebas & Verificación:</span>
                  <div>{activePreview.command_test}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      {/* ALERTA DE ERROR EN CASO DE FALLO */}
      {error && (
        <div className="p-4 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/60 flex items-start gap-3 text-red-700 dark:text-red-300 animate-in fade-in duration-200">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5 text-red-500" />
          <div className="flex-1 text-xs">
            <p className="font-bold text-sm">Error en la Generación del Esqueleto:</p>
            <p className="mt-1 font-mono break-words">{error}</p>
          </div>
          <button
            onClick={handleConfirmAndGenerate}
            disabled={isLoading}
            className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-medium text-xs flex items-center gap-1.5 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Reintentar
          </button>
        </div>
      )}

      {/* 4. BOTÓN DE CONFIRMACIÓN */}
      <div className="flex justify-between items-center pt-2">
        <div className="text-xs text-slate-500">
          Herramienta: <strong className="text-slate-800 dark:text-slate-200 uppercase">{selectedBuildTool}</strong> |
          Arquitectura: <strong className="text-slate-800 dark:text-slate-200">{selectedPattern}</strong> |
          Extensiones aprobadas: <strong className="text-slate-800 dark:text-slate-200">{extensions.filter((e) => e.is_selected).length}</strong>
        </div>

        <button
          type="button"
          onClick={handleConfirmAndGenerate}
          disabled={isLoading}
          className="flex items-center gap-2 px-6 py-3 rounded-xl bg-red-600 hover:bg-red-700 text-white font-bold text-sm shadow-lg hover:shadow-red-600/30 transition-all disabled:opacity-50"
        >
          {isLoading ? (
            <span>Generando código y esqueleto con Quarkus...</span>
          ) : (
            <>
              <Cpu className="w-4 h-4" />
              <span>Aprobar Extensiones y Generar Código Java/Quarkus ⚡</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
