import "server-only";

import { cookies } from "next/headers";

export async function getServerApiRequestOptions(): Promise<Pick<RequestInit, "headers">> {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get("codrut_session");

  if (!sessionCookie?.value) {
    return {};
  }

  return {
    headers: {
      Cookie: `codrut_session=${sessionCookie.value}`,
    },
  };
}
