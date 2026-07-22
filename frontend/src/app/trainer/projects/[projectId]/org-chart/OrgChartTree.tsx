"use client";

import { useMemo, useState, type ReactNode } from "react";
import { AlertTriangleIcon, ChevronDownIcon, ChevronRightIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";
import type { OrgChartModel, OrgChartNode, OrgChartWarning } from "./org-chart-model";

type OrgChartTreeProps = {
  model: OrgChartModel;
};

export function OrgChartTree({ model }: OrgChartTreeProps) {
  const defaultExpandedIds = useMemo(() => collectDefaultExpandedIds(model.roots), [model.roots]);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => defaultExpandedIds);

  const toggleNode = (nodeId: string) => {
    setExpandedIds((current) => {
      const next = new Set(current);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  return (
    <div className="flex flex-col gap-4">
      <OrgChartWarningPanel warnings={model.warnings} />

      {model.roots.length === 0 ? (
        <p className="border-y border-border py-8 text-center text-sm font-medium text-muted-foreground">
          Nu există încă un root valid pentru organigramă. Corectează managerii marcați în atenționări pentru a reconstrui arborele.
        </p>
      ) : (
        <div className="overflow-x-auto border-y border-border bg-surface">
          <ol aria-label="Organigramă proiect" className="flex min-w-[62rem] flex-col gap-3 py-4">
            {model.roots.map((root) => (
              <OrgChartNodeItem key={root.id} node={root} expandedIds={expandedIds} onToggle={toggleNode} />
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

function OrgChartWarningPanel({ warnings }: { warnings: OrgChartWarning[] }) {
  if (warnings.length === 0) return null;

  return (
    <aside
      role="region"
      className="status-warning border-l-2 px-4 py-3"
      aria-labelledby="org-chart-warnings-title"
    >
      <div className="flex items-start gap-3">
        <span className="status-warning-soft inline-flex size-8 shrink-0 items-center justify-center rounded-full">
          <AlertTriangleIcon aria-hidden="true" className="size-4.5" strokeWidth={1.8} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 id="org-chart-warnings-title" className="text-sm font-semibold">
              Atenționări organigramă ({warnings.length})
            </h3>
          </div>
          <ul className="mt-3 grid gap-2 md:grid-cols-2">
            {warnings.map((warning) => (
              <li key={`${warning.participantId}-${warning.managerName}`} className="border-t border-warning-ink/20 pt-2 text-xs leading-5 text-foreground">
                <span className="font-semibold">{warning.participantName}</span>
                <span className="text-muted-foreground"> raportează către </span>
                <span className="font-semibold">{warning.managerName}</span>
                <span className="text-muted-foreground">, dar referința este {warningReasonLabel(warning.reason)}.</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </aside>
  );
}

function OrgChartNodeItem({
  node,
  expandedIds,
  onToggle,
}: {
  node: OrgChartNode;
  expandedIds: Set<string>;
  onToggle: (nodeId: string) => void;
}) {
  const hasChildren = node.children.length > 0;
  const expanded = hasChildren && expandedIds.has(node.id);
  const childrenId = `org-chart-children-${node.id}`;

  return (
    <li>
      <article className={cn("border-l-2 border-border bg-muted/25 px-4 py-3", hasChildren && "border-primary/35 bg-surface")}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <NodeMark name={node.fullName} />
            <div className="min-w-0">
              <p className="break-words font-semibold text-foreground">{node.fullName}</p>
              <p className="mt-1 break-words text-xs font-semibold text-muted-foreground">
                {node.position ?? "Rol necompletat"} / {node.location ?? "Locație necompletată"}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {node.roleGroup ? <NodeChip>{node.roleGroup}</NodeChip> : null}
                {node.descendantCount > 0 ? <NodeChip>{node.descendantCount} raportori total</NodeChip> : null}
              </div>
            </div>
          </div>
          {hasChildren ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-controls={childrenId}
              aria-expanded={expanded}
              aria-label={`${expanded ? "Ascunde" : "Arată"} raportorii pentru ${node.fullName}`}
              onClick={() => onToggle(node.id)}
            >
              {expanded ? (
                <ChevronDownIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
              ) : (
                <ChevronRightIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
              )}
              {node.children.length} {node.children.length === 1 ? "raportor" : "raportori"}
            </Button>
          ) : null}
        </div>
      </article>

      {hasChildren ? (
        expanded ? (
          <ol id={childrenId} className="ml-7 mt-3 flex flex-col gap-3 border-l pl-5">
            {node.children.map((child) => (
              <OrgChartNodeItem key={child.id} node={child} expandedIds={expandedIds} onToggle={onToggle} />
            ))}
          </ol>
        ) : (
          <p className="ml-7 mt-2 border-l border-border px-3 py-2 text-xs font-semibold text-muted-foreground">
            {node.descendantCount} raportori ascunși sub {node.fullName}.
          </p>
        )
      ) : null}
    </li>
  );
}

function collectDefaultExpandedIds(roots: OrgChartNode[]): Set<string> {
  const expandedIds = new Set<string>();

  const visit = (node: OrgChartNode, depth: number) => {
    if (node.children.length > 0 && depth < 2) {
      expandedIds.add(node.id);
      node.children.forEach((child) => visit(child, depth + 1));
    }
  };

  roots.forEach((root) => visit(root, 0));
  return expandedIds;
}

function NodeMark({ name }: { name: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex size-10 shrink-0 items-center justify-center rounded-md text-sm font-semibold text-white",
        nodeMarkClass(name),
      )}
    >
      {nodeInitials(name)}
    </span>
  );
}

function NodeChip({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md bg-surface px-2 py-1 text-[0.7rem] font-semibold text-muted-foreground ring-1 ring-border">
      {children}
    </span>
  );
}

function nodeMarkClass(seed: string): string {
  const classes = [
    "bg-primary",
    "bg-foreground",
    "bg-muted-foreground",
    "bg-success-ink",
    "bg-burgundy-800",
  ];
  return classes[Math.abs(hashString(seed)) % classes.length];
}

function nodeInitials(name: string): string {
  const words = name
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (words.length === 0) return "OR";
  if (words.length === 1) return words[0].slice(0, 2).toLocaleUpperCase("ro");
  return `${words[0][0] ?? ""}${words[1][0] ?? ""}`.toLocaleUpperCase("ro");
}

function hashString(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0;
  }
  return hash;
}

function warningReasonLabel(reason: OrgChartWarning["reason"]): string {
  if (reason === "ambiguous_manager") return "ambiguă";
  if (reason === "self_reference") return "auto-referențiată";
  return "externă sau nerezolvată";
}
