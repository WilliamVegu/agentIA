import React, { useState } from 'react';
import { UploadCloud, FileText, CheckCircle2, AlertCircle, Send, Code } from 'lucide-react';
import { SingleRowCard } from '../components/common/SingleRowCard';
import { specService } from '../services/specService';
import { sessionService } from '../services/sessionService';
import { useStudio } from '../context/StudioContext';
import apiClient from '../services/apiClient';

export const SpecIngestionView: React.FC = () => {
  const { refreshSessions, selectSession, setActiveTab, parsedSpec, setParsedSpec, setCurrentSpecId } = useStudio();

  const [activeTabMode, setActiveTabMode] = useState<'upload' | 'json'>('upload');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [jsonText, setJsonText] = useState(
    JSON.stringify(
      {
        serviceName: "customer-billing-service",
        packageName: "com.tcs.billing",
        basePort: 8080,
        databaseMode: "PostgreSQL",
        entities: [
          {
            name: "Invoice",
            tableName: "invoices",
            attributes: [
              { name: "id", type: "Long", isPrimaryKey: true, nullable: false, validationRules: [] },
              { name: "customerId", type: "String", isPrimaryKey: false, nullable: false, validationRules: ["@NotBlank"] },
              { name: "amount", type: "BigDecimal", isPrimaryKey: false, nullable: false, validationRules: ["@NotNull"] },
              { name: "createdAt", type: "Instant", isPrimaryKey: false, nullable: true, validationRules: [] }
            ]
          }
        ],
        userStories: [
          {
            id: "US-1",
            priority: "P1",
            role: "BillingManager",
            intent: "Emit invoice for completed order",
            benefit: "Collect payment from customer",
            scenarios: [
              {
                scenarioId: "AC-1.1",
                given: "Valid order with customer ID and amount",
                when: "POST request sent to /api/v1/invoices",
                then: "Invoice is persisted and HTTP 201 Created is returned"
              }
            ]
          }
        ]
      },
      null,
      2
    )
  );

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleUploadSubmit = async () => {
    if (!selectedFile) return;
    setIsSubmitting(true);
    setFeedback(null);
    try {
      const summary = await specService.uploadFile(selectedFile);
      if (summary) {
        setParsedSpec(summary);
        if (summary.specId) setCurrentSpecId(summary.specId);
      }
      setFeedback({
        type: 'success',
        message: `Especificación "${summary?.serviceName || selectedFile.name}" procesada y validada exitosamente.`,
      });
      await refreshSessions();
    } catch (err: any) {
      setFeedback({
        type: 'error',
        message: err.response?.data?.detail || 'Error al procesar el archivo spec.md',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleJsonSubmit = async () => {
    setIsSubmitting(true);
    setFeedback(null);
    try {
      const parsed = JSON.parse(jsonText);
      const summary = await specService.submitJson(parsed);
      if (summary) {
        setParsedSpec(summary);
        if (summary.specId) setCurrentSpecId(summary.specId);
      }
      setFeedback({
        type: 'success',
        message: `Blueprint JSON "${summary?.serviceName || parsed.serviceName}" validado y registrado en el repositorio.`,
      });
      await refreshSessions();
    } catch (err: any) {
      setFeedback({
        type: 'error',
        message: err.message || 'Error sintáctico en el JSON de especificación',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Card */}
      <SingleRowCard
        title="Fase 4: Ingesta y Validación Formal de Blueprints (Spec Kit)"
        subtitle="Carga de especificaciones estandarizadas en Markdown o esquemas Blueprint en JSON"
        badge={
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300">
            OpenAPI & Blueprint
          </span>
        }
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTabMode('upload')}
              className={`py-1.5 px-3 rounded-lg text-xs font-medium transition-all ${
                activeTabMode === 'upload'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300'
              }`}
            >
              Cargar spec.md
            </button>
            <button
              onClick={() => setActiveTabMode('json')}
              className={`py-1.5 px-3 rounded-lg text-xs font-medium transition-all ${
                activeTabMode === 'json'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300'
              }`}
            >
              Pegar Blueprint JSON
            </button>
          </div>
        }
      >
        <p className="text-xs text-slate-600 dark:text-slate-400">
          Valida sintáctica y semánticamente la arquitectura antes de iniciar la compilación. Acepta documentos `spec.md` conformes a Spec Kit o esquemas declarativos JSON con tipado formal.
        </p>

        {feedback && (
          <div
            className={`mt-3 p-3 rounded-lg text-xs flex items-center gap-2 ${
              feedback.type === 'success'
                ? 'bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200'
                : 'bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200'
            }`}
          >
            {feedback.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            )}
            <span>{feedback.message}</span>
          </div>
        )}
      </SingleRowCard>

      {/* Upload Zone or JSON Editor */}
      {activeTabMode === 'upload' ? (
        <div className="p-8 border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-2xl bg-white dark:bg-slate-900/60 text-center space-y-4 shadow-sm">
          <div className="w-12 h-12 mx-auto rounded-full bg-blue-50 dark:bg-blue-950/50 flex items-center justify-center text-blue-600 dark:text-blue-400">
            <UploadCloud className="w-6 h-6" />
          </div>

          <div>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
              Seleccione o arrastre un archivo spec.md
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Formato UTF-8 compatible con Spec Kit y Markdown estándar
            </p>
          </div>

          <div className="max-w-xs mx-auto">
            <input
              type="file"
              accept=".md,.markdown,.txt"
              onChange={handleFileChange}
              className="block w-full text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-slate-800 dark:file:text-slate-200"
            />
          </div>

          {selectedFile && (
            <div className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
              Archivo seleccionado: {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
            </div>
          )}

          <div className="pt-2">
            <button
              onClick={handleUploadSubmit}
              disabled={!selectedFile || isSubmitting}
              className="py-2.5 px-6 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-all shadow-sm"
            >
              {isSubmitting ? 'Validando...' : 'Ingestar y Validar Archivo'}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <textarea
            rows={14}
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            className="w-full p-4 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-900 text-slate-100 font-mono text-xs leading-relaxed focus:ring-2 focus:ring-blue-500 focus:outline-none shadow-sm"
          />

          <div className="flex justify-end">
            <button
              onClick={handleJsonSubmit}
              disabled={isSubmitting}
              className="flex items-center gap-2 py-2.5 px-6 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-all shadow-sm"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Validar e Ingestar JSON Blueprint</span>
            </button>
          </div>
        </div>
      )}

      {/* Summary Card of Validated Specification */}
      {parsedSpec && (
        <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4 shadow-sm">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight">
            📋 Resumen de la Especificación Activa
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
              <span className="text-slate-500 dark:text-slate-400 text-xs font-medium">Microservicio</span>
              <div className="text-base font-bold text-slate-900 dark:text-white font-mono mt-1">
                {parsedSpec.serviceName}
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
              <span className="text-slate-500 dark:text-slate-400 text-xs font-medium">Entidades de Dominio</span>
              <div className="text-base font-bold text-slate-900 dark:text-white font-mono mt-1">
                {parsedSpec.entityCount || parsedSpec.entities?.length || 1}
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
              <span className="text-slate-500 dark:text-slate-400 text-xs font-medium">Historias de Usuario</span>
              <div className="text-base font-bold text-slate-900 dark:text-white font-mono mt-1">
                {parsedSpec.storyCount || parsedSpec.userStories?.length || 1}
              </div>
            </div>
          </div>

          <div className="text-xs text-blue-800 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/40 p-3 rounded-lg border border-blue-200 dark:border-blue-900/60 font-mono">
            Paquete Java configurado: <strong>{parsedSpec.packageName || 'com.tcs.microservice'}</strong> (Java 21 LTS / Spring Boot 3.x)
          </div>

          <div className="flex justify-end pt-1">
            <button
              onClick={async () => {
                if (parsedSpec?.specId) {
                  try {
                    const sessResp = await apiClient.post('/sessions', { specId: parsedSpec.specId });
                    const newSessId = sessResp.data?.sessionId || sessResp.data?.session_id;
                    if (newSessId) {
                      await refreshSessions();
                      selectSession(newSessId);
                    }
                  } catch (e) {
                    console.warn(e);
                  }
                }
                setActiveTab(5);
              }}
              className="py-2.5 px-6 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 transition-all shadow-sm"
            >
              ➡️ Proceder a Generar Microservicio
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
