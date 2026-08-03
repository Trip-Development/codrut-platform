# Codrut interface system

## Direction

- Product character: calm, evidence-led, professional coaching software.
- Visual world: graphite surfaces, paper gray, burgundy actions, warm amber comparisons, restrained green outcomes.
- Signature element: compact first-to-latest evidence rows with values, change, and interpretation together.
- Avoid repeated report headings, decorative explanation, link-like disclosure controls, oversized cards, and route-specific copies of shared controls.

## Layout

- Use the existing 4px spacing scale and established app-shell widths.
- Keep comparison controls in one quiet bordered toolbar above the report.
- On desktop, use available width for side-by-side comparisons and three iCARE perspectives.
- On narrow screens, stack without horizontal overflow and keep labels adjacent to their values.
- Use one section heading and one short sentence per result family; do not restate the page title inside the result body.

## Components

- Reuse `CycleComparisonToolbar` for trainer, participant, and individual leadership comparisons.
- Reuse `CycleComparisonBars`, `ResultSignalBadge`, `InterpretationDisclosure`, and `ReportSection` for report presentation.
- Use native or Radix controls already in the repository. Do not add a new UI dependency for report work.
- Extract a primitive on its second real use. Keep assessment-specific transformations in their feature module.

## Charts and meaning

- Baseline is red; comparison is warm amber. Additional category colors come from semantic chart tokens.
- Comparison bars are rounded, left-aligned, and directly labeled. Do not add endpoint dots, rails, ticks, or guide lines.
- Percentage changes use percentage points. Lencioni uses raw points on the source 3–9 scale.
- A lower TA stress-driver score is improvement; higher Lencioni and iCARE scores are improvement.
- Use paired donut charts for category distributions and bars for ordered numeric change.

## Interaction and accessibility

- Every control needs visible keyboard focus and a minimum comfortable target.
- Interpretation disclosures must look actionable and keep the full source text available without dominating scan flow.
- Back actions should return to the referring in-app route when possible and use a safe fallback only for direct visits.
- Validate loading, empty, privacy-threshold, stale-link, mobile, laptop, and desktop states for changed report surfaces.
