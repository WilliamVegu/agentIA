import React from 'react';
import { useScrollAssist } from '../../hooks/useScrollAssist';

interface AssistedScrollBtnProps {
  targetId: string;
  label: string;
  className?: string;
}

export const AssistedScrollBtn: React.FC<AssistedScrollBtnProps> = ({
  targetId,
  label,
  className = '',
}) => {
  const { scrollToElement } = useScrollAssist();

  return (
    <button
      type="button"
      onClick={() => scrollToElement(targetId)}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors border border-slate-200 dark:border-slate-700 select-none ${className}`}
      title={`Desplazarse a ${label}`}
    >
      <span>{label}</span>
      <span className="font-bold text-blue-600 dark:text-blue-400">↓</span>
    </button>
  );
};
