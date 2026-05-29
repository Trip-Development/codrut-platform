import { API_BASE_URL } from "./runtime";

export async function getHealth(): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE_URL}/health/live`, {
    cache: "no-store",
  });

  if (!response.ok) {
    return { status: "unavailable" };
  }

  return response.json();
}
