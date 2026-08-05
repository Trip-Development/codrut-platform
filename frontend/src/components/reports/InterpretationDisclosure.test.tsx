import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { InterpretationDisclosure } from "./InterpretationDisclosure";

describe("InterpretationDisclosure", () => {
  afterEach(cleanup);

  it("formats structured guidance into readable sections and bullet lists", () => {
    render(
      <InterpretationDisclosure>
        {`Pe scurt
• Primul indiciu
• Al doilea indiciu

Factori de presiune
• Presiune ridicată

Comportament sub stres
Reacție observabilă.

Permisiuni utile
• Este în regulă să ceri ajutor.`}
      </InterpretationDisclosure>,
    );

    fireEvent.click(screen.getByText("Vezi interpretarea completă"));

    expect(screen.getByRole("heading", { name: "Pe scurt", level: 5 })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Factori de presiune", level: 5 })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Comportament sub stres", level: 5 })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Permisiuni utile", level: 5 })).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
  });

  it("keeps unstructured interpretations available without inventing sections", () => {
    render(<InterpretationDisclosure>Interpretare existentă.</InterpretationDisclosure>);

    fireEvent.click(screen.getByText("Vezi interpretarea completă"));

    expect(screen.getByText("Interpretare existentă.")).toBeTruthy();
    expect(screen.queryByRole("heading", { level: 5 })).toBeNull();
  });
});
