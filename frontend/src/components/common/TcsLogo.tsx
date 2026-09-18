import React from 'react';
import { useTheme } from '../../context/ThemeContext';

interface TcsLogoProps {
  variant?: 'nav' | 'login';
  showSubtitle?: boolean;
  className?: string;
}

export const TcsLogo: React.FC<TcsLogoProps> = ({
  variant = 'nav',
  showSubtitle = true,
  className = '',
}) => {
  const { theme } = useTheme();

  // In login screen (variant === 'login') the background on the hero side is dark slate/blue gradient,
  // so we use the light logo. In navigation, it alternates based on current theme.
  const isDarkBackground = variant === 'login' || theme === 'dark';
  const logoSrc = isDarkBackground ? '/tcs-logo-light.png' : '/tcs-logo-dark.png';

  const sizeClasses =
    variant === 'login'
      ? 'h-12 sm:h-14 w-auto object-contain'
      : 'h-8 sm:h-9 w-auto object-contain';

  return (
    <div className={`flex items-center gap-3 select-none ${className}`}>
      <img
        src={logoSrc}
        alt="Tata Consultancy Services"
        className={sizeClasses}
      />
      {showSubtitle && (
        <>
          <span
            className={`h-5 w-px ${
              isDarkBackground ? 'bg-slate-700/80' : 'bg-slate-300'
            }`}
          />
          <div className="flex flex-col">
            <span
              className={`text-xs sm:text-sm font-semibold tracking-tight ${
                isDarkBackground ? 'text-white' : 'text-slate-900'
              }`}
            >
              Microservice Code Studio
            </span>
            <span
              className={`text-[10px] font-medium tracking-wide uppercase ${
                isDarkBackground ? 'text-slate-400' : 'text-slate-500'
              }`}
            >
              Enterprise Architecture
            </span>
          </div>
        </>
      )}
    </div>
  );
};
