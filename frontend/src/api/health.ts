import { getApiBaseUrl } from "./runtime";

export async function getHealth(): Promise<{ status: string }> {
  const response = await fetch(`${getApiBaseUrl()}/health/live`, {
    cache: "no-store",
  });

  if (!response.ok) {
    return { status: "unavailable" };
  }

  return response.json();
}
