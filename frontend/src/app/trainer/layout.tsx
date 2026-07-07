import { isAuthSessionUnavailableError } from "@/api/auth";
import { getTrainerSession } from "@/api/auth-server";
import { SessionUnavailableNotice } from "@/components/auth/session-unavailable-notice";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

export default async function TrainerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const requestHeaders = await headers();
  if (requestHeaders.get("x-codrut-pathname") === "/trainer/login") {
    return <>{children}</>;
  }

  try {
    const session = await getTrainerSession();
    if (!session || session.user.role !== "trainer") {
      redirect("/login");
    }
  } catch (error) {
    if (isAuthSessionUnavailableError(error)) {
      return <SessionUnavailableNotice audience="trainer" />;
    }
    redirect("/login");
  }

  return <>{children}</>;
}
