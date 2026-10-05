import React, { useState } from 'react';
import { BookOpen, FileText, ArrowRight, CheckCircle2 } from 'lucide-react';
import { useQuarkus } from '../../context/QuarkusContext';

export const Step6Documentation: React.FC = () => {
  const { currentOrder, setActiveStep } = useQuarkus();

  const docs = currentOrder?.documentation || {};
  const docKeys = Object.keys(docs);

  const [activeDoc, setActiveDoc] = useState<string>(docKeys[0] || 'README.md');

  if (!currentOrder || docKeys.length === 0) {
    return (
      <div className="text-center p-8 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
        <p className="text-sm text-slate-500">
          La documentación oficial aún no ha sido generada. Completa el Paso 5 primero.
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
      {/* Banner */}
      <div className="bg-gradient-to-r from-purple-600/10 via-purple-500/5 to-transparent border-l-4 border-purple-600 p-4 rounded-r-xl">
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-purple-600 dark:text-purple-400" />
          <h3 className="text-sm font-bold text-slate-900 dark:text-white">
            Paso 5: Documentación Generada por el Agente Documentador
          </h3>
          <span className="text-xs bg-purple-600 text-white px-2 py-0.5 rounded-full font-semibold">
            5 Documentos Oficiales
          </span>
        </div>
        <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
          Cada microservicio se entrega con su suite documental completa, generada en todos los modos de IA.
        </p>
      </div>

      {/* Tabs de Documentos */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {docKeys.map((docName) => (
          <button
            key={docName}
            onClick={() => setActiveDoc(docName)}
            className={`px-3 py-2 rounded-lg text-xs font-bold whitespace-nowrap transition-all flex items-center gap-1.5 border ${
              activeDoc === docName
                ? 'bg-purple-600 text-white border-purple-700 shadow-sm'
                : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800 hover:bg-slate-50'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>{docName}</span>
          </button>
        ))}
      </div>

      {/* Visor Markdown del Documento */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="px-4 py-2 bg-slate-100 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center text-xs">
          <span className="font-mono font-bold text-slate-700 dark:text-slate-300">{activeDoc}</span>
          <span className="text-[11px] text-slate-500">Agente Documentador · Markdown</span>
        </div>
        <pre className="p-5 font-mono text-xs bg-slate-950 text-slate-200 overflow-x-auto max-h-[500px] leading-relaxed whitespace-pre-wrap">
          {docs[activeDoc]}
        </pre>
      </div>

      {/* Navegación al Control 2 */}
      <div className="flex justify-end pt-2">
        <button
          onClick={() => setActiveStep(5)}
          className="flex items-center gap-2 px-6 py-3 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-bold text-sm shadow-lg hover:shadow-amber-600/30 transition-all"
        >
          <span>Ir al Control Humano 2: Revisión Final de Entrega (Paso 6)</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

