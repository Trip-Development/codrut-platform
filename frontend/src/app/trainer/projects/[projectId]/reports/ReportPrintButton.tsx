"use client";

import { PrinterIcon } from "lucide-react";

import { Button } from "@/components/ui/button";

export function ReportPrintButton() {
  return (
    <Button type="button" variant="outline" size="sm" onClick={() => window.print()}>
      <PrinterIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
      Tipărește
    </Button>
  );
}
