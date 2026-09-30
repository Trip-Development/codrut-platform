import Link from "next/link";

import type { ParticipantWorkspaceContext } from "@/api/participants";
import { Card } from "@/components/ui/card";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";
import { TRAINING_PROJECT_TYPE } from "@/components/shell/nav";
import { cn } from "@/utils/cn";
import { participantProjectDestination } from "../participant-context";
import { BUN_VENIT, citatulZilei } from "./texte";

/**
 * Pagina de bun venit, pentru omul cu 2+ proiecte — plicul 160, partea B.
 *
 * Totul vine din `summary.contexts`, fără nicio cerere nouă la server. Numele omului nu se
 * citește aici deloc. Proiectele încheiate („Istoric") stau la sfârșit, estompate.
 */
export function PaginaDeBunVenit({
  contexts,
  acum,
}: {
  contexts: ParticipantWorkspaceContext[];
  acum?: Date;
}) {
  const citat = citatulZilei(acum);
  const maiMulteFirme = contexts.length > 1;
  const proiecte = contexts
    .flatMap((context) =>
      context.projects.map((project) => {
        const params = new URLSearchParams();
        params.set("profile", context.participantProfileId);
        params.set("project", project.id);
        return {
          cheie: `${context.participantProfileId}:${project.id}`,
          nume: [maiMulteFirme ? context.companyName : null, project.name].filter(Boolean).join(" · "),
          ce: project.projectType === TRAINING_PROJECT_TYPE ? BUN_VENIT.tipTraining : BUN_VENIT.tipAltul,
          unde: `${participantProjectDestination(project.projectType)}?${params.toString()}`,
          istoric: project.historyBucket === "history",
        };
      }),
    )
    .sort((stanga, dreapta) => Number(stanga.istoric) - Number(dreapta.istoric));

  return (
    <div className="flex max-w-3xl flex-col gap-8">
      <figure data-citatul-zilei className="border-l-2 border-border pl-4">
        <blockquote className="text-base leading-7 text-foreground">{citat.text}</blockquote>
        <figcaption className="mt-1 text-sm text-muted-foreground">{citat.autor}</figcaption>
      </figure>

      <section className="flex flex-col gap-3" aria-labelledby="proiectele-tale">
        <h2 id="proiectele-tale" className="text-base font-semibold text-foreground">
          {BUN_VENIT.numarProiecte(proiecte.length)}
        </h2>
        <div className="grid gap-3 md:grid-cols-2">
          {proiecte.map((proiect) => (
            <Card
              key={proiect.cheie}
              data-proiect-bun-venit
              className={cn("flex flex-col gap-3 p-5", proiect.istoric && "opacity-60")}
            >
              <div className="min-w-0">
                <p className="truncate font-semibold text-foreground">{proiect.nume}</p>
                {/* plicul 166 A3: eticheta tipului nu se repetă când e chiar numele proiectului */}
                {proiect.ce.trim().toLocaleLowerCase("ro") !== proiect.nume.trim().toLocaleLowerCase("ro") ? (
                  <p className="mt-1 text-sm text-muted-foreground">{proiect.ce}</p>
                ) : null}
              </div>
              <Link
                href={proiect.unde}
                className={serverLinkButtonClassName({ variant: "outline", size: "sm", className: "w-fit" })}
              >
                {BUN_VENIT.buton}
              </Link>
            </Card>
          ))}
        </div>
      </section>

      <p className="text-sm leading-6 text-muted-foreground">{BUN_VENIT.ajutor}</p>
    </div>
  );
}
