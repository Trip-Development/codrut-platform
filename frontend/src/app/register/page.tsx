"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BrandMark } from "@/components/brand/brand-mark";
import { isDemoFallbackEnabled } from "@/api/runtime";

const generateNickname = (name: string) => {
  if (!name) return "";
  return name
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // remove Romanian diacritics
    .replace(/[^a-z0-9]/g, "_")      // replace non-alphanumeric with underscore
    .replace(/_+/g, "_")             // remove duplicate underscores
    .replace(/^_+|_+$/g, "");        // trim leading/trailing underscores
};

const TERMS_VERSION = "privacy-2026-06-12";

export default function RegisterPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [nickname, setNickname] = useState("");
  const [isNicknameCustom, setIsNicknameCustom] = useState(false);
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    // Retrieve invitation data from sessionStorage
    const storedInvite = sessionStorage.getItem("codrut_invite");
    let inviteData = null;
    if (storedInvite) {
      try {
        inviteData = JSON.parse(storedInvite);
      } catch {
        // ignore
      }
    }

    // Fallback/demo invite if not found, only for intentional demo browsing.
    if (!inviteData) {
      if (!isDemoFallbackEnabled()) {
        setError("Invitația lipsește sau nu mai este activă. Folosește linkul primit pe email.");
        setLoading(false);
        return;
      }

      inviteData = {
        email: "lider.demo@companie.ro",
        token: "demo-token",
        fullName: "Lider Demo",
        isLeadership: true,
      };
      sessionStorage.setItem("codrut_invite", JSON.stringify(inviteData));
    }

    setEmail(inviteData.email || "lider.demo@companie.ro");
    setFullName(inviteData.fullName || "");
    setNickname(generateNickname(inviteData.fullName || ""));
    setToken(inviteData.token || "demo-token");
    setLoading(false);
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password.length < 12) {
      setError("Parola trebuie să aibă cel puțin 12 caractere.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Parolele introduse nu coincid.");
      return;
    }

    if (!termsAccepted) {
      setError("Trebuie să accepți termenii de confidențialitate înainte de înregistrare.");
      return;
    }

    setSubmitting(true);

    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          password,
          token,
          terms_accepted: termsAccepted,
          terms_version: TERMS_VERSION,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        if (isDemoFallbackEnabled() && token === "demo-token") {
          console.warn("Bypassing API registration error for demo-token in prototype mode.");
          sessionStorage.removeItem("codrut_invite");
          router.push("/participant");
          return;
        }
        throw new Error(data.error?.message || "Înregistrarea a eșuat. Reîncearcă.");
      }

      // Registration successful, remove invite session and redirect to dashboard
      sessionStorage.removeItem("codrut_invite");
      router.push("/participant");
    } catch (err) {
      if (isDemoFallbackEnabled() && token === "demo-token") {
        console.warn("Bypassing registration error for demo-token in prototype mode:", err);
        sessionStorage.removeItem("codrut_invite");
        router.push("/participant");
        return;
      }
      const msg = err instanceof Error ? err.message : "A apărut o eroare la înregistrare.";
      setError(msg);
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <main className="bg-vines-pattern app-min-height flex items-center justify-center bg-background px-4 py-10">
        <section className="w-full max-w-md rounded-[2.5rem] border border-[var(--border)] bg-surface p-10 text-center shadow-brand">
          <BrandMark size="lg" showText={false} className="mx-auto" />
          <div className="mt-8 flex justify-center">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-burgundy border-t-transparent"></div>
          </div>
          <p className="mt-6 text-foreground/60 font-semibold text-sm">Se încarcă datele invitației...</p>
        </section>
      </main>
    );
  }

  return (
    <main className="bg-vines-pattern app-min-height flex items-center justify-center bg-background px-4 py-10">
      <section className="shadow-brand w-full max-w-md rounded-[2.5rem] border border-[var(--border)] bg-surface p-8 md:p-10 transition-all duration-150">
        <div className="mb-8 flex flex-col items-center">
          <BrandMark size="lg" showText={false} />
          <h1 className="font-display mt-6 text-center text-3xl font-bold tracking-tight text-foreground md:text-4xl">
            Înregistrare cont
          </h1>
          <p className="mt-2 text-center text-sm leading-6 text-foreground/60">
            Setează numele și parola pentru acces permanent la platformă.
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-600 dark:border-red-900/30 dark:bg-red-950/20 dark:text-red-400">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <div className="flex justify-between items-center mb-1.5">
              <label className="block text-xs font-bold uppercase tracking-wider text-foreground/75">
                Email securizat
              </label>
              <span className="flex items-center gap-1 text-[11px] font-bold text-burgundy bg-burgundy/5 px-2 py-0.5 rounded-full border border-burgundy/10">
                <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                </svg>
                Asociat invitației
              </span>
            </div>
            <input
              className="w-full rounded-2xl border border-[var(--border)] bg-surface-muted/62 px-4 py-3.5 text-base text-foreground/45 cursor-not-allowed outline-none select-none"
              type="email"
              value={email}
              disabled={true}
              title="Adresa de email este blocată la cea specificată în invitație."
            />
            <p className="mt-1.5 text-[11px] text-foreground/45 italic">
              * Emailul este blocat pentru a păstra continuitatea profilului tău.
            </p>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-foreground/75 mb-1.5">
              Nume complet
            </label>
            <input
              className="w-full rounded-2xl border border-[var(--border)] bg-surface-muted px-4 py-3.5 text-base text-foreground placeholder-foreground/35 outline-none transition-all duration-200 focus:border-burgundy focus:ring-1 focus:ring-burgundy"
              type="text"
              placeholder="Numele tău complet"
              value={fullName}
              onChange={(e) => {
                setFullName(e.target.value);
                if (!isNicknameCustom) {
                  setNickname(generateNickname(e.target.value));
                }
              }}
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-foreground/75 mb-1.5">
              Nume utilizator (Nickname)
            </label>
            <div className="relative flex items-center">
              <span className="absolute left-4 text-foreground/40 font-bold select-none">@</span>
              <input
                className="w-full rounded-2xl border border-[var(--border)] bg-surface-muted pl-8 pr-4 py-3.5 text-base text-foreground placeholder-foreground/35 outline-none transition-all duration-200 focus:border-burgundy focus:ring-1 focus:ring-burgundy"
                type="text"
                placeholder="nickname_ul_tau"
                value={nickname}
                onChange={(e) => {
                  setNickname(generateNickname(e.target.value));
                  setIsNicknameCustom(true);
                }}
                required
              />
            </div>
            <p className="mt-1.5 text-[11px] text-foreground/45 italic">
              Nume de utilizator generat automat. Îl poți edita.
            </p>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-foreground/75 mb-1.5">
              Parolă
            </label>
            <input
              className="w-full rounded-2xl border border-[var(--border)] bg-surface-muted px-4 py-3.5 text-base text-foreground placeholder-foreground/35 outline-none transition-all duration-200 focus:border-burgundy focus:ring-1 focus:ring-burgundy"
              type="password"
              placeholder="Minim 12 caractere"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-foreground/75 mb-1.5">
              Confirmă parola
            </label>
            <input
              className="w-full rounded-2xl border border-[var(--border)] bg-surface-muted px-4 py-3.5 text-base text-foreground placeholder-foreground/35 outline-none transition-all duration-200 focus:border-burgundy focus:ring-1 focus:ring-burgundy"
              type="password"
              placeholder="Reintroduce parola"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>

          <label className="flex gap-3 rounded-2xl border border-[var(--border)] bg-surface-muted/70 p-4 text-left">
            <input
              type="checkbox"
              checked={termsAccepted}
              onChange={(event) => setTermsAccepted(event.target.checked)}
              className="mt-1 h-4 w-4 rounded border-[var(--border)] accent-burgundy"
            />
            <span className="text-xs font-semibold leading-5 text-foreground/65">
              Confirm că am citit și accept regulile de confidențialitate și prelucrare a datelor pentru utilizarea
              platformei Codruț.
            </span>
          </label>

          <button
            type="submit"
            disabled={submitting || !termsAccepted}
            className="tap-soft mt-2.5 w-full rounded-2xl bg-burgundy hover:bg-burgundy-dark disabled:bg-burgundy/50 px-4 py-4 font-semibold text-white transition-colors duration-200 shadow-md flex items-center justify-center gap-2"
          >
            {submitting ? (
              <>
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
                Se creează contul...
              </>
            ) : (
              "Finalizează înregistrarea"
            )}
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-[var(--border)] flex justify-center text-sm">
          <span className="text-foreground/50">Ai deja cont?</span>
          <Link
            href="/login"
            className="ml-2 font-bold text-burgundy hover:text-burgundy-dark transition-colors"
          >
            Intră în cont
          </Link>
        </div>
      </section>
    </main>
  );
}
