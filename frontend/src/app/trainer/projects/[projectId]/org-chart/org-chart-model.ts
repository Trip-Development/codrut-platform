import type { CompanyParticipant } from "@/api/companies";
import { managerReferenceKey, normalizeReportsToName } from "@/api/roster-format";

export type OrgChartNode = {
  id: string;
  fullName: string;
  reportsToName: string;
  position: string | null;
  location: string | null;
  roleGroup: string | null;
  children: OrgChartNode[];
  descendantCount: number;
};

export type OrgChartWarning = {
  participantId: string;
  participantName: string;
  managerName: string;
  reason: "unresolved_manager" | "ambiguous_manager" | "self_reference";
};

export type OrgChartModel = {
  roots: OrgChartNode[];
  warnings: OrgChartWarning[];
  participantCount: number;
};

type MutableOrgChartNode = Omit<OrgChartNode, "children" | "descendantCount"> & {
  children: MutableOrgChartNode[];
  descendantCount: number;
  originalIndex: number;
};

export function buildOrgChartModel(participants: CompanyParticipant[]): OrgChartModel {
  const nodes = participants.map(toMutableNode);
  const nodesByNameKey = new Map<string, MutableOrgChartNode[]>();

  for (const node of nodes) {
    const nameKey = managerReferenceKey(node.fullName);
    if (!nameKey) continue;
    const matches = nodesByNameKey.get(nameKey) ?? [];
    matches.push(node);
    nodesByNameKey.set(nameKey, matches);
  }

  const roots: MutableOrgChartNode[] = [];
  const warnings: OrgChartWarning[] = [];

  for (const node of nodes) {
    if (!node.reportsToName) {
      roots.push(node);
      continue;
    }

    const managerKey = managerReferenceKey(node.reportsToName);
    const managerMatches = nodesByNameKey.get(managerKey) ?? [];

    if (managerMatches.length === 0) {
      warnings.push({
        participantId: node.id,
        participantName: node.fullName,
        managerName: node.reportsToName,
        reason: "unresolved_manager",
      });
      continue;
    }

    if (managerMatches.length > 1) {
      warnings.push({
        participantId: node.id,
        participantName: node.fullName,
        managerName: node.reportsToName,
        reason: "ambiguous_manager",
      });
      continue;
    }

    const [manager] = managerMatches;
    if (manager.id === node.id) {
      warnings.push({
        participantId: node.id,
        participantName: node.fullName,
        managerName: node.reportsToName,
        reason: "self_reference",
      });
      continue;
    }

    manager.children.push(node);
  }

  return {
    roots: roots.sort(compareRootNodes).map(finalizeNode),
    warnings,
    participantCount: participants.length,
  };
}

function toMutableNode(participant: CompanyParticipant, originalIndex: number): MutableOrgChartNode {
  return {
    id: participant.id,
    fullName: participant.full_name,
    reportsToName: normalizeReportsToName(participant.reports_to_name),
    position: participant.position,
    location: participant.location,
    roleGroup: participant.role_group,
    children: [],
    descendantCount: 0,
    originalIndex,
  };
}

function finalizeNode(node: MutableOrgChartNode): OrgChartNode {
  const children = node.children
    .sort((left, right) => left.originalIndex - right.originalIndex)
    .map(finalizeNode);
  const descendantCount = children.reduce((total, child) => total + child.descendantCount + 1, 0);

  return {
    id: node.id,
    fullName: node.fullName,
    reportsToName: node.reportsToName,
    position: node.position,
    location: node.location,
    roleGroup: node.roleGroup,
    children,
    descendantCount,
  };
}

function compareRootNodes(left: MutableOrgChartNode, right: MutableOrgChartNode): number {
  const rankDifference = rootRank(left) - rootRank(right);
  return rankDifference === 0 ? left.originalIndex - right.originalIndex : rankDifference;
}

function rootRank(node: MutableOrgChartNode): number {
  const text = normalizeRankText(`${node.roleGroup ?? ""} ${node.position ?? ""} ${node.fullName}`);

  if (/\b(ceo|chief executive|director general|director executiv|general manager|presedinte|president)\b/.test(text)) {
    return 0;
  }

  if (/\b(leadership|director|manager|lead)\b/.test(text)) {
    return 1;
  }

  return 2;
}

function normalizeRankText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}
