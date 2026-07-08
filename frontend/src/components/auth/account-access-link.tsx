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

export function AccountAccessLink({
  className,
  children = "Intră în cont",
  authenticatedLabel = "Continuă în cont",
}: AccountAccessLinkProps) {
  const [href, setHref] = useState<"/login" | "/trainer" | "/participant">("/login");
  const [label, setLabel] = useState<ReactNode>(children);

  useEffect(() => {
    let cancelled = false;
    void getAuthenticatedSession().then((session) => {
      if (cancelled || !session) return;
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
