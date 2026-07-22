import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSeparator,
  FieldSet,
  FieldTitle,
} from "./field";

afterEach(cleanup);

describe("field primitives", () => {
  it("composes semantic field structures and orientation variants", () => {
    render(
      <FieldSet>
        <FieldLegend variant="label">Date contact</FieldLegend>
        <FieldGroup>
          <Field orientation="horizontal" data-testid="horizontal-field">
            <FieldLabel htmlFor="email">Email</FieldLabel>
            <FieldContent>
              <input id="email" />
              <FieldDescription>Adresa folosită pentru invitație.</FieldDescription>
            </FieldContent>
          </Field>
          <Field orientation="responsive" data-testid="responsive-field">
            <FieldTitle>Status</FieldTitle>
          </Field>
        </FieldGroup>
      </FieldSet>,
    );

    expect(screen.getByText("Date contact").getAttribute("data-variant")).toBe("label");
    expect(screen.getByTestId("horizontal-field").getAttribute("data-orientation")).toBe("horizontal");
    expect(screen.getByTestId("responsive-field").getAttribute("data-orientation")).toBe("responsive");
    expect(screen.getByLabelText("Email")).toBeTruthy();
  });

  it("renders separators with and without content", () => {
    const { container, rerender } = render(<FieldSeparator>Alternativ</FieldSeparator>);
    expect(screen.getByText("Alternativ")).toBeTruthy();
    expect(container.firstElementChild?.getAttribute("data-content")).toBe("true");

    rerender(<FieldSeparator />);
    expect(screen.queryByText("Alternativ")).toBeNull();
    expect(container.firstElementChild?.getAttribute("data-content")).toBe("false");
  });

  it("deduplicates validation errors and omits empty error surfaces", () => {
    const { rerender } = render(<FieldError errors={[]} />);
    expect(screen.queryByRole("alert")).toBeNull();

    rerender(<FieldError errors={[{ message: "Email invalid" }, { message: "Email invalid" }]} />);
    expect(screen.getByRole("alert").textContent).toBe("Email invalid");

    rerender(<FieldError errors={[{ message: "Email invalid" }, undefined, { message: "Câmp obligatoriu" }]} />);
    const alert = screen.getByRole("alert");
    expect(alert.querySelectorAll("li")).toHaveLength(2);
    expect(alert.textContent).toContain("Email invalid");
    expect(alert.textContent).toContain("Câmp obligatoriu");

    rerender(<FieldError>Mesaj direct</FieldError>);
    expect(screen.getByRole("alert").textContent).toBe("Mesaj direct");
  });
});
