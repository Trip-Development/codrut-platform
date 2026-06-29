export function safeReturnHref(
  value: string | undefined,
  fallback: string,
  options: { secureInvite?: boolean } = {},
): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return fallback;
  }

  if (options.secureInvite && !/^\/invite\/[^/?#]+$/.test(value) && value !== "/participant/questionnaires") {
    return fallback;
  }

  return value;
}
