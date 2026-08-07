import type { CSSProperties } from "react";

import { cn } from "@/utils/cn";

const AVATAR_PALETTE_SPACE = 55_520_640;

type HslAnchor = readonly [hue: number, saturation: number, lightness: number];

type IdentityTheme = {
  name: string;
  base: HslAnchor;
  highlight: HslAnchor;
  depth: HslAnchor;
};

const IDENTITY_THEMES: readonly IdentityTheme[] = [
  { name: "rosewood", base: [350, 40, 34], highlight: [7, 58, 74], depth: [342, 39, 17] },
  { name: "terracotta", base: [14, 41, 42], highlight: [25, 68, 74], depth: [10, 40, 22] },
  { name: "sage", base: [138, 17, 38], highlight: [137, 27, 72], depth: [153, 21, 20] },
  { name: "teal", base: [184, 37, 34], highlight: [176, 37, 69], depth: [194, 44, 18] },
  { name: "denim", base: [216, 31, 40], highlight: [215, 47, 75], depth: [227, 31, 23] },
  { name: "iris", base: [261, 22, 42], highlight: [264, 35, 76], depth: [271, 26, 23] },
  { name: "berry", base: [326, 31, 36], highlight: [329, 42, 75], depth: [320, 35, 19] },
  { name: "walnut", base: [28, 20, 38], highlight: [32, 41, 72], depth: [24, 21, 20] },
];

export type IdentityMarkKind = "person" | "contact" | "company";
export type IdentityMarkSize = "xs" | "sm" | "md" | "lg" | "xl";

export type IdentityMarkVisual = {
  style: CSSProperties;
  themeName: string;
};

const SIZE_CLASSES: Record<IdentityMarkSize, string> = {
  xs: "size-7 text-[9px]",
  sm: "size-9 text-[11px]",
  md: "size-10 text-xs",
  lg: "size-14 text-lg",
  xl: "size-[52px] text-sm",
};

export function IdentityMark({
  kind,
  label,
  seed,
  paletteKey,
  size = "sm",
  className,
  pending = false,
  profile = false,
}: {
  kind: IdentityMarkKind;
  label: string;
  seed: string;
  paletteKey?: number | null;
  size?: IdentityMarkSize;
  className?: string;
  pending?: boolean;
  profile?: boolean;
}) {
  const shapeClass = kind === "company" ? "rounded-[11px]" : "rounded-full";

  if (pending) {
    return (
      <span
        aria-hidden="true"
        className={cn(
          "inline-flex shrink-0 animate-pulse bg-foreground/10",
          shapeClass,
          SIZE_CLASSES[size],
          className,
        )}
      />
    );
  }

  const visual = identityMarkVisual(kind, seed, paletteKey);

  return (
    <span
      aria-hidden="true"
      data-identity-mark
      data-identity-kind={kind}
      data-profile-avatar={profile ? "" : undefined}
      data-avatar-palette-key={paletteKey ?? undefined}
      data-avatar-theme={visual.themeName}
      style={visual.style}
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center overflow-hidden font-semibold uppercase tracking-[-0.04em]",
        kind === "contact"
          ? "ring-1 ring-inset ring-border"
          : "text-primary-foreground shadow-[inset_0_1px_1px_rgba(255,255,255,0.48),0_10px_24px_-16px_rgba(0,0,0,0.55)]",
        shapeClass,
        size === "xl" && kind === "company" && "rounded-[14px]",
        SIZE_CLASSES[size],
        className,
      )}
    >
      <span className="relative z-10 drop-shadow-[0_1px_1px_rgba(0,0,0,0.14)]">
        {identityInitials(label)}
      </span>
    </span>
  );
}

export function identityMarkVisual(
  kind: IdentityMarkKind,
  seed: string,
  paletteKey?: number | null,
): IdentityMarkVisual {
  const resolvedKey = resolveIdentityKey(seed, paletteKey);
  const themeSeed = mix32(resolvedKey ^ 0xa511e9b3);
  const colorSeed = mix32(resolvedKey ^ 0x68e31da4);
  const shapeSeed = mix32(resolvedKey ^ 0x9e3779b9);
  const theme = IDENTITY_THEMES[themeSeed % IDENTITY_THEMES.length];

  const hueDrift = unit(colorSeed, 0) * 12 - 6;
  const saturationDrift = unit(colorSeed, 8) * 8 - 4;
  const lightnessDrift = unit(colorSeed, 16) * 6 - 3;
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
    style: kind === "contact"
      ? contactVisualStyle(resolvedKey, colorSeed, shapeSeed, base, highlight, depth)
      : layeredVisualStyle(kind, resolvedKey, colorSeed, shapeSeed, base, highlight, depth),
  };
}

export function identityInitials(label: string): string {
  const parts = label.trim().split(/[^\p{L}\p{N}]+/u).filter(Boolean);
  const selectedParts = parts.length > 1 ? [parts[0], parts.at(-1)] : parts;
  const initials = selectedParts
    .map((part) => Array.from(part ?? "")[0] ?? "")
    .join("")
    .toLocaleUpperCase("ro-RO");

  return initials || "?";
}

