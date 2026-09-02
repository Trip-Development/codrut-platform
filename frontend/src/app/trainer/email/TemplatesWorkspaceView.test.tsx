import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { EmailTemplate } from "@/api/email";
import { TemplatesWorkspaceView, type TemplatesWorkspaceViewProps } from "./TemplatesWorkspaceView";

afterEach(cleanup);

const mockTemplate: EmailTemplate = {
  id: "template-1",
  name: "Promo prospect",
  key: "promo_potential_intro",
  lane: "campaign",
  version: 1,
  subject: "Subiect de test",
  body: "Corp de test",
  variables: ["{first_name}"],
  placeholders: ["{first_name}"],
  active: true,
};

function createProps(overrides: Partial<TemplatesWorkspaceViewProps> = {}): TemplatesWorkspaceViewProps {
  return {
    selectedTemplateId: "template-1",
    selectedTemplate: mockTemplate,
    filteredTemplates: [mockTemplate],
    templateCount: 1,
    searchQuery: "",
    isEditing: true,
    isLoading: false,
    operation: null,
    editSubject: "Subiect de test",
    editHeading: "Titlu de test",
    editBody: "Corp de test",
    editLane: "campaign",
    preview: { subject: "Subiect de test", bodyHtml: "<p>Corp</p>" },
    previewCalendlyUrl: "https://calendly.com",
    validationMessage: null,
    onSearchChange: vi.fn(),
    onSelectTemplate: vi.fn(),
    onCreate: vi.fn(),
    onSave: vi.fn(),
    onCreateVersion: vi.fn(),
    onDelete: vi.fn(),
    setIsEditing: vi.fn(),
    setEditSubject: vi.fn(),
    setEditHeading: vi.fn(),
    setEditBody: vi.fn(),
    setEditLane: vi.fn(),
    setPreviewCalendlyUrl: vi.fn(),
    ...overrides,
  };
}

describe("TemplatesWorkspaceView - S2 Video Button Visibility", () => {
  it("D2.a: cu canalul pe campanie, butonul Adaugă video este disponibil", () => {
    const setEditBody = vi.fn();
    render(<TemplatesWorkspaceView {...createProps({ editLane: "campaign", setEditBody })} />);

    const videoBtn = screen.getByRole("button", { name: "Adaugă video" });
    expect(videoBtn).toBeTruthy();
    expect((videoBtn as HTMLButtonElement).disabled).toBe(false);

    fireEvent.click(videoBtn);
    expect(setEditBody).toHaveBeenCalled();
  });

  it("D2.b: cu canalul pe tranzacțional, butonul Adaugă video NU este disponibil", () => {
    render(<TemplatesWorkspaceView {...createProps({ editLane: "transactional" })} />);

    const videoBtn = screen.queryByRole("button", { name: "Adaugă video" });
    expect(videoBtn).toBeNull();
  });

  it("D2.c: butonul Adaugă buton link se comportă identic pe ambele canale", () => {
    const setEditBodyCampaign = vi.fn();
    const { rerender } = render(
      <TemplatesWorkspaceView {...createProps({ editLane: "campaign", setEditBody: setEditBodyCampaign })} />
    );

    const linkBtnCampaign = screen.getByRole("button", { name: "Adaugă buton link" });
    expect(linkBtnCampaign).toBeTruthy();
    expect((linkBtnCampaign as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(linkBtnCampaign);
    expect(setEditBodyCampaign).toHaveBeenCalled();

    const setEditBodyTransactional = vi.fn();
    rerender(
      <TemplatesWorkspaceView {...createProps({ editLane: "transactional", setEditBody: setEditBodyTransactional })} />
    );

    const linkBtnTransactional = screen.getByRole("button", { name: "Adaugă buton link" });
    expect(linkBtnTransactional).toBeTruthy();
    expect((linkBtnTransactional as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(linkBtnTransactional);
    expect(setEditBodyTransactional).toHaveBeenCalled();
  });
});
