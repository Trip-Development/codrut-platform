import { ChevronDownIcon } from "lucide-react";

import { disclosureTriggerClassName } from "@/components/ui/disclosure";
import { cn } from "@/utils/cn";

const INTERPRETATION_SECTION_TITLES = new Set([
  "Pe scurt",
  "Factori de presiune",
  "Comportament sub stres",
  "Permisiuni utile",
]);

type InterpretationSection = {
  title: string;
  content: string;
};

function structuredInterpretation(value: React.ReactNode): InterpretationSection[] {
  if (typeof value !== "string") return [];

  const sections: InterpretationSection[] = [];
  let current: { title: string; lines: string[] } | null = null;
  for (const line of value.replaceAll("\r\n", "\n").split("\n")) {
    const normalized = line.trim();
    if (INTERPRETATION_SECTION_TITLES.has(normalized)) {
      if (current) {
        sections.push({ title: current.title, content: current.lines.join("\n").trim() });
      }
      current = { title: normalized, lines: [] };
    } else if (current) {
      current.lines.push(line);
    }
  }
  if (current) {
    sections.push({ title: current.title, content: current.lines.join("\n").trim() });
  }

  return sections.length >= 2 && sections.every((section) => section.content)
    ? sections
    : [];
}

function InterpretationSectionBody({ content }: { content: string }) {
  const blocks = content.split(/\n{2,}/).map((block) => block.trim()).filter(Boolean);
  return (
    <div className="mt-2 grid gap-2 text-base leading-7 text-muted-foreground">
      {blocks.map((block, blockIndex) => {
        const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
        if (lines.every((line) => /^[•-]\s+/.test(line))) {
          return (
            <ul key={blockIndex} className="grid list-disc gap-1 pl-5 marker:text-brand-text">
              {lines.map((line, lineIndex) => (
                <li key={lineIndex} className="pl-0.5 text-pretty">
                  {line.replace(/^[•-]\s+/, "")}
                </li>
              ))}
            </ul>
          );
        }
        return <p key={blockIndex} className="text-pretty whitespace-pre-line">{block}</p>;
      })}
    </div>
  );
}

export function InterpretationDisclosure({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const sections = structuredInterpretation(children);

  return (
    <details className={cn("group mt-4 text-muted-foreground", className)}>
      <summary className={cn(disclosureTriggerClassName, "inline-flex min-h-11 items-center gap-2 px-2 py-1.5 text-sm font-semibold text-foreground md:min-h-9")}>
        <span className="group-open:hidden">Vezi interpretarea completă</span>
        <span className="hidden group-open:inline">Ascunde interpretarea</span>
        <ChevronDownIcon className="size-3.5 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden="true" />
      </summary>
      {sections.length > 0 ? (
        <div className="mt-3 grid max-w-5xl gap-3 md:grid-cols-2">
          {sections.map((section) => (
            <section key={section.title} className="rounded-xl bg-surface-muted px-4 py-4 md:px-5">
              <h5 className="text-sm font-semibold text-foreground">{section.title}</h5>
              <InterpretationSectionBody content={section.content} />
            </section>
          ))}
        </div>
      ) : (
        <div className="mt-3 max-w-4xl rounded-xl bg-surface-muted px-4 py-4 text-base leading-7 whitespace-pre-line">
          {children}
        </div>
      )}
    </details>
  );
}
