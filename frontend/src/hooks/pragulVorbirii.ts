/**
 * Pragul vorbirii — plicul 174, partea (a): clipul în care nu s-a vorbit nu mai pleacă la transcriere.
 *
 * Pe probă, liniștea de cameră se „transcria” „Bună ziua!”, iar tăcerea curată „00:00” (plicul 170).
 * Ecranul ascultă deja microfonul (pentru oprirea pe tăcere); acum măsoară și cât timp din înregistrare
 * a fost peste pragul vorbirii. Fără vorbire, clipul nu se mai trimite și omul vede mesajul existent
 * „Nu s-a auzit nimic…”.
 *
 * Pragurile s-au ales din măsurătoare, după regula scrisă în plic înainte de măsură (§3.0), pe 7
 * fișiere de test: liniștea de cameră are vârful la −54,1 dBFS, deci pragul = ⌈−54,1⌉ + 6 = −48;
 * un „Da.” scurt stă 320 ms peste prag, deci minimul = ⌊0,5 × 320⌋ = 160 ms. Vorbirea încetă (−25 dB)
 * stă 2920 ms peste prag. Pragurile sunt din fișiere sintetice, fără AGC și fără reducerea zgomotului
 * pe care le face browserul: marginea reală se citește din proba cu microfonul adevărat.
 *
 * Plasa de pe server din plic, partea (b), n-a intrat: PyAV ar fi crescut imaginea cu ~127 MB (plafon
 * 80 MB). Dacă intră vreodată, pragurile de acolo se țin egale cu acestea.
 *
 * Ecranul nu aruncă niciodată ce n-a ascultat: dacă măsurarea n-a mers (fila ascunsă oprește cadrele,
 * browser fără `getFloatTimeDomainData`), clipul se trimite.
 */
export const PRAG_VORBIRE_DBFS = -48;
export const MIN_MS_VORBIRE = 160;
/** Cât din înregistrare trebuie să fi fost măsurat ca ecranul să aibă voie să hotărască „nimic”. */
export const ACOPERIRE_MINIMA = 0.5;

/** Nivelul unei ferestre de eșantioane (−1…1), în dBFS (RMS). Tăcerea curată: −Infinity. */
export function nivelDbfs(fereastra: Float32Array): number {
  if (fereastra.length === 0) return -Infinity;
  let suma = 0;
  for (let i = 0; i < fereastra.length; i++) suma += fereastra[i] * fereastra[i];
  const rms = Math.sqrt(suma / fereastra.length);
  return rms > 0 ? 20 * Math.log10(rms) : -Infinity;
}

/**
 * „nimic” numai dacă ecranul chiar a ascultat (cel puțin jumătate din înregistrare) și vorbirea a fost
 * sub minim; altfel „trimite”.
 */
export function decizieClip({
  msInregistrare,
  msMasurate,
  msPestePrag,
}: {
  msInregistrare: number;
  msMasurate: number;
  msPestePrag: number;
}): "trimite" | "nimic" {
  const aAscultat = msMasurate > 0 && msMasurate >= ACOPERIRE_MINIMA * msInregistrare;
  return aAscultat && msPestePrag < MIN_MS_VORBIRE ? "nimic" : "trimite";
}
