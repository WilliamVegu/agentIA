import React, { useState } from 'react';
import { Copy, Check, Eye, Code as CodeIcon } from 'lucide-react';

interface MermaidViewerProps {
  chart: string;
  title?: string;
  className?: string;
}

export const MermaidViewer: React.FC<MermaidViewerProps> = ({
  chart,
  title = 'Diagrama de Arquitectura / ER',
  className = '',
}) => {
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState<'diagram' | 'source'>('diagram');

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(chart);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  // Parse flowchart or ER nodes for visual structural representation
  const lines = chart.split('\n').filter((l) => l.trim().length > 0);
  const isEr = chart.includes('erDiagram');

  return (
    <div className={`rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/60 overflow-hidden ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 text-xs">
        <span className="font-semibold text-slate-800 dark:text-slate-200">
          {title}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode(viewMode === 'diagram' ? 'source' : 'diagram')}
            className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:text-blue-600 transition-colors"
            title="Alternar vista de código / diagrama"
          >
            {viewMode === 'diagram' ? (
              <>
                <CodeIcon className="w-3.5 h-3.5" />
                <span>Ver Código</span>
              </>
            ) : (
              <>
                <Eye className="w-3.5 h-3.5" />
                <span>Ver Diagrama</span>
              </>
            )}
          </button>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:text-blue-600 transition-colors"
            title="Copiar definición Mermaid"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-500" />
                <span className="text-emerald-600 dark:text-emerald-400">Copiado</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>Copiar</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="p-4 overflow-x-auto min-h-[220px]">
        {viewMode === 'source' ? (
          <pre className="text-xs font-mono text-slate-800 dark:text-slate-200 whitespace-pre leading-relaxed">
            {chart}
          </pre>
        ) : (
          <div className="flex flex-col gap-3 items-center justify-center py-4">
            {isEr ? (
              <div className="w-full max-w-2xl bg-white dark:bg-slate-950 p-4 rounded-lg border border-slate-200 dark:border-slate-800 shadow-inner">
                <div className="text-xs font-semibold text-blue-600 dark:text-blue-400 mb-2 uppercase tracking-wide">
                  Entidades y Relaciones (ER)
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {lines.filter((l) => !l.startsWith('erDiagram') && l.includes('{')).map((line, idx) => {
                    const entName = line.split('{')[0].trim();
                    return (
                      <div key={idx} className="p-3 bg-slate-50 dark:bg-slate-900 rounded border border-slate-200 dark:border-slate-800">
                        <div className="text-xs font-bold text-slate-900 dark:text-white border-b pb-1 mb-2 border-slate-200 dark:border-slate-800">
                          {entName}
                        </div>
                        <div className="text-[11px] text-slate-600 dark:text-slate-400 font-mono space-y-0.5">
                          <div>+ id : Long [PK]</div>
                          <div>+ createdAt : Instant</div>
                          <div>+ status : String</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="w-full max-w-2xl flex flex-col gap-2 items-center">
                {/* 4 Layers Architectural Box Representation */}
                <div className="w-full p-3 rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900/60 text-center">
                  <div className="text-xs font-bold text-blue-700 dark:text-blue-300">Capa 1: Controllers (REST Endpoints)</div>
                  <div className="text-[11px] text-slate-600 dark:text-slate-400 mt-1 font-mono">@RestController /api/v1/*</div>
                </div>
                <div className="text-slate-400 dark:text-slate-600 font-bold">↓</div>
                <div className="w-full p-3 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-900/60 text-center">
                  <div className="text-xs font-bold text-indigo-700 dark:text-indigo-300">Capa 2: Services (Business Logic)</div>
                  <div className="text-[11px] text-slate-600 dark:text-slate-400 mt-1 font-mono">@Service Spring Transactional</div>
                </div>
                <div className="text-slate-400 dark:text-slate-600 font-bold">↓</div>
                <div className="w-full p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/60 text-center">
                  <div className="text-xs font-bold text-emerald-700 dark:text-emerald-300">Capa 3: Repositories (Data Access)</div>
                  <div className="text-[11px] text-slate-600 dark:text-slate-400 mt-1 font-mono">@Repository JpaRepository</div>
                </div>
                <div className="text-slate-400 dark:text-slate-600 font-bold">↓</div>
                <div className="w-full p-3 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-center">
                  <div className="text-xs font-bold text-slate-800 dark:text-slate-200">Capa 4: Models & SQL (PostgreSQL / MySQL / H2)</div>
                  <div className="text-[11px] text-slate-600 dark:text-slate-400 mt-1 font-mono">Jakarta @Entity & Liquibase/DDL</div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
