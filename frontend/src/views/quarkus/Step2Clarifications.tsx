import React, { useState, useEffect } from 'react';
import {
  HelpCircle,
  CheckCircle,
  ArrowRight,
  MessageSquareCode,
  Sparkles,
  Edit3,
  ListPlus,
  Save,
  Check,
  RotateCcw
} from 'lucide-react';
import { useQuarkus } from '../../context/QuarkusContext';
import { ClarificationAnswerItem } from '../../types/quarkusFactory';

export const Step2Clarifications: React.FC = () => {
  const { currentOrder, submitAnswers, isLoading, setActiveStep } = useQuarkus();

  const questions = currentOrder?.clarification_questions || [];
  const orderId = currentOrder?.id || 'draft';
  const storageKey = `quarkus_draft_answers_${orderId}`;

  // Cargar respuestas iniciales desde localStorage o del pedido
  const [answers, setAnswers] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};

    // 1. Opciones por defecto del modelo
    questions.forEach((q) => {
      if (q.user_answer) {
        initial[q.id] = q.user_answer;
      } else if (q.suggested_options && q.suggested_options.length > 0) {
        initial[q.id] = q.suggested_options[0];
      } else {
        initial[q.id] = '';
      }
    });

    // 2. Sobrescribir con borrador guardado en localStorage si existe
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed = JSON.parse(saved);
        Object.assign(initial, parsed);
      }
    } catch (e) {
      console.warn('Error reading saved draft answers:', e);
    }

    return initial;
  });

  // Modo de edición por pregunta ('suggested' vs 'custom')
  const [inputModes, setInputModes] = useState<Record<string, 'suggested' | 'custom'>>(() => {
    const modes: Record<string, 'suggested' | 'custom'> = {};
    questions.forEach((q) => {
      const currentAns = answers[q.id];
      const isSuggested = q.suggested_options.includes(currentAns);
      modes[q.id] = isSuggested ? 'suggested' : 'custom';
    });
    return modes;
  });

  // Aclaraciones adicionales personalizadas
  const [customClarifications, setCustomClarifications] = useState<string[]>(() => {
    try {
      const savedExtra = localStorage.getItem(`quarkus_extra_clarifications_${orderId}`);
      return savedExtra ? JSON.parse(savedExtra) : [];
    } catch {
      return [];
    }
  });
  const [newExtraText, setNewExtraText] = useState('');
  const [showAddExtra, setShowAddExtra] = useState(false);

  // Guardar en localStorage ante cualquier cambio para evitar pérdida de datos al navegar
  useEffect(() => {
    if (Object.keys(answers).length > 0) {
      localStorage.setItem(storageKey, JSON.stringify(answers));
    }
  }, [answers, storageKey]);

  useEffect(() => {
    localStorage.setItem(`quarkus_extra_clarifications_${orderId}`, JSON.stringify(customClarifications));
  }, [customClarifications, orderId]);

  const handleSelectOption = (questionId: string, option: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: option }));
    setInputModes((prev) => ({ ...prev, [questionId]: 'suggested' }));
  };

  const handleCustomChange = (questionId: string, text: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: text }));
    setInputModes((prev) => ({ ...prev, [questionId]: 'custom' }));
  };

  const handleAddExtraClarification = () => {
    if (newExtraText.trim()) {
      setCustomClarifications((prev) => [...prev, newExtraText.trim()]);
      setNewExtraText('');
      setShowAddExtra(false);
    }
  };

  const handleRemoveExtraClarification = (idx: number) => {
    setCustomClarifications((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload: ClarificationAnswerItem[] = Object.entries(answers).map(([id, ans]) => ({
      question_id: id,
      answer: ans,
    }));

    // Si hay aclaraciones extras agregadas por el usuario, adjuntarlas en el payload
    if (customClarifications.length > 0) {
      payload.push({
        question_id: 'extra-user-clarifications',
        answer: 'Aclaraciones adicionales del usuario:\n' + customClarifications.map((c, i) => `${i + 1}. ${c}`).join('\n')
      });
    }

    await submitAnswers(payload);
  };

  if (!currentOrder) {
    return (
      <div className="text-center p-8 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
        <p className="text-sm text-slate-500">No hay pedido activo. Por favor ingresa un pedido en el Paso 1.</p>
        <button
          onClick={() => setActiveStep(0)}
          className="mt-3 px-4 py-2 bg-red-600 text-white rounded-lg text-xs font-semibold"
        >
          Ir al Paso 1
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Banner Informativo de la Regla Clave */}
      <div className="bg-amber-500/10 border-l-4 border-amber-500 p-4 rounded-r-xl flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <HelpCircle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <span>Paso 2: Aclaración Previa con el Agente Analista</span>
              <span className="text-[11px] bg-amber-500 text-white px-2 py-0.5 rounded-full font-bold">
                Regla Clave: Preguntar antes de construir
              </span>
            </h3>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
              El Agente Analista identificó <strong>{questions.length} puntos ambiguos</strong> para el servicio{' '}
              <strong className="text-slate-800 dark:text-slate-200 font-mono">{currentOrder.basic_data.service_name}</strong>.
              Puedes escoger una de las opciones sugeridas o <strong>escribir tu propia respuesta personalizada</strong>.
            </p>
          </div>
        </div>

        {/* Indicador de autoguardado */}
        <div className="shrink-0 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-[11px] text-emerald-700 dark:text-emerald-300 font-medium">
          <Save className="w-3 h-3 text-emerald-600" />
          <span>Autoguardado activo</span>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {questions.map((q, idx) => {
          const currentAns = answers[q.id] || '';
          const currentMode = inputModes[q.id] || 'suggested';

          return (
            <div
              key={q.id}
              className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm space-y-4"
            >
              {/* Encabezado de la Pregunta */}
              <div className="flex items-start gap-3">
                <span className="w-6 h-6 rounded-full bg-red-100 dark:bg-red-950 text-red-600 dark:text-red-400 font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">
                  {idx + 1}
                </span>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                      {q.category || 'Dimensión de Negocio'}
                    </span>
                  </div>
                  <h4 className="text-sm font-bold text-slate-900 dark:text-white leading-snug">{q.question}</h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 italic">{q.context_or_reason}</p>
                </div>
              </div>

              {/* Selector de Modo: Sugerencias vs Texto Libre */}
              <div className="pl-9 space-y-3">
                <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-2">
                  <button
                    type="button"
                    onClick={() => setInputModes((prev) => ({ ...prev, [q.id]: 'suggested' }))}
                    className={`text-xs font-semibold px-2.5 py-1 rounded-md transition-all ${
                      currentMode === 'suggested'
                        ? 'bg-red-50 dark:bg-red-950/60 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-900'
                        : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                    }`}
                  >
                    💡 Opciones Sugeridas
                  </button>
                  <button
                    type="button"
                    onClick={() => setInputModes((prev) => ({ ...prev, [q.id]: 'custom' }))}
                    className={`text-xs font-semibold px-2.5 py-1 rounded-md transition-all flex items-center gap-1 ${
                      currentMode === 'custom'
                        ? 'bg-red-50 dark:bg-red-950/60 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-900'
                        : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                    }`}
                  >
                    <Edit3 className="w-3 h-3" />
                    <span>Escribir mi propia respuesta</span>
                  </button>
                </div>

                {/* Vista 1: Opciones sugeridas por el Analista */}
                {currentMode === 'suggested' && q.suggested_options && q.suggested_options.length > 0 && (
                  <div className="grid grid-cols-1 gap-2 pt-1">
                    {q.suggested_options.map((opt, optIdx) => {
                      const isSelected = currentAns === opt;
                      return (
                        <div
                          key={optIdx}
                          onClick={() => handleSelectOption(q.id, opt)}
                          className={`p-3 rounded-lg border text-xs cursor-pointer transition-all flex items-start gap-2.5 ${
                            isSelected
                              ? 'border-red-500 bg-red-50/60 dark:bg-red-950/40 text-red-900 dark:text-red-200 font-medium shadow-sm ring-1 ring-red-400'
                              : 'border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50 text-slate-700 dark:text-slate-300'
                          }`}
                        >
                          <div
                            className={`w-4 h-4 rounded-full border flex items-center justify-center shrink-0 mt-0.5 ${
                              isSelected ? 'border-red-600 bg-red-600 text-white' : 'border-slate-400'
                            }`}
                          >
                            {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                          </div>
                          <span className="leading-relaxed flex-1">{opt}</span>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Vista 2: Input para respuesta personalizada escrita libremente */}
                {currentMode === 'custom' && (
                  <div className="space-y-1.5 pt-1">
                    <label className="text-[11px] font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                      <Edit3 className="w-3.5 h-3.5 text-red-500" />
                      <span>Ingresa tu respuesta o aclaración exacta de negocio:</span>
                    </label>
                    <textarea
                      rows={2}
                      value={currentAns}
                      onChange={(e) => handleCustomChange(q.id, e.target.value)}
                      placeholder="Escribe aquí con tus palabras la regla o condición que debe implementar el microservicio..."
                      className="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-xs outline-none focus:ring-2 focus:ring-red-500 shadow-inner"
                      required
                    />
                  </div>
                )}

                {/* Resumen de la respuesta activa */}
                <div className="pt-1 flex items-start gap-2 text-[11px] text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/40 p-2.5 rounded-lg border border-slate-200/60 dark:border-slate-800/60">
                  <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                  <span className="leading-snug">
                    <strong className="text-slate-700 dark:text-slate-300">Respuesta acordada:</strong>{' '}
                    {currentAns || <span className="italic text-amber-600 dark:text-amber-400">Sin respuesta aún (selecciona o escribe arriba)</span>}
                  </span>
                </div>
              </div>
            </div>
          );
        })}

        {/* Sección para añadir aclaraciones adicionales personalizadas */}
        <div className="bg-slate-50 dark:bg-slate-900/60 border border-dashed border-slate-300 dark:border-slate-700 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ListPlus className="w-4 h-4 text-red-500" />
              <h5 className="text-xs font-bold text-slate-800 dark:text-slate-200">
                Aclaraciones o Reglas Adicionales (Opcional)
              </h5>
            </div>
            {!showAddExtra && (
              <button
                type="button"
                onClick={() => setShowAddExtra(true)}
                className="text-xs text-red-600 hover:text-red-700 font-semibold flex items-center gap-1"
              >
                <span>➕ Añadir otra aclaración</span>
              </button>
            )}
          </div>

          {customClarifications.length > 0 && (
            <div className="space-y-2">
              {customClarifications.map((item, i) => (
                <div key={i} className="flex items-center justify-between text-xs p-2 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                  <span>• {item}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveExtraClarification(i)}
                    className="text-red-500 hover:text-red-700 text-[11px] font-bold px-2 py-0.5"
                  >
                    Eliminar
                  </button>
                </div>
              ))}
            </div>
          )}

          {showAddExtra && (
            <div className="space-y-2 pt-2 border-t border-slate-200 dark:border-slate-800">
              <textarea
                rows={2}
                value={newExtraText}
                onChange={(e) => setNewExtraText(e.target.value)}
                placeholder="Escribe otra regla de negocio, restricción o campo específico que deseas agregar..."
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-xs outline-none focus:ring-2 focus:ring-red-500"
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddExtra(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-600 dark:text-slate-400"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleAddExtraClarification}
                  className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white text-xs font-semibold"
                >
                  Guardar Aclaración
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Botón de Envío */}
        <div className="flex items-center justify-between pt-2">
          <button
            type="button"
            onClick={() => setActiveStep(0)}
            className="px-4 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
          >
            ← Volver al Paso 1
          </button>

          <button
            type="submit"
            disabled={isLoading}
            className="flex items-center gap-2 px-6 py-3 rounded-xl bg-red-600 hover:bg-red-700 text-white font-bold text-sm shadow-lg hover:shadow-red-600/30 transition-all disabled:opacity-50"
          >
            {isLoading ? (
              <span>Diseñando contrato OpenAPI, Historias y Base de Datos...</span>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Confirmar Respuestas y Redactar Contrato + Modelo de Datos</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
