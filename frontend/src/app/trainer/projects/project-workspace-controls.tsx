"use client";

import { SearchField } from "@/components/ui/search-field";

export { SearchableCombobox as SearchableProjectFilter } from "@/components/ui/searchable-combobox";
export { normalizeComboboxSearch as normalizeWorkspaceSearch } from "@/components/ui/searchable-combobox";

export function WorkspaceSearchInput({
  id,
  label,
  placeholder,
  value,
  onValueChange,
  className,
}: {
  id: string;
  label: string;
  placeholder: string;
  value: string;
  onValueChange: (value: string) => void;
  className?: string;
}) {
  return (
    <SearchField
      id={id}
      label={label}
      placeholder={placeholder}
      value={value}
      onValueChange={onValueChange}
      className={className}
    />
  );
}
