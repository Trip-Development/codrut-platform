export type ProjectReportSearchParams = {
  cycle?: string;
};

export function buildProjectReportQuery(searchParams: ProjectReportSearchParams): string {
  const params = new URLSearchParams();

  if (searchParams.cycle) params.set("cycle", searchParams.cycle);

  const query = params.toString();
  return query ? `?${query}` : "";
}
