export type ProjectReportSearchParams = {
  baseline?: string;
  compare?: string;
  cycle?: string;
};

export function buildProjectReportQuery(searchParams: ProjectReportSearchParams): string {
  const params = new URLSearchParams();

  if (searchParams.cycle) params.set("cycle", searchParams.cycle);
  if (searchParams.baseline) params.set("baseline", searchParams.baseline);
  if (searchParams.compare) params.set("compare", searchParams.compare);

  const query = params.toString();
  return query ? `?${query}` : "";
}

export async function loadOptionalComparison<T>(
  load: (() => Promise<T>) | null,
): Promise<{ comparison: T | null; failed: boolean }> {
  if (!load) return { comparison: null, failed: false };

  try {
    return { comparison: await load(), failed: false };
  } catch {
    return { comparison: null, failed: true };
  }
}
