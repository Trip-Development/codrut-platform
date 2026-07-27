import { dashboardHrefForRole, isAuthRoleMismatchError, isAuthSessionUnavailableError } from "@/api/auth";
import { getParticipantSession } from "@/api/auth-server";
import { hasCurrentTerms } from "@/api/terms";
import { SessionUnavailableNotice } from "@/components/auth/session-unavailable-notice";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

export default async function ParticipantLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  let session: Awaited<ReturnType<typeof getParticipantSession>>;
  try {
    session = await getParticipantSession();
  } catch (error) {
    if (isAuthRoleMismatchError(error)) {
      redirect(dashboardHrefForRole(error.context.actualRole));
    }
    if (isAuthSessionUnavailableError(error)) {
      return <SessionUnavailableNotice audience="participant" />;
    }
    redirect("/login");
  }

  const pathname = (await headers()).get("x-codrut-pathname") ?? "";
  if (session.state === "authenticated") {
    if (session.user.accessMode === "secure_link") {
      redirect("/");
    }
    const currentTermsAccepted = hasCurrentTerms(session.user);
    if (!currentTermsAccepted && pathname !== "/participant/consent") {
      redirect("/participant/consent");
    }
    if (currentTermsAccepted && pathname === "/participant/consent") {
      redirect("/participant");
    }
  }

  return <>{children}</>;
}
