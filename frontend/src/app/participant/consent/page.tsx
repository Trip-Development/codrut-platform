import { AuthQuotePanel } from "@/components/auth/auth-shell";
import { BrandMark } from "@/components/brand/brand-mark";
import { ConsentForm } from "./ConsentForm";

export default function ParticipantConsentPage() {
  return (
    <main className="grid min-h-[100dvh] bg-background lg:grid-cols-[1.08fr_0.92fr]">
      <AuthQuotePanel variant="activation" />
      <section className="flex items-center px-6 py-12 sm:px-10 lg:px-16">
        <div className="mx-auto w-full max-w-md">
          <BrandMark subtitle="Spațiu participant" className="mb-12 lg:hidden" />
          <h1 className="text-4xl font-semibold leading-tight tracking-normal text-foreground">
            Confirmă confidențialitatea
          </h1>
          <p className="mt-4 text-sm leading-6 text-muted-foreground">
            Acceptă termenii actuali ca să continui în proiectele tale.
          </p>
          <ConsentForm />
        </div>
      </section>
    </main>
  );
}
