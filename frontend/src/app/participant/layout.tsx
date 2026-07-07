import { isAuthSessionUnavailableError } from "@/api/auth";
import { getParticipantSession } from "@/api/auth-server";
import { SessionUnavailableNotice } from "@/components/auth/session-unavailable-notice";
import { redirect } from "next/navigation";

export default async function ParticipantLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  try {
    const session = await getParticipantSession();
    if (!session) {
      redirect("/login");
    }
  } catch (error) {
    if (isAuthSessionUnavailableError(error)) {
      return <SessionUnavailableNotice audience="participant" />;
    }
    redirect("/login");
  }

  return <>{children}</>;
}
