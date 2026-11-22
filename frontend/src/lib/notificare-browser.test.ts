import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Plicul 252, §6.3 și corecția 5: ordinea în browser și recunoașterea iPhone-ului.
const ordine: string[] = [];
const abonare = { endpoint: "https://web.push.apple.com/abc", unsubscribe: vi.fn(async () => true) };
const pushManager = {
  subscribe: vi.fn(async (...args: unknown[]) => {
    void args;
    ordine.push("subscribe");
    return abonare;
  }),
  getSubscription: vi.fn(async () => abonare),
};
const sw = {
  register: vi.fn(async (...args: unknown[]) => {
    void args;
    ordine.push("register");
    return { pushManager };
  }),
  getRegistration: vi.fn(async () => ({ pushManager })),
  ready: Promise.resolve({ pushManager }),
};

function seteazaUa(ua: string, { standalone = false, touch = 0 } = {}) {
  Object.defineProperty(navigator, "userAgent", { value: ua, configurable: true });
  Object.defineProperty(navigator, "maxTouchPoints", { value: touch, configurable: true });
  Object.defineProperty(navigator, "standalone", { value: standalone, configurable: true });
  window.matchMedia = vi.fn(() => ({ matches: false }) as unknown as MediaQueryList);
}

beforeEach(() => {
  ordine.length = 0;
  sw.register.mockClear();
  pushManager.subscribe.mockClear();
  Object.defineProperty(navigator, "serviceWorker", { value: sw, configurable: true });
  vi.stubGlobal("Notification", {
    permission: "default",
    requestPermission: vi.fn(async () => {
      ordine.push("requestPermission");
      return "granted";
    }),
  });
});
afterEach(() => {
  vi.unstubAllGlobals();
});

const IPHONE_SAFARI = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1";
const IPAD_CA_MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15";
const ANDROID_CHROME = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36";

describe("lib/notificare-browser — plicul 252", () => {
  it("aboneaza: permisiunea ÎNTÂI, apoi register(/sw.js), apoi subscribe cu userVisibleOnly", async () => {
    const { aboneaza } = await import("./notificare-browser");
    const endpoint = await aboneaza("BPublicaDeTestAAAA");
    expect(endpoint).toBe(abonare.endpoint);
    expect(ordine).toEqual(["requestPermission", "register", "subscribe"]);
    expect(sw.register).toHaveBeenCalledWith("/sw.js", { scope: "/" });
    expect((pushManager.subscribe.mock.calls[0][0] as { userVisibleOnly: boolean }).userVisibleOnly).toBe(true);
  });

  it("aboneaza: permisiunea refuzată → nimic înregistrat", async () => {
    vi.stubGlobal("Notification", { permission: "denied", requestPermission: vi.fn(async () => "denied") });
    const { aboneaza, PermisiuneRefuzata } = await import("./notificare-browser");
    await expect(aboneaza("K")).rejects.toBeInstanceOf(PermisiuneRefuzata);
    expect(sw.register).not.toHaveBeenCalled();
  });

  it("abonareaDeAcum nu înregistrează nimic la deschidere", async () => {
    const { abonareaDeAcum } = await import("./notificare-browser");
    expect(await abonareaDeAcum()).toBe(abonare.endpoint);
    expect(sw.register).toHaveBeenCalledTimes(0);
  });

  it("iPhone din Safari, iPhone de pe ecranul principal, iPad ca Mac, Android", async () => {
    const { eIphoneFaraEcranPrincipal } = await import("./notificare-browser");
    seteazaUa(IPHONE_SAFARI);
    expect(eIphoneFaraEcranPrincipal()).toBe(true);
    seteazaUa(IPHONE_SAFARI, { standalone: true });
    expect(eIphoneFaraEcranPrincipal()).toBe(false);
    seteazaUa(IPAD_CA_MAC, { touch: 5 });
    expect(eIphoneFaraEcranPrincipal()).toBe(true);
    seteazaUa(ANDROID_CHROME, { touch: 5 });
    expect(eIphoneFaraEcranPrincipal()).toBe(false);
  });
});
