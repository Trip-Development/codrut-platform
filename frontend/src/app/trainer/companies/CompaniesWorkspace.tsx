"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import {
  AlertTriangleIcon,
  ArrowRightIcon,
  BriefcaseBusinessIcon,
  Building2Icon,
  DownloadIcon,
  FilterIcon,
  XIcon,
  type LucideIcon,
} from "lucide-react";

import { type CompanyListItem } from "@/api/companies";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { SelectControl } from "@/components/ui/select-control";
import { SearchableCombobox } from "@/components/ui/searchable-combobox";
import { Sheet, SheetBody, SheetFooter, SheetHeader } from "@/components/ui/sheet";
import { useUrlState } from "@/hooks/use-url-state";
import { cn } from "@/utils/cn";
import {
  WorkspaceSearchInput,
} from "../projects/project-workspace-controls";
import type { CreateCompanyModalProps } from "./CreateCompanyModal";

export type CompaniesWorkspaceProps = {
  initialCompanies: CompanyListItem[];
};

type CompanyIdentity = {
  id: string;
  name: string;
};

const DynamicCreateCompanyModal = dynamic<CreateCompanyModalProps>(
  () => import("./CreateCompanyModal").then((mod) => mod.CreateCompanyModal),
  { ssr: false },
);

export function CompaniesWorkspace({ initialCompanies }: CompaniesWorkspaceProps) {
  const { get, searchKey, isPending: isUrlPending, setParam, setParams } = useUrlState();
  const [companies, setCompanies] = useState<CompanyListItem[]>(initialCompanies);
  const [message, setMessage] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(get("modal") === "create-company");
  const [searchQuery, setSearchQuery] = useState(get("q") ?? "");
  const [statusFilter, setStatusFilter] = useState(get("status") ?? "");
  const [stageFilter, setStageFilter] = useState(get("stage") ?? "");
  const [extraFilter, setExtraFilter] = useState(get("filter") ?? "");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [selectedCompanyIds, setSelectedCompanyIds] = useState<string[]>([]);
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const deferredSearchQuery = useDeferredValue(searchQuery);
  const isFilterPending = isUrlPending || searchQuery !== deferredSearchQuery;

  useEffect(() => {
    setSearchQuery(get("q") ?? "");
    setStatusFilter(get("status") ?? "");
    setStageFilter(get("stage") ?? "");
    setExtraFilter(get("filter") ?? "");
    setCreateOpen(get("modal") === "create-company");
  }, [get, searchKey]);

  const filteredCompanies = useMemo(() => {
    const query = normalizeSearchText(deferredSearchQuery);

    return companies
      .filter((company) => {
        if (!query) return true;
        return normalizeSearchText(
          `${company.name} ${company.id} ${formatCompanyCode(company)} ${stageLabel(company.stage)} ${companyStatusLabel(company)}`,
        ).includes(query);
      })
      .filter((company) => !statusFilter || companyStatusKey(company) === statusFilter)
      .filter((company) => !stageFilter || company.stage === stageFilter)
      .filter((company) => matchExtraFilter(company, extraFilter))
      .sort((first, second) => {
        const statusDifference = companyStatusRank(first) - companyStatusRank(second);
        if (statusDifference !== 0) return statusDifference;
        return first.name.localeCompare(second.name, "ro");
      });
  }, [companies, deferredSearchQuery, extraFilter, stageFilter, statusFilter]);

  const activeCompanies = filteredCompanies.filter((company) => companyStatusKey(company) === "active").length;
  const companiesNeedingAttention = filteredCompanies.filter(
    (company) => companyStatusKey(company) === "attention",
  ).length;
  const pendingAssignments = filteredCompanies.reduce(
    (total, company) => total + Math.max(0, company.assignmentCount - company.completedCount),
    0,
  );
  const activeFilterCount = [statusFilter, stageFilter, extraFilter].filter(Boolean).length;
  const pageCount = Math.max(1, Math.ceil(filteredCompanies.length / pageSize));
  const safePageIndex = Math.min(pageIndex, pageCount - 1);
  const pageStart = safePageIndex * pageSize;
  const pageEnd = Math.min(pageStart + pageSize, filteredCompanies.length);
  const pagedCompanies = filteredCompanies.slice(pageStart, pageEnd);
  const paginationItems = paginationWindow(pageCount, safePageIndex);
  const pageIds = pagedCompanies.map((company) => company.id);
  const selectedCount = selectedCompanyIds.length;
  const allPageSelected = pageIds.length > 0 && pageIds.every((id) => selectedCompanyIds.includes(id));
  const somePageSelected = pageIds.some((id) => selectedCompanyIds.includes(id));

  useEffect(() => {
    setPageIndex(0);
  }, [extraFilter, pageSize, searchQuery, stageFilter, statusFilter]);

  useEffect(() => {
    setSelectedCompanyIds((current) =>
      current.filter((id) => companies.some((company) => company.id === id)),
    );
  }, [companies]);

  function closeCreateModal() {
    setCreateOpen(false);
    setParams({ modal: null }, "replace");
  }

  function updateFilter(key: "status" | "stage" | "filter", value: string) {
    if (key === "status") setStatusFilter(value);
    if (key === "stage") setStageFilter(value);
    if (key === "filter") setExtraFilter(value);
    setParam(key, value, "replace");
  }

  function resetFilters() {
    setSearchQuery("");
    setStatusFilter("");
    setStageFilter("");
    setExtraFilter("");
    setParams({ q: null, status: null, stage: null, filter: null }, "replace");
  }

  function toggleCompanySelection(companyId: string) {
    setSelectedCompanyIds((current) =>
      current.includes(companyId)
        ? current.filter((id) => id !== companyId)
        : [...current, companyId],
    );
  }

  function togglePageSelection() {
    setSelectedCompanyIds((current) => {
      if (allPageSelected) return current.filter((id) => !pageIds.includes(id));
      return Array.from(new Set([...current, ...pageIds]));
    });
  }

  function exportCompanies(companyRows = filteredCompanies, fileName = "companii-codrut.csv") {
    const rows = companyRows.map((company) => [
      company.name,
      formatCompanyCode(company),
      companyStatusLabel(company),
      stageLabel(company.stage),
      company.projectCount,
      company.participantCount,
      company.completedCount,
      company.assignmentCount,
      Math.max(0, company.assignmentCount - company.completedCount),
    ]);
    const header = [
      "Companie",
      "Cod",
      "Status",
      "Etapă",
      "Proiecte",
      "Participanți",
      "Completări",
      "Asignări",
      "De urmărit",
    ];
    const csv = [header, ...rows]
      .map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = fileName;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function exportSelectedCompanies() {
    const selectedCompanies = companies.filter((company) => selectedCompanyIds.includes(company.id));
    if (selectedCompanies.length === 0) return;
    exportCompanies(selectedCompanies, "companii-selectate-codrut.csv");
  }

  function renderFilterControls() {
    return (
      <>
        <FilterSelect
          icon={FilterIcon}
          label="Status"
          value={statusFilter}
          onChange={(value) => updateFilter("status", value)}
          options={[
            ["", "Toate statusurile"],
            ["attention", "Necesită acțiune"],
            ["active", "Active"],
            ["inactive", "De configurat"],
          ]}
        />
        <FilterSelect
          icon={BriefcaseBusinessIcon}
          label="Etapă"
          value={stageFilter}
          onChange={(value) => updateFilter("stage", value)}
          options={[
            ["", "Toate etapele"],
            ["setup", "Configurare"],
            ["invites", "Invitații"],
            ["completion", "În lucru"],
            ["reporting", "Raportare"],
          ]}
        />
        <FilterSelect
          icon={FilterIcon}
          label="Activitate"
          value={extraFilter}
          onChange={(value) => updateFilter("filter", value)}
          options={[
            ["", "Toată activitatea"],
            ["with-pending", "Completări de urmărit"],
            ["without-projects", "Fără proiect"],
            ["reporting", "Pregătite de raportare"],
          ]}
        />
      </>
    );
  }

  return (
    <div className="flex min-w-0 flex-col gap-5">
      <section
        className="grid min-w-0 gap-3 rounded-lg border bg-surface p-3 lg:grid-cols-2 xl:grid-cols-[minmax(24rem,1fr)_minmax(11rem,13rem)_minmax(11rem,13rem)_minmax(11rem,13rem)]"
        aria-label="Filtre companii"
      >
        <div className="flex min-w-0 items-center gap-2 lg:contents">
          <WorkspaceSearchInput
            id="companies-search"
            label="Caută companie"
            value={searchQuery}
            onValueChange={(value) => {
              setSearchQuery(value);
              setParam("q", value || null, "replace");
            }}
            placeholder="Caută după denumire, cod, status sau etapă"
            className="min-w-0 flex-1 lg:col-span-2 xl:col-span-1"
          />
          <Button
            type="button"
            variant="outline"
            className="lg:hidden"
            aria-haspopup="dialog"
            aria-label={activeFilterCount > 0 ? `Filtre, ${activeFilterCount} active` : "Filtre"}
            onClick={() => setFiltersOpen(true)}
          >
            <FilterIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
            Filtre{activeFilterCount > 0 ? ` (${activeFilterCount})` : ""}
          </Button>
        </div>
        <div className="hidden lg:contents">{renderFilterControls()}</div>
      </section>

      <Sheet
        open={filtersOpen}
        onOpenChange={setFiltersOpen}
        labelledBy="company-filters-title"
        describedBy="company-filters-description"
      >
        <SheetHeader className="flex items-start justify-between gap-4">
          <div>
            <h2 id="company-filters-title" className="text-lg font-semibold text-foreground">Filtre</h2>
            <p id="company-filters-description" className="mt-1 text-sm text-muted-foreground">
              Restrânge lista fără să pierzi căutarea curentă.
            </p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="Închide filtrele"
            onClick={() => setFiltersOpen(false)}
          >
            <XIcon aria-hidden="true" strokeWidth={1.8} />
          </Button>
        </SheetHeader>
        <SheetBody className="flex flex-col gap-4">{filtersOpen ? renderFilterControls() : null}</SheetBody>
        <SheetFooter className="flex items-center justify-between gap-3">
          <Button type="button" variant="ghost" onClick={resetFilters}>Resetează</Button>
          <Button type="button" onClick={() => setFiltersOpen(false)}>Gata</Button>
        </SheetFooter>
      </Sheet>

      <div className="min-h-5 px-1 text-xs font-medium text-muted-foreground" role="status" aria-live="polite">
        {isFilterPending ? "Se actualizează lista" : null}
      </div>

      {message ? <InlineFeedback>{message}</InlineFeedback> : null}

      {createOpen ? (
        <DynamicCreateCompanyModal
          onClose={closeCreateModal}
          onCreated={(created) => {
            setCompanies((current) => mergeCompanies(current, [companyToListItem(created)]));
          }}
          onMessage={(nextMessage) => setMessage(nextMessage || null)}
        />
      ) : null}

      {companies.length === 0 ? (
        <CompaniesEmptyState
          title="Nu există companii încă"
          description="Adaugă prima companie pentru a crea proiectul și rosterul."
          actionLabel="Companie nouă"
          onAction={() => {
            setCreateOpen(true);
            setParam("modal", "create-company");
          }}
        />
      ) : filteredCompanies.length === 0 ? (
        <CompaniesEmptyState
          title="Nicio companie găsită"
          description="Schimbă căutarea sau filtrele active."
          actionLabel="Resetează filtrele"
          onAction={resetFilters}
        />
      ) : (
        <section
          aria-label="Lista companiilor"
          aria-busy={isFilterPending}
          className={cn(
            "min-w-0 overflow-hidden rounded-lg border bg-surface transition-opacity",
            isFilterPending && "opacity-70",
          )}
        >
          <div className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
            {selectedCount > 0 ? (
              <div className="flex flex-wrap items-center gap-3">
                <p className="text-sm font-semibold text-foreground">
                  {selectedCount} {selectedCount === 1 ? "selectată" : "selectate"}
                </p>
                <Button type="button" variant="outline" size="sm" onClick={exportSelectedCompanies}>
                  <DownloadIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
                  Exportă selecția
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setSelectedCompanyIds([])}>
                  Renunță
                </Button>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                <span className="font-semibold text-foreground">{filteredCompanies.length}</span>{" "}
                {filteredCompanies.length === 1 ? "companie" : "companii"}
                <span aria-hidden="true"> · </span>{activeCompanies} {activeCompanies === 1 ? "activă" : "active"}
                <span aria-hidden="true"> · </span>{companiesNeedingAttention} necesită acțiune
                <span aria-hidden="true"> · </span>{pendingAssignments}{" "}
                {pendingAssignments === 1 ? "completare" : "completări"} de urmărit
              </p>
            )}
            <div className="flex items-center gap-2">
              {(searchQuery || statusFilter || stageFilter || extraFilter) ? (
                <Button type="button" variant="ghost" size="sm" onClick={resetFilters}>
                  <XIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
                  Resetează
                </Button>
              ) : null}
              <Button type="button" variant="outline" size="sm" onClick={() => exportCompanies()}>
                <DownloadIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
                Exportă
              </Button>
            </div>
          </div>

          <div
            className="w-full max-w-full md:overflow-x-auto md:overscroll-x-contain md:[scrollbar-width:thin]"
            aria-label="Tabelul companiilor"
          >
            <table className="block w-full border-collapse text-left text-sm md:table md:min-w-[74rem] xl:min-w-0 xl:table-fixed">
              <colgroup>
                <col className="w-[4%]" />
                <col className="w-[18%]" />
                <col className="w-[14%]" />
                <col className="w-[8%]" />
                <col className="w-[7%]" />
                <col className="w-[9%]" />
                <col className="w-[14%]" />
                <col className="w-[7%]" />
                <col className="w-[19%]" />
              </colgroup>
              <thead className="hidden bg-muted/60 text-xs font-semibold text-muted-foreground md:table-header-group">
                <tr>
                  <th className="w-12 px-4 py-3">
                    <Checkbox
                      aria-label="Selectează companiile de pe pagina curentă"
                      checked={somePageSelected && !allPageSelected ? "indeterminate" : allPageSelected}
                      onCheckedChange={togglePageSelection}
                    />
                  </th>
                  <th scope="col" className="min-w-56 px-4 py-3 xl:min-w-0">Companie</th>
                  <th scope="col" className="px-4 py-3">Status</th>
                  <th scope="col" className="px-4 py-3">Etapă</th>
                  <th scope="col" className="px-4 py-3 text-right">Proiecte</th>
                  <th scope="col" className="px-4 py-3 text-right">Participanți</th>
                  <th scope="col" className="min-w-36 px-4 py-3 xl:min-w-0">Completare</th>
                  <th scope="col" className="px-4 py-3 text-right">De urmărit</th>
                  <th scope="col" className="min-w-52 px-4 py-3 xl:min-w-0">Următorul pas</th>
                </tr>
              </thead>
              <tbody className="block divide-y divide-border md:table-row-group">
                {pagedCompanies.map((company) => (
                  <CompanyTableRow
                    key={company.id}
                    company={company}
                    selected={selectedCompanyIds.includes(company.id)}
                    onToggleSelected={() => toggleCompanySelection(company.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3 text-sm">
            <p className="font-medium text-muted-foreground">
              {pageStart + 1}-{pageEnd} din {filteredCompanies.length}
            </p>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="icon-sm"
                aria-label="Pagina anterioară"
                disabled={safePageIndex === 0}
                onClick={() => setPageIndex((current) => Math.max(0, current - 1))}
              >
                <ArrowRightIcon aria-hidden="true" className="rotate-180" strokeWidth={1.8} />
              </Button>
              {paginationItems.map((item, index) =>
                typeof item === "number" ? (
                  <Button
                    key={item}
                    type="button"
                    variant={item === safePageIndex ? "default" : "ghost"}
                    size="icon-sm"
                    aria-label={`Pagina ${item + 1}`}
                    aria-current={item === safePageIndex ? "page" : undefined}
                    onClick={() => setPageIndex(item)}
                  >
                    {item + 1}
                  </Button>
                ) : (
                  <span
                    key={`${item}-${index}`}
                    className="inline-flex size-8 items-center justify-center text-muted-foreground"
                    aria-label="Pagini intermediare"
                  >
                    …
                  </span>
                ),
              )}
              <Button
                type="button"
                variant="outline"
                size="icon-sm"
                aria-label="Pagina următoare"
                disabled={safePageIndex >= pageCount - 1}
                onClick={() => setPageIndex((current) => Math.min(pageCount - 1, current + 1))}
              >
                <ArrowRightIcon aria-hidden="true" strokeWidth={1.8} />
              </Button>
              <SelectControl
                label="Companii pe pagină"
                value={pageSize}
                onChange={(event) => setPageSize(Number(event.target.value))}
                wrapperClassName="w-auto"
                className="h-9 bg-background py-1.5 text-sm"
              >
                <option value={10}>10 / pagină</option>
                <option value={25}>25 / pagină</option>
                <option value={50}>50 / pagină</option>
              </SelectControl>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function CompaniesEmptyState({
  title,
  description,
  actionLabel,
  onAction,
}: {
  title: string;
  description: string;
  actionLabel: string;
  onAction: () => void;
}) {
  return (
    <Empty className="min-h-[22rem] border bg-surface">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Building2Icon aria-hidden="true" strokeWidth={1.8} />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
        <Button type="button" onClick={onAction} className="mt-4">
          {actionLabel}
        </Button>
      </EmptyHeader>
    </Empty>
  );
}

function CompanyTableRow({
  company,
  selected,
  onToggleSelected,
}: {
  company: CompanyListItem;
  selected: boolean;
  onToggleSelected: () => void;
}) {
  const pending = Math.max(0, company.assignmentCount - company.completedCount);
  const completion = company.assignmentCount > 0
    ? Math.round((company.completedCount / company.assignmentCount) * 100)
    : 0;

  return (
    <tr
      className={cn(
        "grid grid-cols-[auto_minmax(0,1fr)_auto] gap-x-3 gap-y-3 px-4 py-4 transition-colors hover:bg-muted/35 md:table-row md:px-0 md:py-0",
        selected && "bg-primary/5",
      )}
      aria-selected={selected}
    >
      <td className="col-start-1 row-start-1 py-1 align-middle md:px-4 md:py-3">
        <Checkbox
          aria-label={`Selectează ${company.name}`}
          checked={selected}
          onCheckedChange={onToggleSelected}
        />
      </td>
      <td className="col-start-2 col-end-4 row-start-1 min-w-0 align-middle md:px-4 md:py-3">
        <Link
          href={`/trainer/companies/${company.id}`}
          className="group inline-flex min-w-0 items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45"
        >
          <EntityMark name={company.name} />
          <span className="min-w-0">
            <span className="block break-words font-semibold text-foreground group-hover:text-brand-text md:truncate">{company.name}</span>
            <span className="mt-0.5 block text-xs font-medium text-muted-foreground">{formatCompanyCode(company)}</span>
          </span>
        </Link>
      </td>
      <td className="col-start-2 col-end-4 row-start-2 align-middle md:px-4 md:py-3">
        <CompanyStatusBadge company={company} />
      </td>
      <td className="col-start-2 col-end-4 row-start-3 align-middle md:px-4 md:py-3">
        <CompanyStageInline stage={company.stage} unavailable={company.dataUnavailable} />
      </td>
      <td className="col-start-2 row-start-4 flex items-baseline gap-2 align-middle font-semibold tabular-nums text-foreground md:table-cell md:px-4 md:py-3 md:text-right">
        <span className="text-xs font-medium text-muted-foreground md:hidden">Proiecte</span>
        {company.projectCount}
      </td>
      <td className="col-start-3 row-start-4 flex items-baseline justify-self-end gap-2 align-middle font-semibold tabular-nums text-foreground md:table-cell md:px-4 md:py-3 md:text-right">
        <span className="text-xs font-medium text-muted-foreground md:hidden">Participanți</span>
        {company.participantCount}
      </td>
      <td className="col-start-2 col-end-4 row-start-5 align-middle md:px-4 md:py-3">
        <span className="mb-2 block text-xs font-medium text-muted-foreground md:hidden">Completare</span>
        {company.assignmentCount > 0 ? (
          <div className="min-w-28">
            <div className="flex items-center justify-between gap-3 text-xs">
              <span className="font-semibold tabular-nums text-foreground">{company.completedCount}/{company.assignmentCount}</span>
              <span className="tabular-nums text-muted-foreground">{completion}%</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary" style={{ width: `${completion}%` }} />
            </div>
          </div>
        ) : (
          <span className="text-xs font-medium text-muted-foreground">Nicio asignare</span>
        )}
      </td>
      <td className={cn("col-start-2 col-end-4 row-start-6 flex items-baseline justify-between gap-3 align-middle font-semibold tabular-nums md:table-cell md:px-4 md:py-3 md:text-right", pending > 0 ? "text-brand-text" : "text-muted-foreground")}>
        <span className="text-xs font-medium text-muted-foreground md:hidden">De urmărit</span>
        <span>{pending}</span>
      </td>
      <td className="col-start-2 col-end-4 row-start-7 border-t border-border pt-3 align-middle md:border-0 md:px-4 md:py-3">
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <Link
            href={`/trainer/companies/${company.id}`}
            className="inline-flex items-center gap-1.5 font-semibold text-foreground hover:text-brand-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45"
          >
            {companyNextAction(company)}
            <ArrowRightIcon aria-hidden="true" className="size-3.5 shrink-0" strokeWidth={1.8} />
          </Link>
          <Link
            href={`/trainer/companies/${company.id}/settings`}
            className="font-semibold text-muted-foreground hover:text-brand-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45"
          >
            Setări
          </Link>
        </span>
        {company.dataError ? <span className="mt-1 block text-xs text-destructive">{company.dataError}</span> : null}
      </td>
    </tr>
  );
}

function FilterSelect({
  icon: Icon,
  label,
  value,
  onChange,
  options,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<[string, string]>;
}) {
  const [allOption, ...filterOptions] = options;

  return (
    <SearchableCombobox
      icon={Icon}
      label={label}
      value={value}
      allLabel={allOption?.[1] ?? "Toate"}
      options={filterOptions.map(([optionValue, optionLabel]) => ({
        value: optionValue,
        label: optionLabel,
      }))}
      onValueChange={onChange}
    />
  );
}

function CompanyStatusBadge({ company }: { company: CompanyListItem }) {
  const status = companyStatusKey(company);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-1 text-xs font-semibold",
        status === "inactive" && "bg-muted text-muted-foreground",
        status === "attention" && "status-warning-soft",
        status === "active" && "status-success-soft",
      )}
    >
      {status === "attention" ? <AlertTriangleIcon aria-hidden="true" className="size-3.5" strokeWidth={1.8} /> : <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />}
      {companyStatusLabel(company)}
    </span>
  );
}

function CompanyStageInline({
  stage,
  unavailable,
}: {
  stage: CompanyListItem["stage"];
  unavailable?: boolean;
}) {
  if (unavailable) return <span className="text-xs font-semibold text-destructive">Date indisponibile</span>;

  return (
    <span className="inline-flex items-center gap-2 text-xs font-semibold text-muted-foreground">
      <span className={cn("size-1.5 rounded-full", stageDotClass(stage))} aria-hidden="true" />
      {stageLabel(stage)}
    </span>
  );
}

function EntityMark({ name }: { name: string }) {
  return (
    <span
      className={cn(
        "inline-flex size-9 shrink-0 items-center justify-center rounded-md text-sm font-semibold",
        entityMarkClass(name),
      )}
      aria-hidden="true"
    >
      {companyInitials(name)}
    </span>
  );
}

function companyStatusKey(company: CompanyListItem): "active" | "attention" | "inactive" {
  if (company.dataUnavailable) return "inactive";
  if (company.projectCount === 0 && company.participantCount === 0) return "inactive";
  if (company.projectCount === 0 || company.participantCount === 0) return "attention";
  if (company.assignmentCount === 0 || company.assignmentCount > company.completedCount) return "attention";
  return "active";
}

function companyStatusRank(company: CompanyListItem): number {
  const status = companyStatusKey(company);
  if (status === "attention") return 0;
  if (status === "inactive") return 1;
  return 2;
}

function companyStatusLabel(company: CompanyListItem): string {
  switch (companyStatusKey(company)) {
    case "inactive":
      return company.dataUnavailable ? "Date lipsă" : "De configurat";
    case "attention":
      return "Necesită acțiune";
    case "active":
      return "Activă";
  }
}

function companyNextAction(company: CompanyListItem): string {
  if (company.dataUnavailable) return "Verifică datele";
  if (company.projectCount === 0) return "Creează proiect";
  if (company.participantCount === 0) return "Adaugă participanți";
  if (company.assignmentCount === 0) return "Configurează asignări";
  const pending = Math.max(0, company.assignmentCount - company.completedCount);
  if (pending > 0) return `Urmărește ${pending} ${pending === 1 ? "completare" : "completări"}`;
  return company.stage === "reporting" ? "Deschide rapoartele" : "Deschide compania";
}

function matchExtraFilter(company: CompanyListItem, filter: string): boolean {
  switch (filter) {
    case "with-pending":
      return company.assignmentCount > company.completedCount;
    case "without-projects":
      return company.projectCount === 0;
    case "reporting":
      return company.stage === "reporting";
    default:
      return true;
  }
}

function stageDotClass(stage: CompanyListItem["stage"]): string {
  switch (stage) {
    case "setup":
      return "bg-muted-foreground";
    case "invites":
      return "bg-ochre";
    case "completion":
      return "bg-success";
    case "reporting":
      return "bg-primary";
  }
}

function stageLabel(stage: CompanyListItem["stage"]): string {
  switch (stage) {
    case "setup":
      return "Configurare";
    case "invites":
      return "Invitații";
    case "completion":
      return "În lucru";
    case "reporting":
      return "Raportare";
  }
}

function formatCompanyCode(company: CompanyListItem): string {
  const compact = company.id.replace(/[^a-z0-9]/gi, "").toLocaleUpperCase("ro");
  return compact ? `ID ${compact.slice(0, 8)}` : "ID local";
}

function companyInitials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "CO";
  if (words.length === 1) return words[0].slice(0, 2).toLocaleUpperCase("ro");
  return `${words[0][0] ?? ""}${words[1][0] ?? ""}`.toLocaleUpperCase("ro");
}

function entityMarkClass(seed: string): string {
  const classes = [
    "bg-primary text-primary-foreground",
    "bg-foreground text-background",
    "bg-muted-foreground text-background",
    "bg-success text-background",
    "bg-burgundy-800 text-white",
  ];
  return classes[Math.abs(hashString(seed)) % classes.length];
}

function hashString(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0;
  }
  return hash;
}

function paginationWindow(pageCount: number, currentIndex: number): Array<number | "ellipsis"> {
  if (pageCount <= 5) return Array.from({ length: pageCount }, (_, index) => index);

  const middleStart = Math.max(1, Math.min(currentIndex - 1, pageCount - 4));
  const middle = [middleStart, middleStart + 1, middleStart + 2].filter(
    (index) => index > 0 && index < pageCount - 1,
  );
  const items: Array<number | "ellipsis"> = [0];

  if (middle[0] > 1) items.push("ellipsis");
  items.push(...middle);
  if (middle[middle.length - 1] < pageCount - 2) items.push("ellipsis");
  items.push(pageCount - 1);
  return items;
}

function companyToListItem(company: CompanyIdentity): CompanyListItem {
  return {
    id: company.id,
    name: company.name,
    participantCount: 0,
    projectCount: 0,
    assignmentCount: 0,
    completedCount: 0,
    stage: "setup",
  };
}

function normalizeSearchText(value: string): string {
  return value
    .trim()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("ro");
}

function mergeCompanies(current: CompanyListItem[], incoming: CompanyListItem[]): CompanyListItem[] {
  const map = new Map(current.map((company) => [company.id, company]));
  incoming.forEach((company) => map.set(company.id, company));
  return Array.from(map.values());
}
