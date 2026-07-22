import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React, { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ModalLayer } from "./modal-layer";

afterEach(() => {
  cleanup();
  document.body.style.overflow = "";
  vi.restoreAllMocks();
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

  it("cancels the pending focus handoff when the modal unmounts", async () => {
    const requestAnimationFrameSpy = vi
      .spyOn(window, "requestAnimationFrame")
      .mockImplementation(() => 123);
    const cancelAnimationFrameSpy = vi
      .spyOn(window, "cancelAnimationFrame")
      .mockImplementation(() => undefined);

    const { unmount } = render(
      <ModalLayer labelledBy="modal-title" onClose={() => undefined}>
        <h2 id="modal-title">Modal test</h2>
      </ModalLayer>,
    );

    await waitFor(() => {
      expect(requestAnimationFrameSpy).toHaveBeenCalled();
    });

    unmount();

    expect(cancelAnimationFrameSpy).toHaveBeenCalledWith(123);
  });

  it("closes on Escape and backdrop interaction but not on panel interaction", async () => {
    const onClose = vi.fn();
    render(
      <ModalLayer titleId="modal-title" describedBy="modal-description" onClose={onClose}>
        <h2 id="modal-title">Confirmare</h2>
        <p id="modal-description">Verifică acțiunea.</p>
        <button type="button">Continuă</button>
      </ModalLayer>,
    );

    const dialog = await screen.findByRole("dialog", { name: "Confirmare" });
    fireEvent.mouseDown(dialog);
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.mouseDown(dialog.parentElement as HTMLElement);
    expect(onClose).toHaveBeenCalledTimes(2);
    expect(dialog.getAttribute("aria-describedby")).toBe("modal-description");
  });

  it("keeps focus inside the dialog and restores the previous focus on unmount", async () => {
    const opener = document.createElement("button");
    document.body.appendChild(opener);
    opener.focus();

    const { unmount } = render(
      <ModalLayer labelledBy="focus-title" onClose={() => undefined}>
        <h2 id="focus-title">Focalizare</h2>
        <button type="button">Primul</button>
        <button type="button">Ultimul</button>
      </ModalLayer>,
    );

    const first = await screen.findByRole("button", { name: "Primul" });
    const last = screen.getByRole("button", { name: "Ultimul" });
    await waitFor(() => expect(document.activeElement).toBe(first));
    expect(document.body.style.overflow).toBe("hidden");

    last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(first);

    first.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);

    unmount();
    expect(document.activeElement).toBe(opener);
    expect(document.body.style.overflow).toBe("");
    opener.remove();
  });

  it("focuses the panel when no controls exist and honors a locked backdrop", async () => {
    const onClose = vi.fn();
    render(
      <ModalLayer labelledBy="empty-title" closeOnBackdrop={false} onClose={onClose}>
        <h2 id="empty-title">Fără acțiuni</h2>
      </ModalLayer>,
    );

    const dialog = await screen.findByRole("dialog", { name: "Fără acțiuni" });
    await waitFor(() => expect(document.activeElement).toBe(dialog));
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(dialog);
    fireEvent.mouseDown(dialog.parentElement as HTMLElement);
    expect(onClose).not.toHaveBeenCalled();
  });
});