function layeredVisualStyle(
  kind: Exclude<IdentityMarkKind, "contact">,
  resolvedKey: number,
  colorSeed: number,
  shapeSeed: number,
  base: HslColor,
  highlight: HslColor,
  depth: HslColor,
): CSSProperties {
  const highlightX = 20 + unit(shapeSeed, 0) * 58;
  const highlightY = 16 + unit(shapeSeed, 8) * 56;
  const depthX = clamp(100 - highlightX + (unit(shapeSeed, 16) * 14 - 7), 18, 82);
  const depthY = clamp(100 - highlightY + (unit(shapeSeed, 24) * 14 - 7), 18, 84);
  const highlightWidth = 38 + unit(colorSeed, 4) * (kind === "company" ? 34 : 20);
  const highlightHeight = 36 + unit(shapeSeed, 5) * (kind === "company" ? 28 : 22);
  const depthWidth = 46 + unit(colorSeed, 12) * (kind === "company" ? 28 : 20);
  const depthHeight = 44 + unit(shapeSeed, 13) * (kind === "company" ? 26 : 22);
  const highlightStop = 18 + unit(colorSeed, 20) * 16;
  const depthStop = 24 + unit(shapeSeed, 21) * 18;
  const angle = kind === "company"
    ? 124 + unit(shapeSeed, 3) * 32
    : 18 + (resolvedKey / AVATAR_PALETTE_SPACE) * 64;

  return {
    backgroundColor: base.opaque,
    backgroundImage: [
      `linear-gradient(${angle.toFixed(6)}deg, transparent 12%, ${highlight.withAlpha(kind === "company" ? 0.24 : 0.18)} 48%, transparent 72%)`,
      `radial-gradient(ellipse ${highlightWidth.toFixed(2)}% ${highlightHeight.toFixed(2)}% at ${highlightX.toFixed(2)}% ${highlightY.toFixed(2)}%, ${highlight.opaque} 0, ${highlight.withAlpha(kind === "company" ? 0.62 : 0.72)} ${highlightStop.toFixed(2)}%, transparent 74%)`,
      `radial-gradient(ellipse ${depthWidth.toFixed(2)}% ${depthHeight.toFixed(2)}% at ${depthX.toFixed(2)}% ${depthY.toFixed(2)}%, ${depth.opaque} 0, ${depth.withAlpha(kind === "company" ? 0.72 : 0.78)} ${depthStop.toFixed(2)}%, transparent 76%)`,
    ].join(", "),
  };
}

function contactVisualStyle(
  resolvedKey: number,
  colorSeed: number,
  shapeSeed: number,
  base: HslColor,
  highlight: HslColor,
  depth: HslColor,
): CSSProperties {
  const angle = 132 + unit(shapeSeed, 2) * 24;
  const middleStop = 44 + unit(colorSeed, 10) * 16;
  const matteBase = base.adjusted(0, -8, 22);
  const matteHighlight = highlight.adjusted(0, -10, 8);
  const matteDepth = depth.adjusted(0, -12, 34);

  return {
    color: depth.adjusted(0, 2, 5).opaque,
    backgroundColor: matteBase.opaque,
    backgroundImage: [
      `linear-gradient(${angle.toFixed(6)}deg, ${matteHighlight.withAlpha(0.96)}, ${matteBase.withAlpha(0.88)} ${middleStop.toFixed(2)}%, ${matteDepth.withAlpha(0.82)})`,
      `linear-gradient(${18 + (resolvedKey / AVATAR_PALETTE_SPACE) * 64}deg, ${highlight.withAlpha(0.12)}, transparent 58%)`,
    ].join(", "),
  };
}

type HslColor = {
  opaque: string;
  withAlpha: (alpha: number) => string;
  adjusted: (hue: number, saturation: number, lightness: number) => HslColor;
};

function variedHsl(
  [hue, saturation, lightness]: HslAnchor,
  hueDrift: number,
  saturationDrift: number,
  lightnessDrift: number,
): HslColor {
  return hslColor(
    (hue + hueDrift + 360) % 360,
    clamp(saturation + saturationDrift, 12, 72),
    clamp(lightness + lightnessDrift, 15, 80),
  );
}

function hslColor(hue: number, saturation: number, lightness: number): HslColor {
  const components = `${hue.toFixed(2)} ${saturation.toFixed(2)}% ${lightness.toFixed(2)}%`;

  return {
    opaque: `hsl(${components})`,
    withAlpha: (alpha: number) => `hsl(${components} / ${alpha})`,
    adjusted: (hueDelta, saturationDelta, lightnessDelta) => hslColor(
      (hue + hueDelta + 360) % 360,
      clamp(saturation + saturationDelta, 10, 76),
      clamp(lightness + lightnessDelta, 14, 88),
    ),
  };
}

function resolveIdentityKey(seed: string, paletteKey?: number | null): number {
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
