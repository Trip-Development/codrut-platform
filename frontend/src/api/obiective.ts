import { apiFetch } from "./http";
import { getApiBaseUrl } from "./runtime";
import type { components } from "./generated/schema";

// Plicul 232: obiectivul de aplicare al omului (L1). Tipurile vin din contractul pus de 230.
type ItemContract = components["schemas"]["PracticeObjectiveItem"];
type ListaContract = components["schemas"]["PracticeObjectivesResponse"];
type AlegereContract = components["schemas"]["PracticeObjectiveChoiceResponse"];

export type Obiectiv = {
  id: string;
  nr: number;
  titlu: string;
  situatie: string;
  semnDeReusita: string;
};

export type ObiectiveleProiectului = {
  catalog: string | null;
  catalogName: string | null;
  obiective: Obiectiv[];
};

export type ObiectivulMeu = {
  curent: { obiectiv: Obiectiv; aleasaLa: string } | null;
  primaAlegereLa: string | null;
  istoric: { obiectivId: string; titlu: string; aleasaLa: string; inlocuitaLa: string | null }[];
};

function obiectivDinContract(item: ItemContract): Obiectiv {
  return {
    id: item.id,
    nr: item.nr,
    titlu: item.titlu,
    situatie: item.situatie,
    semnDeReusita: item.semn_de_reusita,
  };
}

function alegereDinContract(data: AlegereContract): ObiectivulMeu {
  return {
    curent: data.curent ? { obiectiv: obiectivDinContract(data.curent.obiectiv), aleasaLa: data.curent.aleasa_la } : null,
    primaAlegereLa: data.prima_alegere_la ?? null,
    istoric: (data.istoric ?? []).map((rand) => ({
      obiectivId: rand.obiectiv_id,
      titlu: rand.titlu,
      aleasaLa: rand.aleasa_la,
      inlocuitaLa: rand.inlocuita_la ?? null,
    })),
  };
}

async function eroare(res: Response, textImplicit: string): Promise<Error> {
  const corp = (await res.json().catch(() => ({}))) as { error?: { message?: string } };
  return new Error(corp?.error?.message || textImplicit);
}

export async function getObiectiveleProiectului(projectId: string): Promise<ObiectiveleProiectului> {
  const res = await apiFetch(`${getApiBaseUrl()}/practice/projects/${projectId}/obiective`);
  if (!res.ok) throw await eroare(res, "Nu am putut încărca obiectivele");
  const data = (await res.json()) as ListaContract;
  return {
    catalog: data.catalog ?? null,
    catalogName: data.catalog_name ?? null,
    obiective: (data.obiective ?? []).map(obiectivDinContract),
  };
}

export async function getObiectivulMeu(projectId: string): Promise<ObiectivulMeu> {
  const res = await apiFetch(`${getApiBaseUrl()}/practice/projects/${projectId}/obiectiv`);
  if (!res.ok) throw await eroare(res, "Nu am putut încărca obiectivul");
  return alegereDinContract((await res.json()) as AlegereContract);
}

export async function alegeObiectivul(projectId: string, objectiveId: string): Promise<ObiectivulMeu> {
  const res = await apiFetch(`${getApiBaseUrl()}/practice/projects/${projectId}/obiectiv`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ objective_id: objectiveId }),
  });
  if (!res.ok) throw await eroare(res, "Nu am putut salva alegerea");
  return alegereDinContract((await res.json()) as AlegereContract);
}
