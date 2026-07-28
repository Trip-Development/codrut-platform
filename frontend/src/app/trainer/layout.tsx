import { canAccessWorkspace, dashboardHrefForRole, isAuthRoleMismatchError, isAuthSessionUnavailableError } from "@/api/auth";
import { getTrainerSession } from "@/api/auth-server";
import { SessionUnavailableNotice } from "@/components/auth/session-unavailable-notice";
import { trainerLoginHref } from "@/lib/auth-return";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

export default async function TrainerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const requestHeaders = await headers();
  const pathname = requestHeaders.get("x-codrut-pathname") ?? "/trainer";
  const requestedRoute = `${pathname}${requestHeaders.get("x-codrut-search") ?? ""}`;
  if (pathname === "/trainer/login") {
    return <>{children}</>;
  }

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
    redirect(trainerLoginHref(requestedRoute));
  }

  if (!session || !canAccessWorkspace(session.user, "trainer")) {
    redirect(trainerLoginHref(requestedRoute));
  }

  return <>{children}</>;
}
