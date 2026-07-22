import "server-only";

import { cookies, headers } from "next/headers";

import {
  isLocalAuthBypassEnabled,
  LOCAL_AUTH_ROLE_HEADER,
  localAuthRoleForPathname,
  type LocalAuthRole,
} from "./runtime";

export async function getServerApiRequestOptions(
  expectedRole?: LocalAuthRole,
): Promise<Pick<RequestInit, "headers">> {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get("codrut_session");
  const requestHeaders = await headers();
  const requestHost = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host") ?? "";
  const localRole = isLocalAuthBypassEnabled(requestHost)
    ? expectedRole ?? localAuthRoleForPathname(requestHeaders.get("x-codrut-pathname") ?? "")
    : null;

  if (!sessionCookie?.value && !localRole) {
    return {};
  }

  const apiHeaders = new Headers();
  if (sessionCookie?.value) {
    apiHeaders.set("Cookie", `codrut_session=${sessionCookie.value}`);
  }
  if (localRole) {
    apiHeaders.set(LOCAL_AUTH_ROLE_HEADER, localRole);
  }

  return {
    headers: apiHeaders,
  };
}
