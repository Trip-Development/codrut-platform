/**
 * Paleta A „Brand cald” — plicul 175. Garda permanentă a culorilor din `globals.css`.
 *
 * Valorile alese de Andrei (STARE, 1 oct, `[culori-aplicatie]`) stau într-un singur loc, iar
 * contrastul perechilor text/fond se socotește aici (WCAG 2.1): o schimbare viitoare de culoare
 * care pică contrastul pică testul. Etichetele nivelurilor se verifică pe ambele teme.
 */
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const css = fs.readFileSync(path.resolve(__dirname, "../globals.css"), "utf8");

function bloc(selector: string): Record<string, string> {
  const i = css.indexOf(`${selector} {`);
  const corp = css.slice(i, css.indexOf("\n}", i));
  return Object.fromEntries([...corp.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]));
}
const TEME = { deschisa: bloc(":root"), intunecata: { ...bloc(":root"), ...bloc('[data-theme="dark"]') } };

type Rgba = [number, number, number, number];
const lin = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const delin = (c: number) => (c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055);
function oklab([r, g, b]: number[]) {
  [r, g, b] = [r, g, b].map(lin);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s];
}
function dinOklab([L, a, b]: number[]): number[] {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  return [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s].map((c) => Math.min(1, Math.max(0, delin(c))));
}
function culoare(v: string, t: Record<string, string>): Rgba {
  v = v.trim();
  if (v === "white") return [1, 1, 1, 1];
  if (v === "black") return [0, 0, 0, 1];
  if (v.startsWith("#")) return [1, 3, 5].map((i) => parseInt(v.slice(i, i + 2), 16) / 255).concat(1) as Rgba;
  let m = v.match(/^var\((--[\w-]+)\)$/);
  if (m) return culoare(t[m[1]], t);
  m = v.match(/^rgba?\((.+)\)$/);
  if (m) {
    const p = m[1].split(",").map(Number);
    return [p[0] / 255, p[1] / 255, p[2] / 255, p[3] ?? 1];
  }
  m = v.match(/^color-mix\(in (oklab|srgb),\s*(.+?)\s+([\d.]+)%,\s*(.+)\)$/);
  if (m) {
    const a = culoare(m[2], t), b = culoare(m[4], t), w = Number(m[3]) / 100;
    if (m[1] === "srgb") return [0, 1, 2].map((k) => a[k] * w + b[k] * (1 - w)).concat(1) as Rgba;
    const la = oklab(a), lb = oklab(b);
    return dinOklab([0, 1, 2].map((k) => la[k] * w + lb[k] * (1 - w))).concat(1) as Rgba;
  }
  throw new Error(`culoare necunoscută: ${v}`);
}
const peste = (f: Rgba, b: Rgba): Rgba => [0, 1, 2].map((k) => f[k] * f[3] + b[k] * (1 - f[3])).concat(1) as Rgba;
const lum = (c: Rgba) => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
function contrast(text: string, fond: string, t: Record<string, string>): number {
  const b = peste(culoare(`var(${fond})`, t), culoare("var(--background)", t));
  const f = peste(culoare(`var(${text})`, t), b);
  const [x, y] = [lum(f), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}

describe("paleta A — valorile alese de Andrei, într-un singur loc", () => {
  it("tema deschisă are fildeșul, vișiniul, ocrul și verdele brandului", () => {
    const t = TEME.deschisa;
    expect(t["--background"]).toBe("#FBF8F4");
    expect(t["--burgundy"]).toBe("#8A1530");
    expect(t["--gold"]).toBe("#C28F2C");
    expect(t["--brand-green"]).toBe("#A3D376");
    expect(t["--foreground"]).toBe("#191716");
    expect(t["--primary"]).toBe("var(--burgundy)");
  });

  it("vișiniul vechi nu mai apare în jetoane", () => {
    expect(css).not.toMatch(/#890505|137,\s*5,\s*5/i);
  });
});

const TEXT: Array<[string, string]> = [
  ["--foreground", "--background"], ["--foreground", "--surface"], ["--foreground", "--surface-muted"],
  ["--muted-foreground", "--background"], ["--muted-foreground", "--surface"], ["--muted-foreground", "--surface-muted"],
  ["--brand-text", "--background"], ["--brand-text", "--surface"], ["--brand-text", "--surface-muted"],
  ["--primary-foreground", "--primary"], ["--sidebar-primary-foreground", "--sidebar-primary"],
  ["--success-ink", "--surface"], ["--danger-ink", "--surface"], ["--warning-ink", "--surface"],
  ["--destructive-foreground", "--destructive"],
];
const ETICHETE: Array<[string, string, string]> = [
  ["CONȘTIENTIZARE", "--muted-foreground", "--track"],
  ["APLICARE", "--gold-ink", "--gold-soft"],
  ["CONSOLIDARE", "--brand-text", "--burgundy-soft"],
  ["INTEGRARE", "--success-ink", "--success-soft"],
];

describe.each(Object.entries(TEME))("contrastul, tema %s", (_, t) => {
  it.each(TEXT)("%s pe %s ≥ 4,5", (text, fond) => {
    expect(contrast(text, fond, t)).toBeGreaterThanOrEqual(4.5);
  });
  it.each(ETICHETE)("eticheta %s (%s pe %s) ≥ 4,5", (_n, text, fond) => {
    expect(contrast(text, fond, t)).toBeGreaterThanOrEqual(4.5);
  });
  it("conturul de focus ≥ 3", () => {
    expect(contrast("--focus-ring", "--background", t)).toBeGreaterThanOrEqual(3);
  });
});

describe("vișiniul ca text, cu opacitate — după 175", () => {
  it("nicio clasă `text-primary/NN` sau `text-burgundy/NN` în afara stărilor de hover", () => {
    // Variantele cu opacitate scapă regulii de pe tema întunecată (`--brand-text`): ~1,4 : 1 pe fond închis.
    const radacina = path.resolve(__dirname, "..", "..", "..");
    const gasite: string[] = [];
    const umbla = (dir: string) => {
      for (const intrare of fs.readdirSync(dir, { withFileTypes: true })) {
        const cale = path.join(dir, intrare.name);
        if (intrare.isDirectory()) umbla(cale);
        else if (/\.tsx?$/.test(intrare.name) && !/\.test\./.test(intrare.name) && !/ \d\./.test(intrare.name)) {
          const text = fs.readFileSync(cale, "utf8");
          for (const m of text.matchAll(/(\S*)text-(?:primary|burgundy)\/\d+/g)) {
            if (!/hover:/.test(m[1])) gasite.push(`${path.relative(radacina, cale)}: ${m[0]}`);
          }
        }
      }
    };
    umbla(path.join(radacina, "src"));
    expect(gasite).toEqual([]);
  });
});
