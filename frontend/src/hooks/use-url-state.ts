"use client";

import { useCallback, useEffect, useMemo, useRef, useTransition } from "react";
import { usePathname, useSearchParams } from "next/navigation";

type UrlStateMode = "push" | "replace";

export function useUrlState() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const [isPending, startTransition] = useTransition();
  const desiredLocationRef = useRef({ pathname, searchKey });

  useEffect(() => {
    desiredLocationRef.current = { pathname, searchKey };
  }, [pathname, searchKey]);

  const params = useMemo(() => new URLSearchParams(searchKey), [searchKey]);

  const setParams = useCallback(
    (
      updates: Record<string, string | number | null | undefined>,
      mode: UrlStateMode = "push",
    ) => {
      const desiredLocation = desiredLocationRef.current;
      const baseSearchKey =
        desiredLocation.pathname === pathname ? desiredLocation.searchKey : searchKey;
      const nextParams = new URLSearchParams(baseSearchKey);
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
      const currentHref = baseSearchKey ? `${pathname}?${baseSearchKey}` : pathname;
      if (href === currentHref) return;

      desiredLocationRef.current = { pathname, searchKey: query };

      startTransition(() => {
        if (mode === "replace") {
          window.history.replaceState(null, "", href);
        } else {
          window.history.pushState(null, "", href);
        }
      });
    },
    [pathname, searchKey, startTransition],
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
