import { getTrainerSession } from "@/api/auth";
import { redirect } from "next/navigation";

export default async function TrainerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  try {
    const session = await getTrainerSession();
    if (!session || session.user.role !== "trainer") {
      redirect("/login");
    }
  } catch {
    redirect("/login");
  }

  return <>{children}</>;
}
