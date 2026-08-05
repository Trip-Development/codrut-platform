"use client";

import type React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";
import type { EmailCampaign } from "@/api/email";
import { campaignStatusLabel } from "./campaign-domain";

export function IconButton({
  label,
  children,
  tone = "neutral",
  disabled,
  onClick,
}: {
  label: string;
  children: React.ReactNode;
  tone?: "neutral" | "danger" | "success";
  disabled?: boolean;
  onClick: () => void;
}) {
  const toneClass = tone === "danger"
    ? "text-foreground/45 hover:bg-destructive/8 hover:text-destructive"
    : tone === "success"
      ? "text-success-ink hover:bg-success/10 hover:text-success-ink"
      : "text-foreground/45 hover:bg-surface-muted hover:text-burgundy";
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon-sm"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className={cn("rounded-sm border-0 shadow-none disabled:opacity-45", toneClass)}
    >
      {children}
    </Button>
  );
}

export function SegmentedButton({
  active,
  className,
  children,
  ...props
}: React.ComponentProps<typeof Button> & { active: boolean }) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      aria-pressed={active}
      className={cn(
        "rounded-sm border-transparent font-bold shadow-none",
        active ? "bg-burgundy text-white hover:bg-burgundy hover:text-white" : "text-foreground/62 hover:bg-surface-muted hover:text-burgundy",
        className,
      )}
      {...props}
    >
      {children}
    </Button>
  );
}

export function CampaignStatusBadge({ status }: { status: EmailCampaign["status"] }) {
  return (
    <Badge
      variant={status === "ready" ? "default" : "outline"}
      className={cn("rounded-md text-[10px] uppercase tracking-[0.12em]", status === "ready" ? "bg-primary text-primary-foreground" : null)}
    >
      {campaignStatusLabel(status)}
    </Badge>
  );
}

export function ContactMetric({ label, value }: { label: string; value: number | undefined }) {
  return (
    <span className="inline-flex items-baseline gap-1.5 whitespace-nowrap">
      <strong className="text-xs font-semibold tabular-nums text-foreground">{value ?? 0}</strong>
      <span className="text-[10px] font-medium text-muted-foreground">{label}</span>
    </span>
  );
}
