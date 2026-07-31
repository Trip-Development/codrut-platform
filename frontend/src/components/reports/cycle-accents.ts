export const CYCLE_ACCENTS = [
  { dot: "bg-burgundy", rail: "border-burgundy" },
  { dot: "bg-ochre", rail: "border-ochre" },
  { dot: "bg-foreground", rail: "border-foreground" },
  { dot: "bg-muted-foreground", rail: "border-muted-foreground" },
] as const;

export function cycleAccent(index: number) {
  return CYCLE_ACCENTS[index % CYCLE_ACCENTS.length];
}
