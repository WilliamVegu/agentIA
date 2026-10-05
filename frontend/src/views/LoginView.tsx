import React, { useState } from 'react';
import { ShieldCheck, ArrowRight, Lock, Mail, Sparkles, Server, CheckCircle2 } from 'lucide-react';
import { ShieldCheck, ArrowRight, Lock, Mail, Sparkles, Server, CheckCircle2, Layers, Zap, LayoutGrid } from 'lucide-react';
import { TcsLogo } from '../components/common/TcsLogo';
import { useAuth } from '../context/AuthContext';
import { useLlm } from '../context/LlmContext';

export const LoginView: React.FC = () => {
  const { login, enterMvp } = useAuth();
  const { provider, setProvider } = useLlm();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleMvp = async () => {
  const handleMvp = async (targetEco: 'launcher' | 'spring' | 'quarkus' = 'launcher') => {
    setError(null);
    setIsLoading(true);
    // Explicitly guarantee the chosen ecosystem target (defaulting to the selector hub)
    localStorage.setItem('agentia_active_ecosystem', targetEco);
    sessionStorage.setItem('agentia_target_ecosystem', targetEco);
    try {
      const result = await enterMvp();
      if (!result.success) setError(result.error || 'No se pudo entrar al MVP');
    } finally {
      setIsLoading(false);
    }
  };

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
            Ingeniería de Software Automatizada para Spring Boot 3 y Quarkus 3.x en Java 21
          </h1>

          <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
            Plataforma corporativa de Tata Consultancy Services para síntesis rigurosa de código fuente, validación sandbox en contenedores aislados, auditoría SAST continua y despliegue local verificado.
            Plataforma corporativa unificada de Tata Consultancy Services para síntesis rigurosa de código fuente, validación en contenedores aislados, auditoría SAST continua y publicación atómica a Git.
          </p>

          <div className="space-y-3 pt-2">
            <div className="flex items-center gap-3 text-xs sm:text-sm text-slate-200">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Orquestación de ciclo de vida con LangGraph y auto-reparación en sandbox</span>
              <span><strong>Spring Boot Studio:</strong> Arquitectura hexagonal DDD, ingesta OpenAPI y verificación hermética</span>
            </div>
            <div className="flex items-center gap-3 text-xs sm:text-sm text-slate-200">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Quality Gate automatizado con detección de secretos y reporte SAST</span>
              <CheckCircle2 className="w-4 h-4 text-red-400 shrink-0" />
              <span><strong>Fábrica Quarkus 3.x:</strong> Orquestación de 8 agentes autónomos, auto-sanación y compuertas de control humano</span>
            </div>
            <div className="flex items-center gap-3 text-xs sm:text-sm text-slate-200">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Manifiestos DevOps listos para producción (Docker, K8s, GitHub CI/CD)</span>
              <CheckCircle2 className="w-4 h-4 text-blue-400 shrink-0" />
              <span><strong>DevOps Corporativo:</strong> Manifiestos Docker, K8s, Jenkinsfile y push directo a ramas Git con tokens efímeros</span>
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
              Acceso al estudio
            </h2>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-1">
              Ingrese con el correo y la clave de acceso configurados para este estudio.
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
                <option value="deepseek">DeepSeek</option>
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

          <div className="pt-4 border-t border-slate-200 dark:border-slate-700 space-y-2">
            <button type="button" onClick={handleMvp} disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg text-sm font-semibold text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors disabled:opacity-60">
              <Sparkles className="w-4 h-4" />
              <span>{isLoading ? 'Ingresando…' : 'Entrar al MVP'}</span>
          <div className="pt-4 border-t border-slate-200 dark:border-slate-700 space-y-2.5">
            <button
              type="button"
              onClick={() => handleMvp('launcher')}
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 shadow-md hover:shadow-blue-600/30 transition-all disabled:opacity-60 cursor-pointer"
            >
              <LayoutGrid className="w-4 h-4" />
              <span>{isLoading ? 'Ingresando…' : 'Entrar al MVP · Elegir Ecosistema (Hub)'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
            <p className="text-center text-xs text-slate-500 dark:text-slate-400">Acceso local sin correo ni contraseña.</p>

            <div className="grid grid-cols-2 gap-2 pt-1">
              <button
                type="button"
                onClick={() => handleMvp('spring')}
                disabled={isLoading}
                title="Entrar directamente a Spring Boot Studio"
                className="flex items-center justify-center gap-1.5 py-2 px-2.5 rounded-lg text-xs font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 hover:bg-emerald-100 dark:hover:bg-emerald-900/40 transition-colors disabled:opacity-60 cursor-pointer"
              >
                <Layers className="w-3.5 h-3.5 text-emerald-600" />
                <span>Spring Boot MVP</span>
              </button>

              <button
                type="button"
                onClick={() => handleMvp('quarkus')}
                disabled={isLoading}
                title="Entrar directamente a Fábrica Quarkus 3.x"
                className="flex items-center justify-center gap-1.5 py-2 px-2.5 rounded-lg text-xs font-semibold text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors disabled:opacity-60 cursor-pointer"
              >
                <Zap className="w-3.5 h-3.5 text-red-600" />
                <span>Quarkus 3.x MVP</span>
              </button>
            </div>

            <p className="text-center text-[11px] text-slate-500 dark:text-slate-400">
              Acceso local sin credenciales. Usa el botón principal para comparar ambos o entra directo al que prefieras.
            </p>
          </div>

        </div>
      </div>
    </div>
  );
};
