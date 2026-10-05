import React, { useState } from 'react';
import {
  FileText,
  Cpu,
  Layers,
  Sparkles,
  Paperclip,
  Check,
  Send,
  Database,
  Lock,
  Key,
  RotateCcw,
  Zap,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  ShieldCheck,
  Code
} from 'lucide-react';
import { useQuarkus } from '../../context/QuarkusContext';
import { useLlm, RECOMMENDED_MODELS } from '../../context/LlmContext';
import {
  CreateOrderRequest,
  BuildTool,
  DatabaseType,
  SecurityType
} from '../../types/quarkusFactory';
import { LlmProviderType } from '../../types';

export const Step1OrderInput: React.FC = () => {
  const { createNewOrder, isLoading, error: quarkusError } = useQuarkus();
  const {
    provider,
    apiKey,
    model,
    isVerified,
    statusMessage,
    isVerifying,
    setProvider,
    setApiKey,
    setModel,
    verifyConnection
  } = useLlm();

  // Estados del formulario (Inician completamente vacíos para tu propio microservicio)
  // Bloque 1: Datos Básicos
  const [serviceName, setServiceName] = useState('');
  const [team, setTeam] = useState('');
  const [groupId, setGroupId] = useState('');
  const [javaVersion, setJavaVersion] = useState('21');
  const [buildTool, setBuildTool] = useState<BuildTool>('maven');

  // Bloque 2: Qué debe hacer (Texto libre de negocio)
  const [businessDesc, setBusinessDesc] = useState('');

  // Bloque 3: Requisitos Técnicos
  const [database, setDatabase] = useState<DatabaseType>('SQLite (Demo local portable)');
  const [security, setSecurity] = useState<SecurityType>('JWT (SmallRye JWT)');
  const [enableKafka, setEnableKafka] = useState(false);

  // Bloque Adjuntos (Opcional)
  const [existingOpenApi, setExistingOpenApi] = useState('');
  const [hasAttachment, setHasAttachment] = useState(false);

  // Acordeón de configuración de LLM en línea
  const [showLlmConfig, setShowLlmConfig] = useState(false);
  const [tempKey, setTempKey] = useState(apiKey);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Criterios de Validación en Tiempo Real
  const cleanService = serviceName.trim().toLowerCase();
  const cleanTeam = team.trim();
  const cleanGroupId = groupId.trim();
  const cleanDesc = businessDesc.trim();

  const isServiceNameValid = cleanService.length >= 3 && /^[a-z0-9]+(-[a-z0-9]+)*$/.test(cleanService);
  const isTeamValid = cleanTeam.length >= 2;
  const isGroupIdValid = cleanGroupId.length >= 3 && /^[a-z0-9_]+(\.[a-z0-9_]+)*$/.test(cleanGroupId);
  const isDescValid = cleanDesc.length >= 30;
  const isDbValid = Boolean(database);
  const isSecurityValid = Boolean(security);

  const allCriteriaValid = isServiceNameValid && isTeamValid && isGroupIdValid && isDescValid && isDbValid && isSecurityValid;

  const handleClearForm = () => {
    setServiceName('');
    setTeam('');
    setGroupId('');
    setBusinessDesc('');
    setExistingOpenApi('');
    setHasAttachment(false);
    setValidationError(null);
  };

  const handleSaveLlmKey = async () => {
    setApiKey(tempKey);
    await verifyConnection(tempKey, provider, model);
  };

  // Helper para sugerencias rápidas en la descripción
  const handleAppendSuggestion = (hint: string) => {
    setBusinessDesc((prev) => {
      const trimmed = prev.trim();
      return trimmed ? `${trimmed} ${hint}` : hint;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (!isServiceNameValid) {
      setValidationError('El nombre del microservicio debe tener al menos 3 caracteres y usar formato kebab-case (ejemplo: inventario-service o pagos-api).');
      return;
    }
    if (!isTeamValid) {
      setValidationError('Especifica el equipo o área propietaria responsable del microservicio.');
      return;
    }
    if (!isGroupIdValid) {
      setValidationError('El GroupId debe tener formato de paquete Java válido (ejemplo: com.empresa.servicio).');
      return;
    }
    if (!isDescValid) {
      setValidationError('La descripción de negocio debe contener al menos 30 caracteres para que la IA cuente con contexto suficiente para sintetizar el contrato OpenAPI.');
      return;
    }

    // Payload de envío (Bloque 4 se desacopla de la UI pero se envía con valores estándar para el orquestador)
    const req: CreateOrderRequest = {
      basic_data: {
        service_name: cleanService,
        team: cleanTeam,
        group_id: cleanGroupId,
        java_version: javaVersion,
        build_tool: buildTool
      },
      business: {
        description: cleanDesc
      },
      technical: {
        database,
        security,
        enable_kafka: enableKafka,
        integraciones: []
      },
      ai_mode: {
        mode: 'Medio',
        estimated_tokens_min: 0,
        estimated_tokens_max: 0
      },
      attachments: {
        existing_openapi: hasAttachment ? existingOpenApi : null,
        support_docs: []
      }
    };

    try {
      await createNewOrder(req);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Error al conectar con el motor de IA';
      setValidationError(detail);
    }
  };

  const activeError = validationError || quarkusError;

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-5xl mx-auto">
      {/* Encabezado descriptivo con barra de estado de IA */}
      <div className="bg-gradient-to-r from-red-600/10 via-red-500/5 to-transparent border-l-4 border-red-600 p-4 rounded-r-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <span>Paso 1: Entrada del Pedido de Microservicio</span>
            <span className="text-xs bg-red-600 text-white px-2 py-0.5 rounded-full font-semibold">
              Generación 100% Dinámica por IA
            </span>
          </h3>
          <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
            Ingresa los datos y requerimientos de tu microservicio desde cero. La IA analizará la información para interrogarte en el Paso 2
            a través de las 12 dimensiones de negocio y generar el contrato OpenAPI, historias de usuario BDD y el modelo relacional de base de datos.
          </p>
        </div>

        {/* Botón de limpiar formulario */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={handleClearForm}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 text-xs font-semibold shadow-sm transition-all"
            title="Limpiar todos los campos"
          >
            <RotateCcw className="w-3.5 h-3.5 text-slate-500" />
            <span>Limpiar Formulario</span>
          </button>
        </div>
      </div>

      {activeError && (
        <div className="bg-red-50 dark:bg-red-950/50 border-2 border-red-500 dark:border-red-700 text-red-900 dark:text-red-200 p-4 rounded-xl text-xs font-semibold flex items-start gap-3 shadow-md">
          <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-bold text-sm block">Error de Generación por IA / Validación:</span>
            <p className="font-mono text-xs leading-relaxed text-red-800 dark:text-red-300">{activeError}</p>
          </div>
        </div>
      )}

      {/* CARD DE ESTADO DEL MODELO LLM Y API KEY */}
      <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className={`w-3 h-3 rounded-full ${provider !== 'mock' && isVerified ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
            <div>
              <span className="text-xs font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                Motor LLM: <span className="uppercase text-red-600 dark:text-red-400 font-mono">{provider}</span>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-normal">
                  {model}
                </span>
              </span>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                {statusMessage}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setShowLlmConfig(!showLlmConfig)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-300 transition-all"
          >
            <Key className="w-3.5 h-3.5 text-amber-500" />
            <span>{showLlmConfig ? 'Ocultar Configuración LLM' : 'Configurar mi API Key'}</span>
          </button>
        </div>

        {/* Panel Desplegable de Configuración de API Key */}
        {showLlmConfig && (
          <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-800 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">Proveedor de IA</label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value as LlmProviderType)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
              >
                <option value="gemini">Google Gemini (Recomendado)</option>
                <option value="deepseek">DeepSeek (V3 / R1)</option>
                <option value="groq">Groq Cloud (Llama 3 ultra rápido)</option>
                <option value="openai">OpenAI (ChatGPT / GPT-4o)</option>
                <option value="mock">Modo Offline (Simulador local sin internet)</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">Modelo de IA</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
              >
                {RECOMMENDED_MODELS[provider]?.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                )) || <option value={model}>{model}</option>}
              </select>
            </div>

            <div>
              <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">API Key Personal</label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={tempKey}
                  onChange={(e) => setTempKey(e.target.value)}
                  placeholder="Pega tu clave (ej. AIzaSy...)"
                  className="flex-1 px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                />
                <button
                  type="button"
                  onClick={handleSaveLlmKey}
                  disabled={isVerifying}
                  className="px-3 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-semibold disabled:opacity-50"
                >
                  {isVerifying ? 'Probando...' : 'Guardar'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* BLOQUE 1: DATOS BÁSICOS */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-red-100 dark:bg-red-900/50 text-red-600 dark:text-red-400 flex items-center justify-center text-xs font-bold">1</div>
            <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">Bloque 1: Datos Básicos del Microservicio</h4>
          </div>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">Identificación técnica Java Quarkus</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1 flex items-center justify-between">
              <span>Nombre del Microservicio *</span>
              {isServiceNameValid ? (
                <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-0.5 text-[10px] font-bold">
                  <CheckCircle2 className="w-3 h-3" /> Válido
                </span>
              ) : (
                <span className="text-amber-500 text-[10px]">kebab-case</span>
              )}
            </label>
            <input
              type="text"
              value={serviceName}
              onChange={(e) => {
                const val = e.target.value;
                setServiceName(val);
                if (!groupId || groupId.startsWith('com.empresa.')) {
                  setGroupId(`com.empresa.${val.toLowerCase().replace(/[^a-z0-9]/g, '')}`);
                }
              }}
              placeholder="ej: billing-service, inventario-api, citas-service"
              className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none font-mono"
              required
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1 flex items-center justify-between">
              <span>Equipo / Área Propietaria *</span>
              {isTeamValid && (
                <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-0.5 text-[10px] font-bold">
                  <CheckCircle2 className="w-3 h-3" />
                </span>
              )}
            </label>
            <input
              type="text"
              value={team}
              onChange={(e) => setTeam(e.target.value)}
              placeholder="ej: Operaciones, Pagos Core, Logística"
              className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none"
              required
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1 flex items-center justify-between">
              <span>GroupId Maven / Gradle *</span>
              {isGroupIdValid && (
                <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-0.5 text-[10px] font-bold">
                  <CheckCircle2 className="w-3 h-3" />
                </span>
              )}
            </label>
            <input
              type="text"
              value={groupId}
              onChange={(e) => setGroupId(e.target.value)}
              placeholder="ej: com.miempresa.servicio"
              className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none font-mono"
              required
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs pt-1">
          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Versión de Java
            </label>
            <select
              value={javaVersion}
              onChange={(e) => setJavaVersion(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none"
            >
              <option value="21">Java 21 LTS (Recomendado - Records, Virtual Threads, Pattern Matching)</option>
              <option value="17">Java 17 LTS</option>
              <option value="11">Java 11</option>
            </select>
          </div>

          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Herramienta de Construcción (Build Tool)
            </label>
            <div className="flex gap-4 pt-1">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="buildTool"
                  value="maven"
                  checked={buildTool === 'maven'}
                  onChange={() => setBuildTool('maven')}
                  className="text-red-600 focus:ring-red-500"
                />
                <span className="font-medium text-slate-700 dark:text-slate-300">Maven (pom.xml)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="buildTool"
                  value="gradle"
                  checked={buildTool === 'gradle'}
                  onChange={() => setBuildTool('gradle')}
                  className="text-red-600 focus:ring-red-500"
                />
                <span className="font-medium text-slate-700 dark:text-slate-300">Gradle (build.gradle)</span>
              </label>
            </div>
          </div>
        </div>
      </div>

      {/* BLOQUE 2: QUÉ DEBE HACER (TEXTO LIBRE DE NEGOCIO) */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm space-y-3">
        <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-emerald-100 dark:bg-emerald-900/50 text-emerald-600 dark:text-emerald-400 flex items-center justify-center text-xs font-bold">2</div>
            <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">Bloque 2: Qué debe hacer (Lógica y Reglas de Negocio) *</h4>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-[11px] font-mono font-bold px-2 py-0.5 rounded ${
              isDescValid ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300' : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
            }`}>
              {cleanDesc.length} / 30 caracteres mín.
            </span>
          </div>
        </div>

        <p className="text-xs text-slate-500 dark:text-slate-400">
          Describe con tus propias palabras qué problema resuelve el servicio, qué entidades maneja, sus operaciones principales y reglas de negocio.
        </p>

        <textarea
          rows={4}
          value={businessDesc}
          onChange={(e) => setBusinessDesc(e.target.value)}
          placeholder="Ejemplo: Microservicio para gestión de citas médicas y pacientes. Permite agendar citas, verificar disponibilidad de médicos por especialidad, registrar diagnósticos y recetas. Las citas en estado 'CONFIRMADA' no pueden eliminarse sin motivo médico registrado..."
          className="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white text-xs focus:ring-2 focus:ring-emerald-500 outline-none leading-relaxed"
          required
        />

        {/* Guías rápidas para enriquecer la entrada */}
        <div className="pt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
          <span className="font-semibold flex items-center gap-1 text-slate-600 dark:text-slate-300">
            <Sparkles className="w-3 h-3 text-amber-500" /> Ideas para incluir:
          </span>
          <button
            type="button"
            onClick={() => handleAppendSuggestion('Debe incluir tabla principal y tabla de detalle asociada con clave foránea.')}
            className="px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
          >
            + Detalle / Items
          </button>
          <button
            type="button"
            onClick={() => handleAppendSuggestion('Estados del proceso: PENDIENTE, EN_PROCESO, FINALIZADO y CANCELADO.')}
            className="px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
          >
            + Ciclo de Estados
          </button>
          <button
            type="button"
            onClick={() => handleAppendSuggestion('Validar que los montos sean mayores a cero y que el código identificador sea único.')}
            className="px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
          >
            + Validaciones de Negocio
          </button>
        </div>
      </div>

      {/* BLOQUE 3: REQUISITOS TÉCNICOS & PERSISTENCIA */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-purple-100 dark:bg-purple-900/50 text-purple-600 dark:text-purple-400 flex items-center justify-center text-xs font-bold">3</div>
            <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">Bloque 3: Requisitos Técnicos, Base de Datos & Seguridad</h4>
          </div>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">Pila tecnológica del contenedor</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-purple-500" />
              <span>Base de Datos y Persistencia Panache *</span>
            </label>
            <select
              value={database}
              onChange={(e) => setDatabase(e.target.value as DatabaseType)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-purple-500 outline-none"
            >
              <option value="SQLite (Demo local portable)">SQLite (Demo local portable - Zero setup en cualquier máquina)</option>
              <option value="PostgreSQL">PostgreSQL (Recomendado para producción)</option>
              <option value="SQL Server">SQL Server (Estándar corporativo)</option>
              <option value="Azure SQL">Azure SQL Database</option>
              <option value="H2 (En memoria)">H2 Database (En memoria)</option>
              <option value="MySQL">MySQL / MariaDB</option>
            </select>
          </div>

          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
              <Lock className="w-3.5 h-3.5 text-blue-500" />
              <span>Seguridad y Autenticación *</span>
            </label>
            <select
              value={security}
              onChange={(e) => setSecurity(e.target.value as SecurityType)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none"
            >
              <option value="JWT (SmallRye JWT)">JWT (Quarkus SmallRye JWT + MicroProfile)</option>
              <option value="OAuth2 / OIDC">OAuth2 / OpenID Connect (Quarkus OIDC)</option>
              <option value="Sin autenticación">Sin autenticación (Endpoints públicos)</option>
            </select>
          </div>
        </div>

        <div className="pt-1">
          <label className="flex items-center gap-2 cursor-pointer p-2.5 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
            <input
              type="checkbox"
              checked={enableKafka}
              onChange={(e) => setEnableKafka(e.target.checked)}
              className="rounded text-red-600 focus:ring-red-500 w-4 h-4"
            />
            <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
              Habilitar Mensajería asíncrona con Apache Kafka (SmallRye Reactive Messaging)
            </span>
          </label>
        </div>
      </div>

      {/* BLOQUE 4: ADJUNTOS OPCIONALES */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm space-y-3">
        <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 flex items-center justify-center text-xs font-bold">4</div>
            <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">Bloque 4: Adjuntos Opcionales (OpenAPI Preexistente)</h4>
          </div>
          <span className="text-[11px] text-slate-500">Opcional</span>
        </div>

        <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold text-slate-700 dark:text-slate-300">
          <input
            type="checkbox"
            checked={hasAttachment}
            onChange={(e) => setHasAttachment(e.target.checked)}
            className="rounded text-red-600 focus:ring-red-500"
          />
          <span>Ya dispongo de un contrato OpenAPI 3.1 previo (adoptar directamente para revisión en el Paso 2)</span>
        </label>

        {hasAttachment && (
          <textarea
            rows={5}
            value={existingOpenApi}
            onChange={(e) => setExistingOpenApi(e.target.value)}
            placeholder="openapi: 3.1.0&#10;info:&#10;  title: Mi API&#10;  version: 1.0.0..."
            className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-950 text-emerald-400 font-mono text-xs outline-none"
          />
        )}
      </div>

      {/* PANEL DE VALIDACIÓN DE CRITERIOS EN VIVO (VALIDADOR EXIGIDO POR EL USUARIO) */}
      <div className={`p-4 rounded-xl border-2 transition-all ${
        allCriteriaValid
          ? 'bg-emerald-50/50 dark:bg-emerald-950/20 border-emerald-300 dark:border-emerald-800'
          : 'bg-amber-50/50 dark:bg-amber-950/20 border-amber-300 dark:border-amber-800'
      }`}>
        <div className="flex items-center justify-between mb-3 border-b border-slate-200/60 dark:border-slate-700/60 pb-2">
          <h5 className="text-xs font-bold uppercase tracking-wider flex items-center gap-2 text-slate-800 dark:text-slate-200">
            <ShieldCheck className={`w-4 h-4 ${allCriteriaValid ? 'text-emerald-600' : 'text-amber-500'}`} />
            <span>Validador de Criterios del Pedido para la IA</span>
          </h5>
          <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
            allCriteriaValid
              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200'
              : 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200'
          }`}>
            {allCriteriaValid ? '✓ Listo para análisis con IA' : 'Faltan criterios obligatorios'}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2.5 text-xs">
          <div className="flex items-center gap-2">
            {isServiceNameValid ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-amber-500 shrink-0" />
            )}
            <span className={isServiceNameValid ? 'text-slate-700 dark:text-slate-300' : 'text-amber-700 dark:text-amber-400 font-medium'}>
              Nombre técnico kebab-case
            </span>
          </div>

          <div className="flex items-center gap-2">
            {isTeamValid ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-amber-500 shrink-0" />
            )}
            <span className={isTeamValid ? 'text-slate-700 dark:text-slate-300' : 'text-amber-700 dark:text-amber-400 font-medium'}>
              Equipo propietario
            </span>
          </div>

          <div className="flex items-center gap-2">
            {isGroupIdValid ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-amber-500 shrink-0" />
            )}
            <span className={isGroupIdValid ? 'text-slate-700 dark:text-slate-300' : 'text-amber-700 dark:text-amber-400 font-medium'}>
              GroupId Java válido
            </span>
          </div>

          <div className="flex items-center gap-2">
            {isDescValid ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-amber-500 shrink-0" />
            )}
            <span className={isDescValid ? 'text-slate-700 dark:text-slate-300' : 'text-amber-700 dark:text-amber-400 font-medium'}>
              Descripción (≥ 30 caracteres)
            </span>
          </div>
        </div>
      </div>

      {/* BOTÓN DE ACCIÓN PARA PASAR AL PASO 2 */}
      <div className="flex items-center justify-between pt-2">
        <p className="text-xs text-slate-500">
          Al enviar, el <strong>Agente Analista</strong> sintetizará directamente el contrato OpenAPI 3.1, Historias de Usuario BDD y Modelo Relacional sin cuestionarios.
        </p>

        <button
          type="submit"
          disabled={isLoading || !allCriteriaValid}
          className="flex items-center gap-2 px-6 py-3 rounded-xl bg-red-600 hover:bg-red-700 text-white font-bold text-sm shadow-lg hover:shadow-red-600/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <span>Sintetizando Contrato OpenAPI con IA...</span>
          ) : (
            <>
              <span>Generar y Revisar Contrato OpenAPI (Paso 2)</span>
              <Send className="w-4 h-4" />
            </>
          )}
        </button>
      </div>
    </form>
  );
};
