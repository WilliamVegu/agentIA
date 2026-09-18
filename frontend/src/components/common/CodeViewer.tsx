import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';

interface CodeViewerProps {
  code: string;
  language?: string;
  filename?: string;
  maxHeight?: string;
  className?: string;
}

export const CodeViewer: React.FC<CodeViewerProps> = ({
  code = '',
  language = 'java',
  filename,
  maxHeight = 'max-h-96',
  className = '',
}) => {
  const [copied, setCopied] = useState(false);

  const safeCode = typeof code === 'string'
    ? code
    : (code !== null && code !== undefined ? JSON.stringify(code, null, 2) : '');

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(safeCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  const lines = safeCode.split('\n');

  return (
    <div className={`rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-900 overflow-hidden shadow-sm ${className}`}>
      {/* File Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-slate-950/80 border-b border-slate-800 text-xs">
        <div className="flex items-center gap-2">
          {filename && (
            <span className="font-mono text-slate-300 font-medium">
              {filename}
            </span>
          )}
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono text-[10px] uppercase">
            {language}
          </span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
          title="Copiar código al portapapeles"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400 text-xs font-medium">Copiado</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span className="text-xs">Copiar</span>
            </>
          )}
        </button>
      </div>

      {/* Code with Line Numbers */}
      <div className={`overflow-auto p-3 text-xs font-mono text-slate-200 leading-relaxed ${maxHeight}`}>
        <table className="w-full border-collapse">
          <tbody>
            {lines.map((line, idx) => (
              <tr key={idx} className="hover:bg-slate-800/40">
                <td className="select-none text-slate-500 text-right pr-4 pl-1 w-10 text-[11px] align-top">
                  {idx + 1}
                </td>
                <td className="whitespace-pre font-mono text-slate-100 pr-2">
                  {line || ' '}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
