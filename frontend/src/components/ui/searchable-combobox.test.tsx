import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Building2Icon } from "lucide-react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { normalizeComboboxSearch, SearchableCombobox } from "./searchable-combobox";

afterEach(cleanup);

const options = [
  { value: "atelier", label: "Atelier Meridian" },
  { value: "brasov", label: "Echipa Brașov" },
  { value: "iasi", label: "Iași Leadership" },
];

function renderCombobox(value = "", onValueChange = vi.fn()) {
  render(
    <SearchableCombobox
      icon={Building2Icon}
      label="Companie"
      value={value}
      allLabel="Toate companiile"
      options={options}
      onValueChange={onValueChange}
    />,
  );
  return onValueChange;
}

describe("SearchableCombobox", () => {
  it("normalizes Romanian diacritics and whitespace", () => {
    expect(normalizeComboboxSearch("  BRAȘOV  ")).toBe("brasov");
    expect(normalizeComboboxSearch("Iași")).toBe("iasi");
  });

  it("opens from the keyboard, focuses search, filters without diacritics, and selects", async () => {
    const onValueChange = renderCombobox();
    const trigger = screen.getByRole("combobox", { name: "Companie" });

    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    const search = await screen.findByRole("searchbox", { name: "Caută în companie" });
    await waitFor(() => expect(document.activeElement).toBe(search));

    fireEvent.change(search, { target: { value: "brasov" } });
    expect(screen.getByRole("option", { name: "Echipa Brașov" })).toBeTruthy();
    expect(screen.queryByRole("option", { name: "Atelier Meridian" })).toBeNull();

    fireEvent.keyDown(search, { key: "Enter" });
    expect(onValueChange).toHaveBeenCalledWith("brasov");
    expect(screen.queryByRole("searchbox")).toBeNull();
  });

  it("supports bounded arrow navigation, Home, End, pointer selection, and Escape", async () => {
    const onValueChange = renderCombobox("atelier");
    fireEvent.click(screen.getByRole("combobox", { name: "Companie" }));
    const search = await screen.findByRole("searchbox");

    fireEvent.keyDown(search, { key: "ArrowUp" });
    fireEvent.keyDown(search, { key: "End" });
    fireEvent.keyDown(search, { key: "ArrowDown" });
    expect(search.getAttribute("aria-activedescendant")).toMatch(/option-3$/);

    fireEvent.keyDown(search, { key: "Home" });
    expect(search.getAttribute("aria-activedescendant")).toMatch(/option-0$/);

    fireEvent.mouseEnter(screen.getByRole("option", { name: "Iași Leadership" }));
    fireEvent.click(screen.getByRole("option", { name: "Iași Leadership" }));
    expect(onValueChange).toHaveBeenCalledWith("iasi");

    fireEvent.click(screen.getByRole("combobox", { name: "Companie" }));
    fireEvent.keyDown(await screen.findByRole("searchbox"), { key: "Escape" });
    expect(screen.queryByRole("searchbox")).toBeNull();
  });

  it("shows an empty result without creating an active descendant", async () => {
    renderCombobox("unknown");
    fireEvent.click(screen.getByRole("combobox", { name: "Companie" }));
    const search = await screen.findByRole("searchbox");
    fireEvent.change(search, { target: { value: "inexistent" } });

    expect(screen.getByText("Nicio opțiune găsită")).toBeTruthy();
    expect(search.getAttribute("aria-activedescendant")).toBeNull();
    fireEvent.keyDown(search, { key: "Enter" });
  });
});
