"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import { dashboardHrefForRole, getAuthenticatedSession } from "@/api/auth";

type AccountAccessLinkProps = {
  className?: string;
  children?: ReactNode;
  authenticatedLabel?: ReactNode;
};

type AccountAccessSession = Awaited<ReturnType<typeof getAuthenticatedSession>>;

let accountAccessSessionPromise: Promise<AccountAccessSession> | null = null;

function getAccountAccessSession(): Promise<AccountAccessSession> {
  accountAccessSessionPromise ??= getAuthenticatedSession().finally(() => {
    accountAccessSessionPromise = null;
  });
  return accountAccessSessionPromise;
}

export function AccountAccessLink({
  className,
  children = "Intră în cont",
  authenticatedLabel = "Continuă în cont",
}: AccountAccessLinkProps) {
  const [href, setHref] = useState<"/login" | "/trainer" | "/participant">("/login");
  const [label, setLabel] = useState<ReactNode>(children);

  useEffect(() => {
    let cancelled = false;
    void getAccountAccessSession().then((session) => {
      if (cancelled || !session || session.user.accessMode === "secure_link") return;
      setHref(dashboardHrefForRole(session.user.role));
      setLabel(authenticatedLabel);
    });
    return () => {
      cancelled = true;
    };
  }, [authenticatedLabel]);

  return (
    <Link href={href} className={className}>
      {label}
    </Link>
  );
}
