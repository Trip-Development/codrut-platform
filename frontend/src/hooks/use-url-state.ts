"use client";

import { useCallback, useMemo, useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

type UrlStateMode = "push" | "replace";

export function useUrlState() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const [isPending, startTransition] = useTransition();

  const params = useMemo(() => new URLSearchParams(searchKey), [searchKey]);

  const setParams = useCallback(
    (
      updates: Record<string, string | number | null | undefined>,
      mode: UrlStateMode = "push",
    ) => {
      const nextParams = new URLSearchParams(searchKey);
      Object.entries(updates).forEach(([key, value]) => {
        const normalized = value === null || value === undefined ? "" : String(value);
        if (normalized) {
          nextParams.set(key, normalized);
        } else {
          nextParams.delete(key);
        }
      });

      const query = nextParams.toString();
      const href = query ? `${pathname}?${query}` : pathname;
      const currentHref = searchKey ? `${pathname}?${searchKey}` : pathname;
      if (href === currentHref) return;

      startTransition(() => {
        if (mode === "replace") {
          router.replace(href, { scroll: false });
        } else {
          router.push(href, { scroll: false });
        }
      });
    },
    [pathname, router, searchKey, startTransition],
  );
  const get = useCallback((key: string) => params.get(key), [params]);
  const setParam = useCallback(
    (key: string, value: string | number | null | undefined, mode?: UrlStateMode) =>
      setParams({ [key]: value }, mode),
    [setParams],
  );

  return {
    get,
    params,
    searchKey,
    isPending,
    setParams,
    setParam,
  };
}
