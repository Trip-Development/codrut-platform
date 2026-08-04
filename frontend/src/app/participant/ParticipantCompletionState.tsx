import Link from "next/link";
import { ArrowRightIcon, CheckCircle2Icon, Clock3Icon } from "lucide-react";

import { serverLinkButtonClassName } from "@/components/ui/server-link-button";

type ParticipantCompletionStateProps = {
  resultCount: number;
  resultsHref?: string;
};

export function ParticipantCompletionState({
  resultCount,
  resultsHref = "/participant/results",
}: ParticipantCompletionStateProps) {
  const resultsReady = resultCount > 0;

  return (
    <section
      aria-labelledby="participant-completion-title"
      className={
        resultsReady
          ? "overflow-hidden rounded-lg bg-burgundy px-6 py-7 text-white shadow-[0_24px_48px_-32px_rgba(137,5,5,0.8)] md:px-8 md:py-8"
          : "rounded-lg border border-border bg-surface px-6 py-7 shadow-none md:px-8 md:py-8"
      }
    >
      <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
        <div className="flex min-w-0 items-start gap-4">
          <span
            className={
              resultsReady
                ? "flex size-11 shrink-0 items-center justify-center rounded-lg bg-white/12 text-white"
                : "flex size-11 shrink-0 items-center justify-center rounded-lg bg-muted text-burgundy"
            }
            aria-hidden="true"
          >
            {resultsReady ? (
              <CheckCircle2Icon className="size-6" strokeWidth={2} />
            ) : (
              <Clock3Icon className="size-6" strokeWidth={1.9} />
            )}
          </span>
          <div className="min-w-0">
            <p className={resultsReady ? "text-xs font-semibold text-white/70" : "text-xs font-semibold text-burgundy"}>
              Toate chestionarele sunt finalizate
            </p>
            <h2
              id="participant-completion-title"
              className={
                resultsReady
                  ? "mt-2 text-3xl font-semibold leading-tight tracking-tight text-white"
                  : "mt-2 text-2xl font-semibold leading-tight tracking-tight text-foreground"
              }
            >
              {resultsReady ? "Rezultatele tale sunt disponibile." : "Răspunsurile au fost trimise."}
            </h2>
            <p className={resultsReady ? "mt-2 text-sm text-white/76" : "mt-2 text-sm text-muted-foreground"}>
              {resultsReady
                ? `${resultCount} ${resultCount === 1 ? "rezultat este pregătit" : "rezultate sunt pregătite"}.`
                : "Rezultatele vor apărea aici când sunt disponibile."}
            </p>
          </div>
        </div>

        {resultsReady ? (
          <Link
            href={resultsHref}
            className={serverLinkButtonClassName({
              size: "lg",
              className: "w-fit border-white bg-white text-burgundy shadow-sm hover:bg-zinc-100 hover:text-burgundy focus-visible:ring-white/70 focus-visible:ring-offset-burgundy",
            })}
          >
            Deschide rezultatele
            <ArrowRightIcon data-icon="inline-end" aria-hidden="true" strokeWidth={2.2} />
          </Link>
        ) : null}
      </div>
    </section>
  );
}
