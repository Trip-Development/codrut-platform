export const CYCLE_ACCENTS = [
  { dot: "bg-[#dc3f43]", rail: "border-[#dc3f43]", color: "#dc3f43" },
  { dot: "bg-[#d79c2b]", rail: "border-[#d79c2b]", color: "#d79c2b" },
  { dot: "bg-[#22a06b]", rail: "border-[#22a06b]", color: "#22a06b" },
  { dot: "bg-[#3b82f6]", rail: "border-[#3b82f6]", color: "#3b82f6" },
  { dot: "bg-[#8b5cf6]", rail: "border-[#8b5cf6]", color: "#8b5cf6" },
  { dot: "bg-[#0891b2]", rail: "border-[#0891b2]", color: "#0891b2" },
  { dot: "bg-[#ea7c2b]", rail: "border-[#ea7c2b]", color: "#ea7c2b" },
] as const;

export function cycleAccent(index: number) {
  return CYCLE_ACCENTS[index % CYCLE_ACCENTS.length];
}
