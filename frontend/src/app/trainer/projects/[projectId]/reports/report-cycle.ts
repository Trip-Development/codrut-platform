export type ProjectReportSearchParams = {
  cycle?: string;
  baseline?: string;
  compare?: string;
};

export function buildProjectReportQuery(searchParams: ProjectReportSearchParams): string {
  const params = new URLSearchParams();

  if (searchParams.cycle) params.set("cycle", searchParams.cycle);
  if (!searchParams.cycle && searchParams.baseline) params.set("baseline", searchParams.baseline);
  if (!searchParams.cycle && searchParams.compare) params.set("compare", searchParams.compare);

  const query = params.toString();
  return query ? `?${query}` : "";
}
