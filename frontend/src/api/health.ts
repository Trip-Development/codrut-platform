import { generatedApiFetch, type ApiHealth } from "./generated/client";

export async function getHealth(): Promise<ApiHealth> {
  const response = await generatedApiFetch("/api/health/live", {
    cache: "no-store",
  });

  if (!response.ok) {
    return { status: "unavailable" };
  }

  return response.json() as Promise<ApiHealth>;
}
