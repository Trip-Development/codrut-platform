// Plicul 252 (L3-P2): SINGURUL loc care atinge `navigator.serviceWorker`, `PushManager` și
// `Notification`, ca testele să-l poată preface. Nimic de aici nu cere voie la deschiderea paginii.

export type Permisiune = "granted" | "denied" | "default";

export function suportat(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

/** iPhone/iPad (și iPad-ul care se prezintă ca Mac) cu Cody deschis din browser, nu de pe ecranul principal. */
export function eIphoneFaraEcranPrincipal(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  const eIos = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && (navigator.maxTouchPoints ?? 0) > 1);
  if (!eIos) return false;
  const deSine =
    (typeof window !== "undefined" && window.matchMedia?.("(display-mode: standalone)").matches) ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true;
  return !deSine;
}

export function permisiunea(): Permisiune {
  if (typeof Notification === "undefined") return "default";
  return Notification.permission as Permisiune;
}

/** Adresa abonării de acum, fără să înregistreze nimic. */
export async function abonareaDeAcum(): Promise<string | null> {
  const inregistrare = await navigator.serviceWorker.getRegistration();
  if (!inregistrare) return null;
  const abonare = await inregistrare.pushManager.getSubscription();
  return abonare?.endpoint ?? null;
}

function cheieDinBase64Url(text: string): Uint8Array {
  const b64 = text.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (text.length % 4)) % 4);
  const sir = atob(b64);
  return Uint8Array.from(sir, (c) => c.charCodeAt(0));
}

export class PermisiuneRefuzata extends Error {
  constructor() {
    super("permisiune refuzata");
    this.name = "PermisiuneRefuzata";
  }
}

/**
 * Pornește abonarea. Ordinea (corecția 5): (1) cererea de permisiune, chemată prima, direct din
 * apăsare (pe iPhone altfel poate fi refuzată); (2) înregistrarea lui /sw.js; (3) așteptarea
 * service worker-ului activ; (4) abonarea, numai cu notificări vizibile.
 */
export async function aboneaza(cheiePublica: string): Promise<string> {
  const raspuns = await Notification.requestPermission();
  if (raspuns !== "granted") throw new PermisiuneRefuzata();
  await navigator.serviceWorker.register("/sw.js", { scope: "/" });
  const gata = await navigator.serviceWorker.ready;
  const abonare = await gata.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: cheieDinBase64Url(cheiePublica) as BufferSource,
  });
  return abonare.endpoint;
}

/** Oprește abonarea de pe telefon (asta singură oprește notificările). */
export async function dezaboneaza(): Promise<void> {
  const inregistrare = await navigator.serviceWorker.getRegistration();
  const abonare = await inregistrare?.pushManager.getSubscription();
  if (abonare) await abonare.unsubscribe();
}
