import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Building2Icon } from "lucide-react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SearchableProjectFilter, WorkspaceSearchInput } from "./project-workspace-controls";

describe("project workspace controls", () => {
  afterEach(() => cleanup());

  it("focuses and searches filter options without Romanian diacritics", () => {
    const onValueChange = vi.fn();
    render(
      <SearchableProjectFilter
        icon={Building2Icon}
        label="Status"
        value=""
        allLabel="Toate statusurile"
        options={[
          { value: "active", label: "Active" },
          { value: "draft", label: "În pregătire" },
        ]}
        onValueChange={onValueChange}
      />,
    );

    fireEvent.click(screen.getByRole("combobox", { name: "Status" }));
    const search = screen.getByRole("searchbox", { name: "Caută în status" });
    expect(document.activeElement).toBe(search);

    fireEvent.change(search, { target: { value: "pregatire" } });
    expect(screen.queryByRole("option", { name: "Active" })).toBeNull();
    fireEvent.keyDown(search, { key: "Enter" });

    expect(onValueChange).toHaveBeenCalledWith("draft");
    expect(screen.getByRole("combobox", { name: "Status" }).getAttribute("aria-expanded")).toBe("false");
  });

  it("keeps the search icon at the start and exposes a clear action", () => {
    const onValueChange = vi.fn();
    render(
      <WorkspaceSearchInput
        id="project-search"
        label="Caută proiect"
        placeholder="Caută proiect"
        value="Atlas"
        onValueChange={onValueChange}
      />,
    );

    const input = screen.getByLabelText("Caută proiect");
    expect(input.className).toContain("pl-10");
    expect(input.parentElement?.querySelector("svg")?.getAttribute("class")).toContain("left-3.5");
    fireEvent.click(screen.getByRole("button", { name: "Șterge căutarea" }));
    expect(onValueChange).toHaveBeenCalledWith("");
  });
});
