import { BrandMark } from "@/components/brand/brand-mark";
import { OperationFeedback } from "@/components/presentation/operation-feedback";

export default function InviteLoading() {
  return (
    <main className="flex min-h-[100dvh] items-center justify-center bg-background px-4 py-10 text-foreground md:px-6">
      <section className="w-full max-w-md rounded-lg border bg-surface p-6 shadow-sm md:p-8">
        <BrandMark size="lg" showText={false} className="mx-auto" />
        <OperationFeedback
          className="mt-8"
          title="Verificăm invitația"
          detail="Confirmăm accesul și sarcinile disponibile."
          meta="în verificare"
        />
      </section>
    </main>
  );
}
