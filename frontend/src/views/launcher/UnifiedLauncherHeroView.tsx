import React from 'react';
import { useEcosystem } from '../../context/EcosystemContext';
import {
  Zap,
  Layers,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  Database,
  Terminal,
  Workflow,
  Sparkles,
  GitBranch,
  Boxes,
  Cpu,
  Clock,
  ExternalLink,
} from 'lucide-react';
import { TcsLogo } from '../../components/common/TcsLogo';

export const UnifiedLauncherHeroView: React.FC = () => {
  const { goToSpring, goToQuarkus } = useEcosystem();

  return (
    <div className="min-h-full py-8 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto flex flex-col justify-center">
      {/* Hero Header */}
      <div className="text-center max-w-3xl mx-auto space-y-4">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300 text-xs font-semibold shadow-xs">
          <Sparkles className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
          <span>Plataforma Unificada de Ingeniería Agéntica Multi-Ecosistema</span>
        </div>

        <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-slate-900 dark:text-white">
          Elige tu Ecosistema de Desarrollo
        </h1>

        <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300 leading-relaxed">
          Selecciona el motor sobre el cual deseas especificar, modelar y generar microservicios autónomos en Java 21.
          Ambos sistemas conviven de forma independiente y conservan sus respectivos flujos especializados.
        </p>
      </div>

      {/* Main Ecosystem Selection Cards */}
      <div className="mt-10 grid grid-cols-1 lg:grid-cols-2 gap-8 items-stretch">
        {/* Card 1: Spring Boot Microservice Studio */}
        <div className="relative group rounded-3xl p-6 sm:p-8 bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 hover:border-emerald-500/70 dark:hover:border-emerald-500/70 shadow-sm hover:shadow-xl transition-all duration-300 flex flex-col justify-between overflow-hidden">
          {/* Subtle Top Gradient Accent */}
          <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-emerald-500 via-teal-500 to-green-600" />

          <div>
            {/* Header info */}
            <div className="flex items-center justify-between gap-4 mb-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-2xl bg-emerald-100 dark:bg-emerald-950/60 border border-emerald-300 dark:border-emerald-800 flex items-center justify-center shadow-xs">
                  <Layers className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <span>Spring Boot Studio</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/60 text-emerald-800 dark:text-emerald-300 font-semibold">
                      v3.3 · DDD
                    </span>
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                    Estudio de Microservicios con Arquitectura Hexagonal
                  </p>
                </div>
              </div>
              <span className="hidden sm:inline-flex px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900">
                End-to-End
              </span>
            </div>

            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 mb-6 leading-relaxed">
              Flujo guiado para microservicios empresariales de alta disponibilidad. Cubre desde la ingesta de especificaciones funcionales hasta la generación de código, esquemas SQL sincronizados y verificación hermética.
            </p>

            {/* Feature Highlights */}
            <div className="space-y-3 mb-6">
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Capacidades Integradas
              </div>
              <ul className="space-y-2.5 text-xs text-slate-700 dark:text-slate-200">
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span><strong>Ingesta & Requerimientos:</strong> Transformación estructurada de requerimientos a historias BDD con criterios de aceptación.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span><strong>Arquitectura Hexagonal:</strong> Puertos y adaptadores, separación de capas de dominio, infraestructura y aplicación.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span><strong>Modelado de Dominio & SQL:</strong> Diagrama ER visual interactivo, entidades JPA y scripts sincronizados (PostgreSQL & H2).</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span><strong>Auditoría & Despliegue:</strong> Pruebas unitarias, análisis estático Sonar, manifiestos Docker y Kubernetes.</span>
                </li>
              </ul>
            </div>

            {/* Tech Badges */}
            <div className="flex flex-wrap gap-1.5 mb-8">
              {['Spring Boot 3.3', 'Java 21', 'Spring Data JPA', 'PostgreSQL 16', 'Docker', 'Maven', 'H2 In-Memory'].map((tech) => (
                <span
                  key={tech}
                  className="px-2.5 py-1 rounded-lg text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
                >
                  {tech}
                </span>
              ))}
            </div>
          </div>

          {/* Action Button */}
          <button
            onClick={goToSpring}
            className="w-full py-3 px-5 rounded-2xl font-semibold text-sm text-white bg-gradient-to-r from-emerald-600 to-teal-700 hover:from-emerald-500 hover:to-teal-600 active:from-emerald-700 active:to-teal-800 shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 group-hover:gap-3"
          >
            <span>Entrar al Estudio Spring Boot</span>
            <ArrowRight className="w-4 h-4 transition-transform" />
          </button>
        </div>

        {/* Card 2: Quarkus Agent Factory */}
        <div className="relative group rounded-3xl p-6 sm:p-8 bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 hover:border-red-500/70 dark:hover:border-red-500/70 shadow-sm hover:shadow-xl transition-all duration-300 flex flex-col justify-between overflow-hidden">
          {/* Subtle Top Gradient Accent */}
          <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-red-500 via-rose-500 to-indigo-600" />

          <div>
            {/* Header info */}
            <div className="flex items-center justify-between gap-4 mb-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-2xl bg-red-100 dark:bg-red-950/60 border border-red-300 dark:border-red-800 flex items-center justify-center shadow-xs">
                  <Zap className="w-6 h-6 text-red-600 dark:text-red-400" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <span>Fábrica Quarkus 3.x</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/60 text-red-800 dark:text-red-300 font-semibold">
                      v3.15 LTS · GraalVM
                    </span>
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                    Flujo Especializado en 8 Pasos con 2 Controles Humanos
                  </p>
                </div>
              </div>
              <span className="hidden sm:inline-flex px-2.5 py-1 rounded-full text-[11px] font-semibold bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-900">
                8 Agentes IA
              </span>
            </div>

            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 mb-6 leading-relaxed">
              Fábrica ágil enfocada en Quarkus Supersonic Subatomic Java. Diseñada con 8 agentes especializados, doble compuerta de aprobación humana, auto-corrección (Self-Healing) y trazabilidad granular de tokens.
            </p>

            {/* Feature Highlights */}
            <div className="space-y-3 mb-6">
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Capacidades Integradas
              </div>
              <ul className="space-y-2.5 text-xs text-slate-700 dark:text-slate-200">
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <span><strong>Agente Analista & Control 1:</strong> Síntesis OpenAPI 3.1, BDD Gherkin y aprobación humana antes de codificar.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <span><strong>Agente Arquitecto:</strong> Selección dinámica de patrones (Capas/Hexagonal/Eventos) y extensiones Quarkus 3.15.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <span><strong>Construcción & Self-Healing:</strong> DTOs Records inmutables, pruebas automatizadas, auto-reparación y Code Review.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <span><strong>DevOps & Control 2:</strong> Aprobación final, Jenkinsfile, Dockerfile JVM/Nativo y exportación en ZIP.</span>
                </li>
              </ul>
            </div>

            {/* Tech Badges */}
            <div className="flex flex-wrap gap-1.5 mb-8">
              {['Quarkus 3.15 LTS', 'Java 21', 'GraalVM Native', 'Hibernate Reactive', 'Panache', 'JAX-RS', 'SmallRye Health'].map((tech) => (
                <span
                  key={tech}
                  className="px-2.5 py-1 rounded-lg text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
                >
                  {tech}
                </span>
              ))}
            </div>
          </div>

          {/* Action Button */}
          <button
            onClick={goToQuarkus}
            className="w-full py-3 px-5 rounded-2xl font-semibold text-sm text-white bg-gradient-to-r from-red-600 to-rose-700 hover:from-red-500 hover:to-rose-600 active:from-red-700 active:to-rose-800 shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 group-hover:gap-3"
          >
            <span>Entrar a la Fábrica Quarkus</span>
            <ArrowRight className="w-4 h-4 transition-transform" />
          </button>
        </div>
      </div>

      {/* Comparison and Switching Guidance Banner */}
      <div className="mt-8 p-4 rounded-2xl bg-slate-100/90 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-600 dark:text-slate-400">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 shadow-xs">
            <GitBranch className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div>
            <span className="font-semibold text-slate-800 dark:text-slate-200">
              Libertad de navegación entre ecosistemas:
            </span>{' '}
            Puedes cambiar de sistema o regresar a esta pantalla en cualquier momento mediante el botón de alternancia en la barra superior.
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-mono text-[11px] text-slate-500">Ambos motores sincronizados</span>
        </div>
      </div>
    </div>
  );
};
