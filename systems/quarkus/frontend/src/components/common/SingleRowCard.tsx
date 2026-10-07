import React from 'react';

interface SingleRowCardProps {
  title: string;
  subtitle?: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  id?: string;
}

export const SingleRowCard: React.FC<SingleRowCardProps> = ({
  title,
  subtitle,
  badge,
  children,
  actions,
  className = '',
  id,
}) => {
  return (
    <div
      id={id}
      className={`bg-white dark:bg-slate-900/90 border border-slate-200/90 dark:border-slate-800 rounded-xl p-5 shadow-sm transition-all flex flex-col justify-between ${className}`}
    >
      <div>
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <h3 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight">
              {title}
            </h3>
            {subtitle && (
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                {subtitle}
              </p>
            )}
          </div>
          {badge && <div className="shrink-0">{badge}</div>}
        </div>

        <div className="text-sm text-slate-700 dark:text-slate-300">
          {children}
        </div>
      </div>

      {actions && (
        <div className="mt-5 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex flex-row items-center gap-2">
          {actions}
        </div>
      )}
    </div>
  );
};
