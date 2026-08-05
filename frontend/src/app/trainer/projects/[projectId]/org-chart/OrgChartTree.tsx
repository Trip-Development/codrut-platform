"use client";

import { useMemo, useState, type ReactNode } from "react";
import { AlertTriangleIcon, ChevronDownIcon, ChevronRightIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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
        <Card className="gap-0 p-3 sm:p-4">
          <ol aria-label="Organigramă proiect" className="flex min-w-0 flex-col gap-3">
            {model.roots.map((root) => (
              <OrgChartNodeItem key={root.id} node={root} depth={0} expandedIds={expandedIds} onToggle={toggleNode} />
            ))}
          </ol>
        </Card>
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
        <AlertTriangleIcon aria-hidden="true" className="size-4.5 shrink-0 text-warning-ink" strokeWidth={1.8} />
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
  depth,
  expandedIds,
  onToggle,
}: {
  node: OrgChartNode;
  depth: number;
  expandedIds: Set<string>;
  onToggle: (nodeId: string) => void;
}) {
  const hasChildren = node.children.length > 0;
  const expanded = hasChildren && expandedIds.has(node.id);
  const childrenId = `org-chart-children-${node.id}`;

  return (
    <li>
      <article
        className={cn(
          "rounded-lg border bg-muted/20 px-3 py-3 transition-colors sm:px-4",
          hasChildren && "bg-surface",
          depth === 0 && "border-primary/30",
        )}
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <NodeMark name={node.fullName} depth={depth} />
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
              className="w-full justify-center sm:w-auto"
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
          <ol id={childrenId} className="relative ml-3 mt-3 flex flex-col gap-3 border-l border-border pl-3 sm:ml-5 sm:pl-5">
            {node.children.map((child) => (
              <OrgChartNodeItem key={child.id} node={child} depth={depth + 1} expandedIds={expandedIds} onToggle={onToggle} />
            ))}
          </ol>
        ) : (
          <p className="ml-3 mt-2 border-l border-border px-3 py-2 text-xs font-semibold text-muted-foreground sm:ml-5">
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

function NodeMark({ name, depth }: { name: string; depth: number }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex size-10 shrink-0 items-center justify-center rounded-md text-sm font-semibold ring-1 ring-inset",
        depth === 0
          ? "bg-primary text-primary-foreground ring-primary/20"
          : depth === 1
            ? "bg-foreground text-background ring-foreground/15"
            : "bg-muted text-foreground ring-border",
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

function nodeInitials(name: string): string {
  const words = name
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (words.length === 0) return "OR";
  if (words.length === 1) return words[0].slice(0, 2).toLocaleUpperCase("ro");
  return `${words[0][0] ?? ""}${words[1][0] ?? ""}`.toLocaleUpperCase("ro");
}

function warningReasonLabel(reason: OrgChartWarning["reason"]): string {
  if (reason === "ambiguous_manager") return "ambiguă";
  if (reason === "self_reference") return "auto-referențiată";
  return "externă sau nerezolvată";
}
