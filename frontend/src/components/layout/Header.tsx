import React, { useState, useEffect } from 'react';
import {
  Sun,
  Moon,
  Cpu,
  Server,
  LogOut,
  CheckCircle2,
  AlertCircle,
  ArrowLeftRight,
  Layers,
  Zap,
} from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';
import { useLlm } from '../../context/LlmContext';
import { useEcosystem } from '../../context/EcosystemContext';
import { llmService } from '../../services/llmService';

interface HeaderProps {
  onOpenSettings?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onOpenSettings }) => {
  const { theme, toggleTheme } = useTheme();
  const { user, logout, isAutomaticAccess } = useAuth();
  const { provider, model, isVerified } = useLlm();
  const { activeEcosystem, goToLauncher, goToSpring, goToQuarkus } = useEcosystem();

  const [backendHealth, setBackendHealth] = useState<'UP' | 'DOWN' | 'CHECKING'>('CHECKING');

  useEffect(() => {
    let isMounted = true;
    const check = async () => {
      try {
        const res = await llmService.checkHealth();
        if (isMounted) {
          setBackendHealth(res.status === 'UP' ? 'UP' : 'DOWN');
        }
      } catch {
        if (isMounted) setBackendHealth('DOWN');
      }
    };
    check();
    const interval = setInterval(check, 15000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="sticky top-0 z-30 h-16 w-full bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border-b border-slate-200/90 dark:border-slate-800 px-4 sm:px-6 flex items-center justify-between transition-colors shadow-xs">
      {/* Left: Branding & Ecosystem Switcher */}
      <div className="flex items-center gap-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 hidden lg:inline-block">
          TCS Microservices
        </span>
        <span className="text-slate-300 dark:text-slate-700 hidden lg:inline-block">/</span>

        {/* Persistent 3-Way Ecosystem Quick Switcher */}
        <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800/90 p-1 rounded-xl border border-slate-200/80 dark:border-slate-700/80">
          <button
            onClick={goToLauncher}
            title="Ir al Hub Selector de Ecosistemas"
            aria-label="Cambiar de ecosistema (Hub Selector)"
            className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
              activeEcosystem === 'launcher'
                ? 'bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            Hub Selector
          </button>

          <button
            onClick={goToSpring}
            title="Cambiar a Spring Boot Studio"
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
              activeEcosystem === 'spring'
                ? 'bg-emerald-600 text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:text-emerald-700 dark:hover:text-emerald-400'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Spring Boot</span>
          </button>

          <button
            onClick={goToQuarkus}
            title="Cambiar a Fábrica Quarkus 3.x"
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
              activeEcosystem === 'quarkus'
                ? 'bg-red-600 text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:text-red-700 dark:hover:text-red-400'
            }`}
          >
            <Zap className="w-3.5 h-3.5" />
            <span>Quarkus</span>
          </button>
        </div>
      </div>

      {/* Right: Controls & Badges */}
      <div className="flex items-center gap-3">
        {/* Backend Health Status */}
        <div
          className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
          title={`Backend FastAPI: ${backendHealth}`}
        >
          <Server className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
          <span>FastAPI</span>
          {backendHealth === 'UP' ? (
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          ) : backendHealth === 'DOWN' ? (
            <span className="w-2 h-2 rounded-full bg-rose-500" />
          ) : (
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
          )}
        </div>

        {/* LLM Engine Badge (Clickable to open settings) */}
        <button
          onClick={onOpenSettings}
          className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-all ${
            isVerified
              ? 'bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800'
              : 'bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800'
          }`}
          title="Configuración de Motor LLM"
        >
          <Cpu className="w-3.5 h-3.5" />
          <span className="font-semibold uppercase text-[11px]">{provider}</span>
          <span className="text-[10px] text-slate-500 dark:text-slate-400 hidden lg:inline">({model})</span>
          {isVerified ? (
            <CheckCircle2 className="w-3 h-3 text-emerald-500" />
          ) : (
            <AlertCircle className="w-3 h-3 text-amber-500" />
          )}
        </button>

        {/* Theme Toggle Button */}
        <button
          type="button"
          onClick={toggleTheme}
          className="p-2 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          title={theme === 'dark' ? 'Cambiar a Modo Claro' : 'Cambiar a Modo Oscuro'}
        >
          {theme === 'dark' ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-slate-600" />
          )}
        </button>

        {/* User Profile & Logout */}
        {user && (
          <div className="flex items-center gap-2 pl-2 border-l border-slate-200 dark:border-slate-800">
            <div className="hidden sm:flex flex-col text-right">
              <span className="text-xs font-medium text-slate-900 dark:text-white">
                {user.name}
              </span>
              <span className="text-[10px] text-slate-500 dark:text-slate-400">
                {isAutomaticAccess ? 'MVP local' : `${user.role} · ${user.email}`}
              </span>
            </div>
            <button
              onClick={logout}
              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition-colors"
              title="Cerrar sesión"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
