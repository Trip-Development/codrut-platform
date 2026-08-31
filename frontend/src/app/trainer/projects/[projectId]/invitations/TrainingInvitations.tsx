"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { CheckCircleIcon, CopyIcon, XCircleIcon } from "lucide-react";

import { sendTrainingInvitations } from "@/api/practice";
import type { TrainingInvitation, TrainingInvitationSent } from "@/api/practice";
import { Card } from "@/components/ui/card";

/**
 * Invitațiile în formă de training.
 *
 * Ce s-a crezut la plicul 30 și s-a dovedit greșit la 31: că ruta obișnuită de
 * invitații merge și fără ciclu de evaluare. Nu merge. Acea rută cere ca omul să
 * aibă deja o asignare de chestionar activă; altfel îl sare tăcut și nu scrie
 * nimic — nici invitație, nici email. Un proiect de training n-are chestionare,
 * deci n-avea cum să trimită nimic, niciodată.
 *
 * Acum se cheamă calea trainingului, care întoarce linkul fiecărui om chiar și
 * când emailul nu pleacă. Emailul poate cădea din motive care nu țin de noi;
 * drumul participantului trebuie să se poată parcurge oricum — trainerul copiază
 * linkul și îl dă cum vrea.
 */
export function TrainingInvitations({
  projectId,
  rows,
}: {
  projectId: string;
  rows: TrainingInvitation[];
}) {
  const router = useRouter();
  const [reimprospatez, startReimprospatare] = useTransition();
  const [bifati, setBifati] = useState<Set<string>>(new Set());
  const [trimit, setTrimit] = useState(false);
  const [rezultate, setRezultate] = useState<TrainingInvitationSent[] | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);
  const [copiat, setCopiat] = useState<string | null>(null);

  // Linkul proaspăt trimis are prioritate față de cel adus de server.
  const linkDupaProfil = new Map<string, string>();
  for (const r of rows) if (r.inviteUrl) linkDupaProfil.set(r.participantProfileId, r.inviteUrl);
  for (const r of rezultate ?? []) {
    if (r.inviteUrl) linkDupaProfil.set(r.participantProfileId, r.inviteUrl);
  }

  function toggle(id: string) {
    setBifati((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleToti() {
    setBifati((prev) =>
      prev.size === rows.length ? new Set() : new Set(rows.map((r) => r.participantProfileId)),
    );
  }

  async function copiaza(id: string, link: string) {
    try {
      await navigator.clipboard.writeText(link);
      setCopiat(id);
      window.setTimeout(() => setCopiat((c) => (c === id ? null : c)), 2000);
    } catch {
      setEroare("Nu am putut copia linkul. Selectează-l și copiază-l cu mâna.");
    }
  }

  async function trimite() {
    if (bifati.size === 0) return;
    setTrimit(true);
    setEroare(null);
    setRezultate(null);
    try {
      const raspuns = await sendTrainingInvitations(projectId, Array.from(bifati));
      setRezultate(raspuns);
      setBifati(new Set());
      // Tabelul se aduce singur la zi. Andrei nu reîncarcă pagina cu mâna.
      startReimprospatare(() => router.refresh());
    } catch (e) {
      setEroare(e instanceof Error ? e.message : "Nu am putut trimite invitațiile.");
    } finally {
      setTrimit(false);
    }
  }

  const cuLink = (rezultate ?? []).filter((r) => r.inviteUrl).length;
  const cuEmail = (rezultate ?? []).filter((r) => r.emailSent).length;
  const esuate = (rezultate ?? []).filter((r) => !r.inviteUrl);

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
        <div>
          <h3 className="text-base font-semibold text-foreground">Invitații</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Bifează oamenii și trimite. Fiecare primește un link personal — pe email, dacă
            emailul e pornit, și oricum în tabelul de mai jos, de unde îl poți copia.
          </p>
        </div>
        <button
          type="button"
          onClick={trimite}
          disabled={trimit || bifati.size === 0}
          className="rounded-md bg-burgundy px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {trimit ? "Trimit…" : `Trimite invitații (${bifati.size})`}
        </button>
      </div>

      {rezultate ? (
        <div className="border-b bg-muted/20 px-5 py-3 text-sm">
          <p className="font-medium text-foreground">
            {cuLink === 0
              ? "Nicio invitație nu s-a putut face."
              : `Am făcut ${cuLink} ${cuLink === 1 ? "invitație" : "invitații"}` +
                (cuEmail === cuLink
                  ? cuEmail === 1
                    ? " și am trimis emailul."
                    : " și am trimis emailurile."
                  : cuEmail === 0
                    ? ". Emailul nu a plecat — copiază linkurile din tabel."
                    : `, iar ${cuEmail} au plecat și pe email. Pentru restul, copiază linkul din tabel.`)}
          </p>
          {esuate.length > 0 ? (
            <ul className="mt-2 space-y-1 text-xs text-danger">
              {esuate.map((r) => (
                <li key={r.participantProfileId}>
                  {r.fullName ?? r.email ?? "Participant"}: {r.error ?? "nu s-a putut."}
                </li>
              ))}
            </ul>
          ) : null}
          {rezultate.some((r) => r.inviteUrl && !r.emailSent && r.error) ? (
            <p className="mt-2 text-xs text-muted-foreground">
              {rezultate.find((r) => r.inviteUrl && !r.emailSent && r.error)?.error}
            </p>
          ) : null}
          {reimprospatez ? (
            <p className="mt-2 text-xs text-muted-foreground">Aduc tabelul la zi…</p>
          ) : null}
        </div>
      ) : null}
      {eroare ? <p className="border-b px-5 py-3 text-sm text-danger">{eroare}</p> : null}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] text-left text-sm">
          <thead className="bg-muted/40 text-xs uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="p-4">
                <input
                  type="checkbox"
                  checked={rows.length > 0 && bifati.size === rows.length}
                  onChange={toggleToti}
                  aria-label="Bifează toți"
                />
              </th>
              <th className="p-4 font-medium">Participant</th>
              <th className="p-4 font-medium">Link de intrare</th>
              <th className="p-4 text-center font-medium">Invitat</th>
              <th className="p-4 text-center font-medium">A intrat</th>
              <th className="p-4 text-center font-medium">A făcut testul de intrare</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-muted-foreground">
                  Niciun participant înscris în acest proiect.
                </td>
              </tr>
            ) : (
              rows.map((r) => {
                const link = linkDupaProfil.get(r.participantProfileId) ?? null;
                return (
                  <tr key={r.participantProfileId} className="border-t">
                    <td className="p-4">
                      <input
                        type="checkbox"
                        checked={bifati.has(r.participantProfileId)}
                        onChange={() => toggle(r.participantProfileId)}
                        aria-label={`Bifează ${r.fullName}`}
                      />
                    </td>
                    <td className="p-4">
                      <span className="font-medium text-foreground">{r.fullName}</span>
                      <span className="block text-xs text-muted-foreground">{r.email}</span>
                    </td>
                    <td className="p-4">
                      {link ? (
                        <div className="flex items-center gap-2">
                          <code className="max-w-[280px] truncate rounded bg-muted px-2 py-1 text-xs">
                            {link}
                          </code>
                          <button
                            type="button"
                            onClick={() => copiaza(r.participantProfileId, link)}
                            className="inline-flex shrink-0 items-center gap-1 rounded-md border px-2 py-1 text-xs hover:bg-muted"
                          >
                            <CopyIcon className="size-3" />
                            {copiat === r.participantProfileId ? "Copiat" : "Copiază link"}
                          </button>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">încă neinvitat</span>
                      )}
                    </td>
                    <Semn da={r.invited || link !== null} />
                    <Semn da={r.hasAccount} />
                    <Semn da={r.hasTestIn} />
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Semn({ da }: { da: boolean }) {
  return (
    <td className="p-4 text-center">
      {da ? (
        <CheckCircleIcon className="mx-auto size-4" style={{ color: "#15803d" }} aria-label="da" />
      ) : (
        <XCircleIcon className="mx-auto size-4 text-muted-foreground/40" aria-label="nu" />
      )}
    </td>
  );
}
