import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  ProfileAvatar,
  profileAvatarVisual,
  profileInitials,
} from "./profile-avatar";

const PALETTE_SPACE = 55_520_640;
const PALETTE_MULTIPLIER = 16_777_619;
const PALETTE_OFFSET = 2_166_136_261;

afterEach(cleanup);

describe("ProfileAvatar", () => {
  it("renders a stable Romanian-aware monogram for the account label", () => {
    render(
      <ProfileAvatar
        label="Ștefan Popescu"
        seed="trainer:user-1"
        paletteKey={12_345}
        className="size-8"
      />,
    );

    expect(screen.getByText("ȘP")).toBeTruthy();
    expect(document.querySelector("[data-profile-avatar]")?.getAttribute("data-avatar-theme")).toBeTruthy();
  });

  it("keeps the persisted account appearance stable across workspace contexts", () => {
    expect(profileAvatarVisual("trainer:user-1", 12_345)).toEqual(
      profileAvatarVisual("participant:different-seed", 12_345),
    );
    expect(profileAvatarVisual("trainer:user-1", 12_346)).not.toEqual(
      profileAvatarVisual("trainer:user-1", 12_345),
    );
  });

  it("spreads the first assigned accounts across bounded themes without duplicate gradients", () => {
    const visuals = Array.from({ length: 100 }, (_, index) => {
      const sequenceValue = index + 1;
      const paletteKey = (sequenceValue * PALETTE_MULTIPLIER + PALETTE_OFFSET) % PALETTE_SPACE;
      return profileAvatarVisual(`account-${sequenceValue}`, paletteKey);
    });

    expect(new Set(visuals.map((visual) => visual.themeName))).toHaveLength(8);
    expect(new Set(visuals.map((visual) => visual.style.backgroundImage))).toHaveLength(100);
  });

  it.each([
    ["Andrei Pop", "AP"],
    ["andrei.pop", "AP"],
    ["Participant", "P"],
    ["", "?"],
  ])("derives initials from %j", (label, expected) => {
    expect(profileInitials(label)).toBe(expected);
  });
});
