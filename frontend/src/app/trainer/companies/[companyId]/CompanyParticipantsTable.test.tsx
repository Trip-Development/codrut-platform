import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CompanyParticipant } from "@/api/companies";
import { CompanyParticipantsTable } from "./CompanyParticipantsTable";

const navigation = vi.hoisted(() => ({
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: navigation.replace, push: vi.fn() }),
  usePathname: () => "/trainer/companies/company-1/participants",
  useSearchParams: () => new URLSearchParams(),
}));

const participants: CompanyParticipant[] = [
  {
    id: "participant-1",
    full_name: "Ștefan Ionescu",
    email: "stefan@example.test",
    reports_to_name: "Ana Manager",
    position: "Consultant",
    location: "București",
    role_group: "member",
    pcm_profile: null,
    user_id: null,
  },
  {
    id: "participant-2",
    full_name: "Ana Manager",
    email: "ana@example.test",
    reports_to_name: null,
    position: "Director",
    location: "Cluj",
    role_group: "leadership",
    pcm_profile: null,
    user_id: "user-2",
  },
];

describe("CompanyParticipantsTable", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("filters company participants without diacritics and persists the query in the URL", () => {
    render(<CompanyParticipantsTable participants={participants} />);

    fireEvent.change(screen.getByLabelText("Caută participant"), {
      target: { value: "stefan" },
    });

    expect(screen.getByText("Ștefan Ionescu")).toBeTruthy();
    expect(screen.queryByText("ana@example.test")).toBeNull();
    expect(navigation.replace).toHaveBeenCalledWith(
      "/trainer/companies/company-1/participants?q=stefan",
      { scroll: false },
    );
  });
});
