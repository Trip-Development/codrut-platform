import { apiFetch } from "./http";
import { getApiBaseUrl } from "./runtime";
import { PracticeError } from "./practice";
import type { components } from "./generated/schema";

// Plicul 252 (L3-P2): notificarea zilnică a replicii zilei. Tipurile vin din contract.
type InfoContract = components["schemas"]["PracticeDailyReminderInfoResponse"];
type StareContract = components["schemas"]["PracticeDailyReminderStateResponse"];

export type InfoNotificare = { disponibila: boolean; cheiePublica: string | null; ore: number[] };
export type StareNotificare = { pornita: boolean; ora: number | null };

async function eroare(res: Response): Promise<PracticeError> {
  const corp = (await res.json().catch(() => ({}))) as { error?: { code?: string; message?: string; details?: unknown } };
  const plic = corp?.error;
  const detalii = plic?.details && typeof plic.details === "object" && !Array.isArray(plic.details) ? plic.details : {};
  return new PracticeError(plic?.message || "", plic?.code || "unknown", detalii as Record<string, unknown>);
}

const adresa = (projectId: string, rest = "") =>
  `${getApiBaseUrl()}/practice/projects/${projectId}/notificare-zilnica${rest}`;

const json = (corp: unknown) => ({
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(corp),
});

export async function getNotificare(projectId: string): Promise<InfoNotificare> {
  const res = await apiFetch(adresa(projectId));
  if (!res.ok) throw await eroare(res);
  const d = (await res.json()) as InfoContract;
  return { disponibila: d.disponibila, cheiePublica: d.cheie_publica ?? null, ore: d.ore };
}

export async function stareaNotificarii(projectId: string, endpoint: string): Promise<StareNotificare> {
  const res = await apiFetch(adresa(projectId, "/stare"), { method: "POST", ...json({ endpoint }) });
  if (!res.ok) throw await eroare(res);
  const d = (await res.json()) as StareContract;
  return { pornita: d.pornita, ora: d.ora ?? null };
}

export async function pornesteNotificarea(projectId: string, endpoint: string, ora: number): Promise<StareNotificare> {
  const res = await apiFetch(adresa(projectId), { method: "PUT", ...json({ endpoint, ora }) });
  if (!res.ok) throw await eroare(res);
  const d = (await res.json()) as StareContract;
  return { pornita: d.pornita, ora: d.ora ?? null };
}

export async function opresteNotificarea(projectId: string, endpoint: string): Promise<void> {
  const res = await apiFetch(adresa(projectId, "/opreste"), { method: "POST", ...json({ endpoint }) });
  if (!res.ok) throw await eroare(res);
}
