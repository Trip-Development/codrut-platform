"use client";

import { createContext, useContext } from "react";

/**
 * Unde e randat ce primește `AppShell` în `sidebarTop` — plicul 160.
 *
 * Același element stă de două ori: în meniul lateral (desktop, poate fi strâns) și în meniul de
 * pe telefon. Paginile de participant sunt componente de server, deci nu pot da o funcție; ce stă
 * acolo află de aici dacă meniul e strâns și dacă e copia de pe telefon.
 * În afara meniului (valoarea implicită) totul arată ca înainte.
 */
export type SidebarState = {
  inSidebar: boolean;
  collapsed: boolean;
  mobile: boolean;
};

const IN_AFARA_MENIULUI: SidebarState = { inSidebar: false, collapsed: false, mobile: false };

export const SidebarStateContext = createContext<SidebarState>(IN_AFARA_MENIULUI);

export function useSidebarState(): SidebarState {
  return useContext(SidebarStateContext);
}
