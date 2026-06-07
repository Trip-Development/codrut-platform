import { getParticipantSession } from "@/api/auth-server";
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
  } catch {
    redirect("/login");
  }

  return <>{children}</>;
}
