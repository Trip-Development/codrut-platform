import type { CSSProperties } from "react";

import { cn } from "@/utils/cn";

const AVATAR_PALETTE_SPACE = 55_520_640;

type HslAnchor = readonly [hue: number, saturation: number, lightness: number];

type AvatarTheme = {
  name: string;
  base: HslAnchor;
  highlight: HslAnchor;
  depth: HslAnchor;
};

const AVATAR_THEMES: readonly AvatarTheme[] = [
  { name: "rosewood", base: [350, 40, 34], highlight: [7, 58, 74], depth: [342, 39, 17] },
  { name: "terracotta", base: [14, 41, 42], highlight: [25, 68, 74], depth: [10, 40, 22] },
  { name: "sage", base: [138, 17, 38], highlight: [137, 27, 72], depth: [153, 21, 20] },
  { name: "teal", base: [184, 37, 34], highlight: [176, 37, 69], depth: [194, 44, 18] },
  { name: "denim", base: [216, 31, 40], highlight: [215, 47, 75], depth: [227, 31, 23] },
  { name: "iris", base: [261, 22, 42], highlight: [264, 35, 76], depth: [271, 26, 23] },
  { name: "berry", base: [326, 31, 36], highlight: [329, 42, 75], depth: [320, 35, 19] },
  { name: "walnut", base: [28, 20, 38], highlight: [32, 41, 72], depth: [24, 21, 20] },
];

export type ProfileAvatarVisual = {
  style: CSSProperties;
  themeName: string;
};

export function ProfileAvatar({
  label,
  seed,
  paletteKey,
  className,
  pending = false,
}: {
  label: string;
  seed: string;
  paletteKey?: number | null;
  className?: string;
  pending?: boolean;
}) {
  if (pending) {
    return (
      <span
        aria-hidden="true"
        className={cn("inline-flex shrink-0 animate-pulse rounded-full bg-foreground/10", className)}
      />
    );
  }

  const visual = profileAvatarVisual(seed, paletteKey);

  return (
    <span
      aria-hidden="true"
      data-profile-avatar
      data-avatar-palette-key={paletteKey ?? undefined}
      data-avatar-theme={visual.themeName}
      style={visual.style}
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full shadow-[inset_0_1px_1px_rgba(255,255,255,0.48),0_10px_24px_-16px_rgba(0,0,0,0.55)]",
        className,
      )}
    >
      <span className="relative z-10 text-[11px] font-semibold uppercase tracking-[-0.04em] text-primary-foreground drop-shadow-sm">
        {profileInitials(label)}
      </span>
    </span>
  );
}

export function profileAvatarVisual(
  seed: string,
  paletteKey?: number | null,
): ProfileAvatarVisual {
  const resolvedKey = resolveAvatarKey(seed, paletteKey);
  const themeSeed = mix32(resolvedKey ^ 0xa511e9b3);
  const colorSeed = mix32(resolvedKey ^ 0x68e31da4);
  const shapeSeed = mix32(resolvedKey ^ 0x9e3779b9);
  const theme = AVATAR_THEMES[themeSeed % AVATAR_THEMES.length];

  const hueDrift = unit(colorSeed, 0) * 12 - 6;
  const saturationDrift = unit(colorSeed, 8) * 8 - 4;
  const lightnessDrift = unit(colorSeed, 16) * 6 - 3;
  const highlightX = 20 + unit(shapeSeed, 0) * 58;
  const highlightY = 16 + unit(shapeSeed, 8) * 56;
  const depthX = clamp(100 - highlightX + (unit(shapeSeed, 16) * 14 - 7), 18, 82);
  const depthY = clamp(100 - highlightY + (unit(shapeSeed, 24) * 14 - 7), 18, 84);
  const highlightWidth = 38 + unit(colorSeed, 4) * 20;
  const highlightHeight = 36 + unit(shapeSeed, 5) * 22;
  const depthWidth = 46 + unit(colorSeed, 12) * 20;
  const depthHeight = 44 + unit(shapeSeed, 13) * 22;
  const highlightStop = 18 + unit(colorSeed, 20) * 16;
  const depthStop = 24 + unit(shapeSeed, 21) * 18;
  const angle = 18 + (resolvedKey / AVATAR_PALETTE_SPACE) * 64;

  const base = variedHsl(theme.base, hueDrift, saturationDrift, lightnessDrift);
  const highlight = variedHsl(
    theme.highlight,
    hueDrift * 0.55,
    saturationDrift,
    lightnessDrift * 0.55,
  );
  const depth = variedHsl(
    theme.depth,
    hueDrift * 0.35,
    saturationDrift * 0.6,
    lightnessDrift * 0.35,
  );

  return {
    themeName: theme.name,
    style: {
      backgroundColor: base.opaque,
      backgroundImage: [
        `linear-gradient(${angle.toFixed(6)}deg, transparent 12%, ${highlight.withAlpha(0.18)} 48%, transparent 72%)`,
        `radial-gradient(ellipse ${highlightWidth.toFixed(2)}% ${highlightHeight.toFixed(2)}% at ${highlightX.toFixed(2)}% ${highlightY.toFixed(2)}%, ${highlight.opaque} 0, ${highlight.withAlpha(0.72)} ${highlightStop.toFixed(2)}%, transparent 74%)`,
        `radial-gradient(ellipse ${depthWidth.toFixed(2)}% ${depthHeight.toFixed(2)}% at ${depthX.toFixed(2)}% ${depthY.toFixed(2)}%, ${depth.opaque} 0, ${depth.withAlpha(0.78)} ${depthStop.toFixed(2)}%, transparent 76%)`,
      ].join(", "),
    },
  };
}

export function profileInitials(label: string): string {
  const parts = label.trim().split(/[^\p{L}\p{N}]+/u).filter(Boolean);
  const selectedParts = parts.length > 1 ? [parts[0], parts.at(-1)] : parts;
  const initials = selectedParts
    .map((part) => Array.from(part ?? "")[0] ?? "")
    .join("")
    .toLocaleUpperCase("ro-RO");

  return initials || "?";
}

function resolveAvatarKey(seed: string, paletteKey?: number | null): number {
  if (
    paletteKey !== null
    && paletteKey !== undefined
    && Number.isSafeInteger(paletteKey)
    && paletteKey >= 0
    && paletteKey < AVATAR_PALETTE_SPACE
  ) {
    return paletteKey;
  }

  return unsignedHash(seed) % AVATAR_PALETTE_SPACE;
}

function variedHsl(
  [hue, saturation, lightness]: HslAnchor,
  hueDrift: number,
  saturationDrift: number,
  lightnessDrift: number,
) {
  const variedHue = (hue + hueDrift + 360) % 360;
  const variedSaturation = clamp(saturation + saturationDrift, 12, 72);
  const variedLightness = clamp(lightness + lightnessDrift, 15, 80);
  const components = `${variedHue.toFixed(2)} ${variedSaturation.toFixed(2)}% ${variedLightness.toFixed(2)}%`;

  return {
    opaque: `hsl(${components})`,
    withAlpha: (alpha: number) => `hsl(${components} / ${alpha})`,
  };
}

function unit(value: number, shift: number): number {
  return ((value >>> shift) & 255) / 255;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

function mix32(input: number): number {
  let value = input >>> 0;
  value ^= value >>> 16;
  value = Math.imul(value, 0x7feb352d);
  value ^= value >>> 15;
  value = Math.imul(value, 0x846ca68b);
  value ^= value >>> 16;
  return value >>> 0;
}

function unsignedHash(value: string): number {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}
