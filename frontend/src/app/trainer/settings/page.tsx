import Link from "next/link";

import { audienceAccessNote } from "@/api/auth";
import { getTrainerSession } from "@/api/auth-server";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

export default async function TrainerSettingsPage() {
  const trainer = await getTrainerSession();

  return (
    <AppShell
      audience="trainer"
      eyebrow="Setări"
      title="Cont și preferințe"
      description="Setări utile pentru owner/trainer: identitate, notificări, vizibilitate rapoarte și preferințe de lucru."
      navItems={trainerNavItems}
      activeHref="/trainer/settings"
      userLabel={trainer.user.name}
      session={trainer}
      accessNote={audienceAccessNote("trainer")}
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Profil</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">Cont trainer</h2>
          <div className="mt-5 grid gap-3 md:grid-cols-2">
            <SettingRow label="Nume afișat" value={trainer.user.name} />
            <SettingRow label="Rol" value="Trainer / owner" />
            <SettingRow label="Sesiune" value={trainer.state === "authenticated" ? "Autentificat" : "Acces temporar"} />
            <SettingRow label="Spațiu implicit" value="Companii" />
          </div>
        </section>

        <aside className="space-y-4">
          <SettingsLink
            href="/trainer/companies"
            label="Companii"
            detail="Adaugă clienți, apoi gestionează participanți, echipe, invitații și rapoarte per companie."
          />
          <SettingsLink
            href="/trainer/email"
            label="Șabloane email"
            detail="Editează textele reutilizabile. Livrarea invitațiilor se urmărește din spațiul companiei."
          />
        </aside>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <SettingsPanel
          title="Preferințe interfață"
          items={[
            "Tema aleasă rămâne salvată între pagini.",
            "Navigarea principală pornește din Companii.",
            "Lista de participanți este tratată ca acțiune în contextul companiei.",
          ]}
        />
        <SettingsPanel
          title="Vizibilitate rapoarte"
          items={[
            "Trainerul poate lucra cu răspunsuri detaliate pentru analiză.",
            "Managerii evaluați nu văd răspunsuri individuale.",
            "Rapoartele pentru clienți trebuie livrate agregat sau validate înainte de expunere.",
          ]}
        />
        <SettingsPanel
          title="Notificări"
          items={[
            "Emailurile operaționale se gestionează din tabul Invitații al companiei.",
            "Pentru pilot, notificările reale trebuie verificate întâi în mediu de test, apoi trimise prin furnizorul de email.",
            "Notificările Telegram/Calendly rămân integrare separată.",
          ]}
        />
      </div>
    </AppShell>
  );
}

function SettingRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-background px-4 py-3">
      <p className="text-xs font-bold uppercase tracking-wider text-foreground/45">{label}</p>
      <p className="mt-1 text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

function SettingsLink({ href, label, detail }: { href: string; label: string; detail: string }) {
  return (
    <Link
      href={href}
      className="tap-soft block rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm hover:border-burgundy/45"
    >
      <p className="text-sm font-bold text-foreground">{label}</p>
      <p className="mt-2 text-sm leading-6 text-foreground/58">{detail}</p>
    </Link>
  );
}

function SettingsPanel({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <h2 className="text-base font-semibold text-foreground">{title}</h2>
      <div className="mt-4 space-y-2">
        {items.map((item) => (
          <p key={item} className="rounded-xl bg-surface-muted px-3 py-2 text-sm leading-6 text-foreground/62">
            {item}
          </p>
        ))}
      </div>
    </section>
  );
}
