// Plicul 252 (L3-P2): service worker-ul minimal al lui Cody — NUMAI notificarea zilnică.
// Fără memorie de pagini, fără cereri: paginile au cod de siguranță pe cerere (plicul 231).
// Mesajul de la server vine gol; textul e scris aici, la fel ca în texte-notificare.ts.
const TITLU = "O replică pe zi";
const TEXT = "Situația de azi te așteaptă. Durează un minut.";
const ADRESA = "/participant/replica-zilei";

self.addEventListener("push", (event) => {
  event.waitUntil(
    self.registration.showNotification(TITLU, {
      body: TEXT,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      tag: "replica-zilei",
      lang: "ro",
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    (async () => {
      const ferestre = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const fereastra of ferestre) {
        try {
          await fereastra.focus();
          await fereastra.navigate(ADRESA);
          return;
        } catch {
          break;
        }
      }
      await self.clients.openWindow(ADRESA);
    })(),
  );
});
