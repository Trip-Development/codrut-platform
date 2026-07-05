import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React, { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { ModalLayer } from "./modal-layer";

afterEach(() => {
  cleanup();
  document.body.style.overflow = "";
});

function ReRenderingModal() {
  const [value, setValue] = useState("");

  return (
    <ModalLayer labelledBy="modal-title" onClose={() => undefined}>
      <button type="button">Închide</button>
      <h2 id="modal-title">Modal test</h2>
      <label>
        Nume campanie
        <input value={value} onChange={(event) => setValue(event.target.value)} />
      </label>
    </ModalLayer>
  );
}

describe("ModalLayer", () => {
  it("does not steal focus back to the first button after field changes", async () => {
    render(<ReRenderingModal />);

    const input = await screen.findByLabelText("Nume campanie");
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Închide" })).toBe(document.activeElement);
    });

    input.focus();
    fireEvent.change(input, { target: { value: "A" } });

    expect(input).toBe(document.activeElement);
    fireEvent.change(input, { target: { value: "AB" } });
    expect(input).toBe(document.activeElement);
  });
});
