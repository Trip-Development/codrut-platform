import Link from "next/link";
import { ArrowRightIcon } from "lucide-react";

import { AccountAccessLink } from "@/components/auth/account-access-link";
import { BrandMark } from "@/components/brand/brand-mark";
import { PublicSiteHeaderScrollState } from "@/components/landing/public-site-header-scroll-state";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";

const navItems = [
  { href: "/#proces", label: "Proces" },
  { href: "/#raportare", label: "Raportare" },
  { href: "/#contact", label: "Contact" },
] as const;

export function PublicSiteHeader() {
  const headerId = "public-site-header";

  return (
    <>
      <div id={`${headerId}-sentinel`} aria-hidden="true" className="pointer-events-none absolute left-0 top-0 h-px w-px opacity-0" />
      <PublicSiteHeaderScrollState headerId={headerId} />
      <header id={headerId} className="public-sticky-header sticky top-0 z-50" data-scrolled="false">
        <div className="mx-auto flex h-18 max-w-7xl items-center justify-between gap-4 px-4 md:px-6">
          <Link href="/" className="-ml-2 rounded-lg px-2 py-1 transition-colors hover:bg-muted">
            <BrandMark subtitle="Platformă de training și coaching" />
          </Link>

          <nav aria-label="Navigare principală" className="hidden items-center gap-1 lg:flex">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-lg px-3 py-2 text-sm font-semibold text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <AccountAccessLink className={serverLinkButtonClassName({ variant: "ghost", size: "sm" })}>
              Intră în cont
            </AccountAccessLink>
            <Link
              href="/#contact"
              className={serverLinkButtonClassName({ size: "sm", className: "hidden md:inline-flex" })}
            >
              Solicită demo
              <ArrowRightIcon data-icon="inline-end" />
            </Link>
          </div>
        </div>
      </header>
    </>
  );
}
