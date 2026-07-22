"use client";

import type React from "react";

import { ModalLayer } from "@/components/ui/modal-layer";
import { cn } from "@/utils/cn";

type SheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  labelledBy: string;
  describedBy?: string;
  children: React.ReactNode;
  closeOnBackdrop?: boolean;
  closeOnEscape?: boolean;
  className?: string;
  panelClassName?: string;
};

function Sheet({
  open,
  onOpenChange,
  labelledBy,
  describedBy,
  children,
  closeOnBackdrop = true,
  closeOnEscape = true,
  className,
  panelClassName,
}: SheetProps) {
  if (!open) return null;

  return (
    <ModalLayer
      labelledBy={labelledBy}
      describedBy={describedBy}
      onClose={() => onOpenChange(false)}
      closeOnBackdrop={closeOnBackdrop}
      closeOnEscape={closeOnEscape}
      className={cn(
        "!items-stretch !justify-end !overflow-hidden !p-0 !backdrop-blur-none",
        className,
      )}
      panelClassName={cn(
        "!h-dvh !max-h-dvh !w-full !max-w-[32rem] !overflow-hidden !rounded-none !border-y-0 !border-r-0 !p-0",
        panelClassName,
      )}
    >
      {children}
    </ModalLayer>
  );
}

function SheetHeader({ className, ...props }: React.ComponentProps<"header">) {
  return (
    <header
      data-slot="sheet-header"
      className={cn("shrink-0 border-b border-border px-5 py-4 sm:px-6", className)}
      {...props}
    />
  );
}

function SheetBody({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-body"
      className={cn("min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6", className)}
      {...props}
    />
  );
}

function SheetFooter({ className, ...props }: React.ComponentProps<"footer">) {
  return (
    <footer
      data-slot="sheet-footer"
      className={cn("shrink-0 border-t border-border bg-surface px-5 py-4 sm:px-6", className)}
      {...props}
    />
  );
}

export { Sheet, SheetBody, SheetFooter, SheetHeader };
