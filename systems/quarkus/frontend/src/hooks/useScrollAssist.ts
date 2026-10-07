import { useCallback } from 'react';

export function useScrollAssist() {
  const scrollToElement = useCallback((elementId: string) => {
    const el = document.getElementById(elementId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      el.classList.add('ring-2', 'ring-blue-500', 'ring-offset-2', 'transition-all', 'duration-500');
      setTimeout(() => {
        el.classList.remove('ring-2', 'ring-blue-500', 'ring-offset-2');
      }, 1500);
    }
  }, []);

  return { scrollToElement };
}
