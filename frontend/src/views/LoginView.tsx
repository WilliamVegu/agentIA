import React, { useState } from 'react';
import { ShieldCheck, ArrowRight, Lock, Mail, Sparkles, Server, CheckCircle2 } from 'lucide-react';
import { TcsLogo } from '../components/common/TcsLogo';
import { useAuth } from '../context/AuthContext';
import { useLlm } from '../context/LlmContext';

export const LoginView: React.FC = () => {
  const { login, loginDemo } = useAuth();
  const { provider, setProvider } = useLlm();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const res = await login(email, password);
      if (!res.success) {
        setError(res.error || 'Error al iniciar sesión');
      }
    } catch {
      setError('Error de comunicación con el servicio de autenticación');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex flex-col lg:flex-row bg-slate-50 dark:bg-slate-950 transition-colors">
      {/* Columna Hero Izquierda (50% en pantallas grandes) */}
      <div className="lg:w-1/2 bg-gradient-to-br from-slate-950 via-slate-900 to-blue-950 p-8 sm:p-12 lg:p-16 flex flex-col justify-between text-white relative overflow-hidden">
        {/* Subtle decorative grid overlay */}
        <div className="absolute inset-0 bg-[radial-gradient(#0076CE_1px,transparent_1px)] [background-size:24px_24px] opacity-15 pointer-events-none" />

        {/* Top: TCS Brand Logo */}
        <div className="relative z-10">
          <TcsLogo variant="login" showSubtitle={true} />
        </div>

        {/* Center: Real Value Proposition (Anti-AI Copywriting) */}
        <div className="relative z-10 my-12 space-y-6 max-w-xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-400/30">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Generador Autónomo de Microservicios Empresariales</span>
          </div>

          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-white leading-tight">
            Ingeniería de Software Automatizada para Arquitecturas Spring Boot 3 y Java 21
          </h1>

          <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
            Plataforma corporativa de Tata Consultancy Services para síntesis rigurosa de código fuente, validación sandbox en contenedores aislados, auditoría SAST continua y despliegue local verificado.
          </p>

          <div className="space-y-3 pt-2">
            <div className="flex items-center gap-3 text-xs sm:text-sm text-slate-200">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Orquestación de ciclo de vida con LangGraph y auto-reparación en sandbox</span>
            </div>
            <div className="flex items-center gap-3 text-xs sm:text-sm text-slate-200">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Quality Gate automatizado con detección de secretos y reporte SAST</span>
            </div>
            <div className="flex items-center gap-3 text-xs sm:text-sm text-slate-200">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Manifiestos DevOps listos para producción (Docker, K8s, GitHub CI/CD)</span>
            </div>
          </div>
        </div>

        {/* Bottom: Compliance Badge */}
        <div className="relative z-10 pt-6 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-blue-400" />
            <span>TCS Global Enterprise Security Standard</span>
          </div>
          <span>Sprint 1 · v1.0.0</span>
        </div>
      </div>

      {/* Columna Formulario Derecha (50% en pantallas grandes) */}
      <div className="lg:w-1/2 flex items-center justify-center p-6 sm:p-12 bg-white dark:bg-slate-900 transition-colors">
        <div className="w-full max-w-md space-y-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
              Acceso Corporativo
            </h2>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-1">
              Ingrese con sus credenciales institucionales de Tata Consultancy Services.
            </p>
          </div>

          {error && (
            <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-700 dark:text-rose-300">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Correo Electrónico Corporativo
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="usuario@tcs.com"
                  required
                  className="w-full pl-9 pr-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-xs focus:ring-2 focus:ring-blue-600 focus:outline-none transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Contraseña de Dominio
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full pl-9 pr-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-xs focus:ring-2 focus:ring-blue-600 focus:outline-none transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Motor de Inferencia Inicial
              </label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value as any)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-xs focus:ring-2 focus:ring-blue-600 focus:outline-none"
              >
                <option value="mock">Modo Offline (Mock Engine Local - Sin Consumo)</option>
                <option value="gemini">Google Gemini (gemini-3.6-flash)</option>
                <option value="groq">Groq Cloud (qwen/qwen3.8-27b)</option>
                <option value="openai">OpenAI (gpt-4o-mini)</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 shadow-md transition-all disabled:opacity-60 cursor-pointer"
            >
              <span>Ingresar al Studio</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          {/* 1-Click Demo Login Button (User Feedback #2) */}
          <div className="pt-3 border-t border-slate-200 dark:border-slate-800 space-y-2">
            <div className="text-center text-[11px] text-slate-500 dark:text-slate-400">
              ¿Desea explorar el entorno inmediatamente sin ingresar credenciales?
            </div>
            <button
              type="button"
              onClick={loginDemo}
              className="w-full py-2 px-4 rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-300 dark:border-slate-700 transition-colors"
            >
              Acceso Rápido de Demostración (1-Click Demo)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
