import { canAccessWorkspace, dashboardHrefForRole, isAuthRoleMismatchError, isAuthSessionUnavailableError } from "@/api/auth";
import { getTrainerSession } from "@/api/auth-server";
import { SessionUnavailableNotice } from "@/components/auth/session-unavailable-notice";
import { safeTrainerReturnTo, trainerLoginHref } from "@/lib/auth-return";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

export default async function TrainerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const requestHeaders = await headers();
  const pathname = requestHeaders.get("x-codrut-pathname") ?? "/trainer";
  const search = requestHeaders.get("x-codrut-search") ?? "";
  const requestedRoute = `${pathname}${search}`;
  const loginReturnTo = safeTrainerReturnTo(
    new URLSearchParams(search.startsWith("?") ? search.slice(1) : search).get("returnTo"),
  );

  let session: Awaited<ReturnType<typeof getTrainerSession>>;
  try {
    session = await getTrainerSession();
  } catch (error) {
    if (isAuthRoleMismatchError(error)) {
      redirect(dashboardHrefForRole(error.context.actualRole));
    }
    if (isAuthSessionUnavailableError(error)) {
      return <SessionUnavailableNotice audience="trainer" />;
    }
    if (pathname === "/trainer/login") {
      return <>{children}</>;
    }
    redirect(trainerLoginHref(requestedRoute));
  }

  if (!session || !canAccessWorkspace(session.user, "trainer")) {
    if (pathname === "/trainer/login") {
      return <>{children}</>;
    }
    redirect(trainerLoginHref(requestedRoute));
  }
  if (pathname === "/trainer/login") {
    redirect(loginReturnTo);
  }

  return <>{children}</>;
}
