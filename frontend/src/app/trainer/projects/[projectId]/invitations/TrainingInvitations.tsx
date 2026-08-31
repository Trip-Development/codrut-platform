"use client";

import { useState } from "react";
import { CheckCircleIcon, XCircleIcon } from "lucide-react";

import { sendParticipantInvitations } from "@/api/companies";
import type { TrainingInvitation } from "@/api/practice";
import { Card } from "@/components/ui/card";

/**
 * Invitațiile în formă de training.
 *
 * Formularul de coaching e construit în jurul ciclurilor de evaluare; pe un
 * proiect de training nu există niciun ciclu, deci cere ceva ce n-are de unde lua.
 *
 * Mecanismul de invitație și de făcut cont există și e bun — nu s-a construit
 * altul. Se cheamă exact aceeași rută (`POST /companies/{id}/participants/invitations`),
 * fără ciclu; backendul o acceptă așa.
 *
 *     bifezi oamenii → Trimite invitații → primesc email cu link
 *     → își fac contul → intră direct la testul de intrare
 */
export function TrainingInvitations({
  companyId,
  projectId,
  rows,
}: {
  companyId: string;
  projectId: string;
  rows: TrainingInvitation[];
}) {
  const [bifati, setBifati] = useState<Set<string>>(new Set());
  const [trimit, setTrimit] = useState(false);
  const [mesaj, setMesaj] = useState<string | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);

  function toggle(id: string) {
    setBifati((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setMesaj(null);
  }

  function toggleToti() {
    setBifati((prev) =>
      prev.size === rows.length ? new Set() : new Set(rows.map((r) => r.participantProfileId)),
    );
    setMesaj(null);
  }

  async function trimite() {
    if (bifati.size === 0) return;
    setTrimit(true);
    setEroare(null);
    setMesaj(null);
    try {
      const rezultat = await sendParticipantInvitations(companyId, {
        participantIds: Array.from(bifati),
        projectId,
        assessmentCycleId: null,
        mode: "email",
        targetMode: "selected",
      });
      setMesaj(
        `Trimise: ${rezultat.emails_sent} · în așteptare: ${rezultat.emails_queued} · ` +
          `nereușite: ${rezultat.emails_failed}. Reîncarcă pagina ca să vezi starea nouă.`,
      );
      setBifati(new Set());
    } catch (e) {
      setEroare(e instanceof Error ? e.message : "Nu am putut trimite invitațiile.");
    } finally {
      setTrimit(false);
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
        <div>
          <h3 className="text-base font-semibold text-foreground">Invitații</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Bifează oamenii și trimite. Primesc un email cu link, își fac contul și intră
            direct la testul de intrare.
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

      {mesaj ? <p className="border-b px-5 py-3 text-sm text-muted-foreground">{mesaj}</p> : null}
      {eroare ? <p className="border-b px-5 py-3 text-sm text-danger">{eroare}</p> : null}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] text-left text-sm">
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
              <th className="p-4 text-center font-medium">Invitat</th>
              <th className="p-4 text-center font-medium">A intrat</th>
              <th className="p-4 text-center font-medium">A făcut testul de intrare</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="p-8 text-center text-muted-foreground">
                  Niciun participant înscris în acest proiect.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
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
                  <Semn da={r.invited} />
                  <Semn da={r.hasAccount} />
                  <Semn da={r.hasTestIn} />
                </tr>
              ))
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
