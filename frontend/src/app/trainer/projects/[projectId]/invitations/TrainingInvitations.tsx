"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { CheckCircleIcon, CopyIcon, XCircleIcon } from "lucide-react";

import { sendTrainingInvitations } from "@/api/practice";
import type { TrainingInvitation, TrainingInvitationSent } from "@/api/practice";
import { Card } from "@/components/ui/card";

/**
 * Invitațiile la training. Sunt invitații la CONT, nu la un chestionar.
 *
 * La coaching sunt două feluri de oameni: liderul, care are cont, și colegii lui,
 * care primesc o legătură trecătoare către un chestionar și dispar. De aceea
 * invitația de acolo e legată de asignări — legătura ESTE sarcina.
 *
 * La training nu sunt două feluri. Toți exersează cu Cody, toți dau testul de
 * intrare și pe cel de ieșire, toți au tablou de competențe. Nu primesc niciun
 * chestionar: trebuie doar să intre în cont, unde găsesc pașii următori.
 *
 *     bifezi oamenii → li se face contul → email cu link de pus parola
 *     → își pun parola → cont permanent → intră la testul de intrare
 *
 * Linkul se poate arăta o singură dată, la trimitere: în bază nu se păstrează
 * decât amprenta lui, ca la orice link de parolă. „Trimite din nou" face unul
 * proaspăt și îl stinge pe cel vechi.
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

  const linkDupaProfil = new Map<string, string>();
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
      startReimprospatare(() => router.refresh());
    } catch (e) {
      setEroare(e instanceof Error ? e.message : "Nu am putut trimite invitațiile.");
    } finally {
      setTrimit(false);
    }
  }

  const cuLink = (rezultate ?? []).filter((r) => r.inviteUrl).length;
  const laCoada = (rezultate ?? []).filter((r) => r.emailQueued).length;
  const esuate = (rezultate ?? []).filter((r) => !r.inviteUrl);
  const auLinkFaraEmail = (rezultate ?? []).find((r) => r.inviteUrl && !r.emailQueued && r.error);

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
        <div>
          <h3 className="text-base font-semibold text-foreground">Invitații</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Bifează oamenii și trimite. Fiecare primește pe email un link prin care își pune
            parola. După ce intră, găsește acolo pașii următori. Linkul apare și mai jos, ca
            să-l poți da mai departe chiar dacă emailul nu pleacă.
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
                (laCoada === 0
                  ? ". Emailul nu a intrat la coadă — copiază linkurile din tabel."
                  : laCoada === cuLink
                    ? `, iar ${laCoada === 1 ? "emailul a intrat" : "emailurile au intrat"} la coadă.`
                    : `, iar ${laCoada} au intrat la coadă. Pentru restul, copiază linkul din tabel.`)}
          </p>
          {laCoada > 0 ? (
            <p className="mt-1 text-xs text-muted-foreground">
              {"„La coadă” nu înseamnă „a ajuns”."} Plecarea se face după aceea și poate eșua la
              furnizorul de email. Linkul din tabel merge oricum.
            </p>
          ) : null}
          {auLinkFaraEmail ? (
            <p className="mt-2 text-xs text-muted-foreground">{auLinkFaraEmail.error}</p>
          ) : null}
          {cuLink > 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">
              Copiază linkurile acum dacă ai nevoie de ele: sunt linkuri de parolă și nu se
              păstrează. Le poți face oricând din nou cu „Trimite invitații”.
            </p>
          ) : null}
          {esuate.length > 0 ? (
            <ul className="mt-2 space-y-1 text-xs text-danger">
              {esuate.map((r) => (
                <li key={r.participantProfileId}>
                  {r.fullName ?? r.email ?? "Participant"}: {r.error ?? "nu s-a putut."}
                </li>
              ))}
            </ul>
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
              <th className="p-4 font-medium">Link de pus parola</th>
              <th className="p-4 text-center font-medium">Invitat</th>
              <th className="p-4 text-center font-medium">Și-a făcut contul</th>
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
                        <span className="text-xs text-muted-foreground">
                          {r.hasAccount
                            ? "și-a pus parola"
                            : r.invited
                              ? "trimis — bifează și trimite din nou pentru un link nou"
                              : "încă neinvitat"}
                        </span>
                      )}
                    </td>
                    <Semn da={r.invited} />
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
