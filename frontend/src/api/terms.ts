import type { CurrentUser } from "./auth";

export const CURRENT_TERMS_VERSION = "privacy-2026-07-16";

export function hasCurrentTerms(user: CurrentUser): boolean {
  return user.consentCurrent === true || Boolean(
    user.termsAcceptedAt && user.termsVersion === CURRENT_TERMS_VERSION,
  );
}
