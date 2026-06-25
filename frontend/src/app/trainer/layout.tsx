import { getTrainerSession } from "@/api/auth-server";
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
  } catch {
    redirect("/login");
  }

  return <>{children}</>;
}
