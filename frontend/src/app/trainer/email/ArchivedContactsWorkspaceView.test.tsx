import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CampaignRecipientRow } from "@/api/email";
import { ArchivedContactsWorkspaceView } from "./ArchivedContactsWorkspaceView";

afterEach(cleanup);

const archivedContact: CampaignRecipientRow = {
  id: "recipient-1",
  company: "",
  email: "ioana@example.com",
  clientType: "tip_2",
  status: "archived",
  activationAllowed: false,
  statusBeforeArchive: "suppressed",
  purgeAfter: "2026-08-29T12:00:00Z",
};

describe("ArchivedContactsWorkspaceView", () => {
  it("distinguishes an empty archive from an empty search result", () => {
    const setSearch = vi.fn();
    const props = {
      message: null,
      contacts: [],
      action: null,
      setSearch,
      restoreContact: vi.fn(),
      deleteContact: vi.fn(),
    };
    const { rerender } = render(
      <ArchivedContactsWorkspaceView {...props} search="" />,
    );

    expect(screen.getByText("Arhiva este goală.")).toBeTruthy();
    fireEvent.change(screen.getByRole("textbox", { name: "Caută contacte arhivate" }), {
      target: { value: "Ioana" },
    });
    expect(setSearch).toHaveBeenCalledWith("Ioana");

    rerender(<ArchivedContactsWorkspaceView {...props} search="Ioana" />);
    expect(
      screen.getByText("Niciun contact arhivat nu corespunde căutării."),
    ).toBeTruthy();
  });

  it("shows the protected restore-in-progress state without inventing a name", () => {
    render(
      <ArchivedContactsWorkspaceView
        message="Restaurarea este în curs."
        contacts={[archivedContact]}
        search=""
        action={{ recipientId: archivedContact.id, kind: "restore" }}
        setSearch={vi.fn()}
        restoreContact={vi.fn()}
        deleteContact={vi.fn()}
      />,
    );

    expect(screen.getByText("Restaurarea este în curs.")).toBeTruthy();
    expect(screen.getByText("Contact fără nume")).toBeTruthy();
    expect(screen.getByText("Înainte: Adresă respinsă")).toBeTruthy();
    expect(screen.getByText("Curățare automată: 29 august 2026")).toBeTruthy();
    expect(
      (screen.getByRole("button", { name: "Restaurăm" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("offers permanent deletion only from the archive", () => {
    const deleteContact = vi.fn();
    render(
      <ArchivedContactsWorkspaceView
        message={null}
        contacts={[archivedContact]}
        search=""
        action={null}
        setSearch={vi.fn()}
        restoreContact={vi.fn()}
        deleteContact={deleteContact}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Șterge definitiv" }));
    expect(deleteContact).toHaveBeenCalledWith(archivedContact);
  });
});
