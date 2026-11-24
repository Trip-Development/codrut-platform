import { apiFetch } from "./http";
import { getApiBaseUrl } from "./runtime";
import { PracticeError } from "./practice";
import type { components } from "./generated/schema";

// Plicul 251: replica zilei a omului (L2-P2). Tipurile vin din contractul pus de 236.
type StareContract = components["schemas"]["PracticeDailyReplyResponse"];

export type SituatiaZilei = { id: string; text: string; obiectivNr: number; obiectivTitlu: string };

export type ReplicaDeAzi = {
  situatieId: string;
  replica: string;
  raspuns: string;
  nota: number | null;
  trimisaLa: string;
  // Plicul 267: răspunsul profesorului vine din fundal; cât e în lucru, `raspuns` e gol.
  // Câmpul apare numai când e adevărat, ca forma de până acum să rămână neschimbată.
  inLucru?: boolean;
};

export type StareaZilei = {
  situatie: SituatiaZilei | null;
  motiv: "fara_obiective" | "fara_situatii" | null;
  dinObiectivulMeu: boolean;
  azi: ReplicaDeAzi | null;
  serie: number;
};

function stareDinContract(data: StareContract): StareaZilei {
  return {
    situatie: data.situatie
      ? {
          id: data.situatie.id,
          text: data.situatie.text,
          obiectivNr: data.situatie.obiectiv_nr,
          obiectivTitlu: data.situatie.obiectiv_titlu,
        }
      : null,
    motiv: data.motiv ?? null,
    dinObiectivulMeu: data.din_obiectivul_meu,
    azi: data.azi
      ? {
          situatieId: data.azi.situatie_id,
          replica: data.azi.replica,
          raspuns: data.azi.raspuns,
          nota: data.azi.nota ?? null,
          trimisaLa: data.azi.trimisa_la,
          ...(data.azi.in_lucru === true ? { inLucru: true } : {}),
        }
      : null,
    serie: data.serie,
  };
}

// Plicul de eroare al aplicației e `{error:{code,message,details}}` (ca în api/practice.ts).
async function eroare(res: Response): Promise<PracticeError> {
  const corp = (await res.json().catch(() => ({}))) as { error?: { code?: string; message?: string; details?: unknown } };
  const plic = corp?.error;
  const detalii = plic?.details && typeof plic.details === "object" && !Array.isArray(plic.details) ? plic.details : {};
  return new PracticeError(plic?.message || "", plic?.code || "unknown", detalii as Record<string, unknown>);
}

const adresa = (projectId: string) => `${getApiBaseUrl()}/practice/projects/${projectId}/replica-zilei`;

export async function getReplicaZilei(projectId: string): Promise<StareaZilei> {
  const res = await apiFetch(adresa(projectId));
  if (!res.ok) throw await eroare(res);
  return stareDinContract((await res.json()) as StareContract);
}

export async function trimiteReplicaZilei(projectId: string, situationId: string, replica: string): Promise<StareaZilei> {
  const res = await apiFetch(adresa(projectId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ situation_id: situationId, replica }),
  });
  if (!res.ok) throw await eroare(res);
  return stareDinContract((await res.json()) as StareContract);
}
