import React, { useState } from 'react';
import { Copy, Check, Eye, Code as CodeIcon } from 'lucide-react';

interface MermaidViewerProps {
  chart: string;
  title?: string;
  className?: string;
}

interface ParsedErEntity {
  name: string;
  attributes: Array<{
    type: string;
    name: string;
    key?: string;
  }>;
}

function parseErDiagram(chartText: string): ParsedErEntity[] {
  const entities: ParsedErEntity[] = [];
  const blockRegex = /([A-Za-z0-9_]+)\s*\{([^}]*)\}/g;
  let match: RegExpExecArray | null;

  while ((match = blockRegex.exec(chartText)) !== null) {
    const entName = match[1].trim();
    if (entName.toLowerCase() === 'erdiagram') continue;

    const body = match[2];
    const rawLines = body.split('\n');
    const attributes: Array<{ type: string; name: string; key?: string }> = [];

    for (const rawLine of rawLines) {
      const trimmed = rawLine.trim();
      if (!trimmed || trimmed.startsWith('%%')) continue;
      const parts = trimmed.split(/\s+/);
      if (parts.length >= 2) {
        const type = parts[0];
        const name = parts[1];
        const key = parts.slice(2).join(' ') || undefined;
        attributes.push({ type, name, key });
      } else if (parts.length === 1) {
        attributes.push({ type: '', name: parts[0] });
      }
    }

    entities.push({ name: entName, attributes });
  }

  if (entities.length === 0) {
    const lines = chartText.split('\n').map((l) => l.trim());
    for (const line of lines) {
      if (line.includes('{')) {
        const entName = line.split('{')[0].trim();
        if (entName && entName.toLowerCase() !== 'erdiagram') {
          entities.push({ name: entName, attributes: [] });
        }
      }
    }
  }

  return entities;
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

  const isEr = chart.includes('erDiagram');
  const parsedEntities = React.useMemo(() => (isEr ? parseErDiagram(chart) : []), [isEr, chart]);

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
                  {parsedEntities.map((ent, idx) => (
                    <div key={idx} className="p-3 bg-slate-50 dark:bg-slate-900 rounded border border-slate-200 dark:border-slate-800">
                      <div className="text-xs font-bold text-slate-900 dark:text-white border-b pb-1 mb-2 border-slate-200 dark:border-slate-800">
                        {ent.name}
                      </div>
                      <div className="text-[11px] text-slate-600 dark:text-slate-400 font-mono space-y-0.5">
                        {ent.attributes.length > 0 ? (
                          ent.attributes.map((attr, aIdx) => (
                            <div key={aIdx}>
                              + {attr.name} {attr.type ? `: ${attr.type}` : ''} {attr.key ? `[${attr.key}]` : ''}
                            </div>
                          ))
                        ) : (
                          <div className="text-slate-400 italic">Sin atributos definidos</div>
                        )}
                      </div>
                    </div>
                  ))}
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
