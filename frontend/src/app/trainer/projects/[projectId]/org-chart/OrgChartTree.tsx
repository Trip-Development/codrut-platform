"use client";

import { useMemo, useState } from "react";

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
    <div className="mt-5 space-y-4">
      <OrgChartWarningPanel warnings={model.warnings} />

      {model.roots.length === 0 ? (
        <p className="rounded-xl border border-dashed border-[var(--border)] bg-surface-muted p-5 text-sm text-foreground/58">
          Nu există încă un root valid pentru organigramă. Corectează managerii marcați în atenționări pentru a reconstrui arborele.
        </p>
      ) : (
        <div className="pb-1">
          <ol aria-label="Organigramă proiect" className="space-y-4">
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
    <aside role="region" className="status-panel-warning space-y-3 p-4" aria-labelledby="org-chart-warnings-title">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id="org-chart-warnings-title" className="text-sm font-semibold">
          Atenționări organigramă ({warnings.length})
        </h3>
        <p className="text-xs font-semibold text-foreground/58">
          Acești participanți nu sunt mutați sub noduri inventate.
        </p>
      </div>
      <ul className="space-y-2">
        {warnings.map((warning) => (
          <li key={`${warning.participantId}-${warning.managerName}`} className="rounded-xl border border-[var(--border)] bg-surface px-3 py-2 text-xs leading-5">
            <span className="font-bold">{warning.participantName}</span>
            <span className="text-foreground/62"> raportează către </span>
            <span className="font-bold">{warning.managerName}</span>
            <span className="text-foreground/62">, dar referința este {warningReasonLabel(warning.reason)}.</span>
          </li>
        ))}
      </ul>
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
      <div className="rounded-xl border border-[var(--border)] bg-surface-muted px-4 py-3 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="break-words font-semibold text-foreground">{node.fullName}</p>
            <p className="mt-1 break-words text-xs font-semibold text-foreground/48">
              {node.position ?? "Rol necompletat"} · {node.location ?? "Locație necompletată"}
            </p>
          </div>
          {hasChildren ? (
            <button
              type="button"
              aria-controls={childrenId}
              aria-expanded={expanded}
              aria-label={`${expanded ? "Ascunde" : "Arată"} raportorii pentru ${node.fullName}`}
              onClick={() => onToggle(node.id)}
              className="tap-soft shrink-0 rounded-full border border-[var(--border)] bg-surface px-3 py-1.5 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy"
            >
              {expanded ? "-" : "+"} {node.children.length} {node.children.length === 1 ? "raportor" : "raportori"}
            </button>
          ) : null}
        </div>
      </div>

      {hasChildren ? (
        expanded ? (
          <ol id={childrenId} className="ml-5 mt-3 space-y-3 border-l border-[var(--border)] pl-4">
            {node.children.map((child) => (
              <OrgChartNodeItem key={child.id} node={child} expandedIds={expandedIds} onToggle={onToggle} />
            ))}
          </ol>
        ) : (
          <p className="ml-5 mt-2 rounded-xl border border-dashed border-[var(--border)] bg-surface px-3 py-2 text-xs font-semibold text-foreground/52">
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

function warningReasonLabel(reason: OrgChartWarning["reason"]): string {
  if (reason === "ambiguous_manager") return "ambiguă";
  if (reason === "self_reference") return "auto-referențiată";
  return "externă sau nerezolvată";
}
