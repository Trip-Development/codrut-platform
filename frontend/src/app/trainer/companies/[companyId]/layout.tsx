import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

export default async function CompanyDetailLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ companyId: string }>;
}) {
  await params;

  return (
    <AppShell
      audience="trainer"
      eyebrow="Companie"
      title="Spațiu companie"
      description="Proiecte active, participanți și setări administrative."
      navItems={trainerNavItems}
      activeHref="/trainer/companies"
    >
      {children}
    </AppShell>
  );
}
