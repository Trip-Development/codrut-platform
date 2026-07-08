import { getApiBaseUrl } from "../runtime";
import type { paths } from "./schema";

export type { components, operations, paths } from "./schema";

export type GeneratedApiPath = keyof paths & string;

export type ApiHealth =
  paths["/api/health/live"]["get"]["responses"][200]["content"]["application/json"];

const GENERATED_API_PREFIX = "/api";

function normalizeGeneratedPath(path: GeneratedApiPath): string {
  if (!path.startsWith("/")) {
    throw new Error("Generated API paths must start with '/'.");
  }

  if (path.startsWith(`${GENERATED_API_PREFIX}/`)) {
    return path.slice(GENERATED_API_PREFIX.length);
  }

  return path;
}

export function generatedApiUrl(path: GeneratedApiPath): string {
  const baseUrl = getApiBaseUrl().replace(/\/+$/, "");
  return `${baseUrl}${normalizeGeneratedPath(path)}`;
}

export function generatedApiFetch(
  path: GeneratedApiPath,
  init?: RequestInit,
): Promise<Response> {
  return fetch(generatedApiUrl(path), init);
}
