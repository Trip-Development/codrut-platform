import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { clearAppShellIdentityCache } from "./app-shell";
import { ParticipantRouteError } from "./route-error";
import { ParticipantRouteLoading } from "./route-loading";

/**
 * Plicul 116, partea A.
 *
 * Ecranele de încărcare și de eroare arătau meniul de TRAINING cât timp tipul proiectului nu se
 * știe încă. Raționamentul scris acolo era corect până la plicul 113: meniul de training era o
 * submulțime a celuilalt. De la 113 nu mai e — are „Tablou Competențe" și „Exersează (Cody)", pe
 * care celălalt nu le mai are.
 *
 * Deci, în clipele dinaintea primei pagini, un om dintr-un proiect care NU e de training vedea
 * tabul Cody. Mai bine lipsește o clipă un tab decât să apară unuia care n-are ce căuta acolo.
 */

afterEach(() => {
  cleanup();
  clearAppShellIdentityCache();
});

const EXERSAREA = /Exersează \(Cody\)/;
const TABLOUL = /Tablou Competențe/;

describe("meniul cât timp tipul proiectului nu se știe", () => {
  it("la încărcare, fără tip, nu arată exersarea și tabloul", () => {
    render(
      <ParticipantRouteLoading title="Chestionare" activeHref="/participant" kind="home" />,
    );

    expect(screen.queryAllByText(EXERSAREA)).toHaveLength(0);
    expect(screen.queryAllByText(TABLOUL)).toHaveLength(0);
  });

  it("la încărcare, cu tipul training, le arată", () => {
    render(
      <ParticipantRouteLoading
        title="Exersează"
        activeHref="/participant/practice"
        kind="home"
        projectType="training"
      />,
    );

    expect(screen.queryAllByText(EXERSAREA).length).toBeGreaterThan(0);
    expect(screen.queryAllByText(TABLOUL).length).toBeGreaterThan(0);
  });

  const eroare = { name: "Error", message: "ceva n-a mers" } as Error;

  it("la eroare, fără tip, nu arată exersarea și tabloul", () => {
    render(<ParticipantRouteError error={eroare} reset={() => {}} />);

    expect(screen.queryAllByText(EXERSAREA)).toHaveLength(0);
    expect(screen.queryAllByText(TABLOUL)).toHaveLength(0);
  });

  it("la eroare, cu tipul training, le arată", () => {
    render(<ParticipantRouteError error={eroare} reset={() => {}} projectType="training" />);

    expect(screen.queryAllByText(EXERSAREA).length).toBeGreaterThan(0);
    expect(screen.queryAllByText(TABLOUL).length).toBeGreaterThan(0);
  });
});
