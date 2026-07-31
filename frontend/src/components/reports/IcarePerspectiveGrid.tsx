import type { ReactNode } from "react";

export type IcarePerspective = {
  id: string;
  label: string;
  responseCount: number;
  content: ReactNode;
};

export function IcarePerspectiveGrid({
  perspectives,
  ariaLabel = "Perspective iCARE",
}: {
  perspectives: IcarePerspective[];
  ariaLabel?: string;
}) {
  if (perspectives.length === 0) return null;

  return (
    <section
      aria-label={ariaLabel}
      className="grid items-start gap-4 lg:grid-cols-3"
    >
      {perspectives.map((perspective) => {
        const responseCopy = `${perspective.responseCount} ${perspective.responseCount === 1 ? "răspuns" : "răspunsuri"}`;
        return (
          <div
            key={perspective.id}
            aria-label={`${perspective.label}: ${responseCopy}`}
            className="min-w-0"
            role="group"
          >
            {perspective.content}
          </div>
        );
      })}
    </section>
  );
}
