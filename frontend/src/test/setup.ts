import { vi } from "vitest";

const nextRouterMock = {
  push: vi.fn(),
  replace: vi.fn(),
  prefetch: vi.fn(),
  back: vi.fn(),
  refresh: vi.fn(),
};

const localStorageMock = (function () {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value.toString();
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
  };
})();

Object.defineProperty(window, "localStorage", {
  value: localStorageMock,
  writable: true,
});

class ResizeObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}

Object.defineProperty(globalThis, "ResizeObserver", {
  value: ResizeObserverMock,
  writable: true,
});

Object.defineProperties(HTMLElement.prototype, {
  hasPointerCapture: {
    configurable: true,
    value: vi.fn(() => false),
  },
  setPointerCapture: {
    configurable: true,
    value: vi.fn(),
  },
  releasePointerCapture: {
    configurable: true,
    value: vi.fn(),
  },
});

vi.mock("next/navigation", () => ({
  useRouter: () => nextRouterMock,
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "",
}));

vi.mock("next/font/google", () => ({
  Geist: () => ({ className: "__geist", variable: "__geist-variable" }),
}));
