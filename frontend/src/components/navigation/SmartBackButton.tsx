"use client";

import { ArrowLeftIcon } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";

export function SmartBackButton({ fallbackHref = "/" }: { fallbackHref?: string }) {
  const router = useRouter();

  function goBack() {
    if (window.history.length > 1) {
      router.back();
      return;
    }
    router.push(fallbackHref);
  }

  return (
    <Button type="button" size="lg" onClick={goBack}>
      <ArrowLeftIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
      Înapoi
    </Button>
  );
}
