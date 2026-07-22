"use client";

import { useEffect } from "react";

type PublicSiteHeaderScrollStateProps = {
  headerId: string;
};

export function PublicSiteHeaderScrollState({ headerId }: PublicSiteHeaderScrollStateProps) {
  useEffect(() => {
    const header = document.getElementById(headerId);
    const sentinel = document.getElementById(`${headerId}-sentinel`);

    if (!header || !sentinel) {
      return undefined;
    }

    const setScrolled = (isScrolled: boolean) => {
      header.dataset.scrolled = isScrolled ? "true" : "false";
    };
    const observer = new IntersectionObserver(
      ([entry]) => {
        setScrolled(!entry.isIntersecting);
      },
      { threshold: 1 },
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [headerId]);

  return null;
}
