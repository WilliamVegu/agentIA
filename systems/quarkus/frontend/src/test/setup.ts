import '@testing-library/jest-dom/vitest';

// Polyfill window.matchMedia for JSDOM
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// Polyfill ResizeObserver
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Polyfill IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  readonly root: Element | Document | null = null;
  readonly rootMargin: string = '';
  readonly thresholds: ReadonlyArray<number> = [];
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() { return []; }
};

// Polyfill clipboard
Object.defineProperty(navigator, 'clipboard', {
  value: {
    writeText: async () => {},
    readText: async () => '',
  },
  writable: true,
});

// Polyfill scrollIntoView for JSDOM
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}

// Polyfill EventSource for JSDOM
global.EventSource = class MockEventSource {
  url: string;
  onopen: any = null;
  onmessage: any = null;
  onerror: any = null;
  readyState = 0;
  constructor(url: string) {
    this.url = url;
  }
  close() {}
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() { return true; }
} as any;


