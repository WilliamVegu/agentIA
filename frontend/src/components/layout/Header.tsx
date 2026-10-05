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
  const { activeEcosystem, goToLauncher } = useEcosystem();

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
      {/* Left: Branding & Ecosystem indicator */}
      <div className="flex items-center gap-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 hidden xs:inline-block">
          TCS Microservices
        </span>
        <span className="text-slate-300 dark:text-slate-700 hidden xs:inline-block">/</span>

        {activeEcosystem === 'launcher' ? (
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
            Hub de Ecosistemas
          </span>
        ) : activeEcosystem === 'spring' ? (
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
              <Layers className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
              <span>Spring Boot Studio</span>
            </span>
            <button
              onClick={goToLauncher}
              className="text-[11px] font-medium text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white px-2 py-0.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors flex items-center gap-1"
              title="Volver al selector de ecosistemas"
            >
              <ArrowLeftRight className="w-3 h-3 text-slate-400" />
              <span className="hidden sm:inline">Cambiar</span>
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-50 dark:bg-red-950/60 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800">
              <Zap className="w-3.5 h-3.5 text-red-600 dark:text-red-400" />
              <span>Quarkus 3.x Factory</span>
            </span>
            <button
              onClick={goToLauncher}
              className="text-[11px] font-medium text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white px-2 py-0.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors flex items-center gap-1"
              title="Volver al selector de ecosistemas"
            >
              <ArrowLeftRight className="w-3 h-3 text-slate-400" />
              <span className="hidden sm:inline">Cambiar</span>
            </button>
          </div>
        )}
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
