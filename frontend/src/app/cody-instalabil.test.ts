import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const frontendRoot = path.resolve(__dirname, "../..");
const publicDir = path.join(frontendRoot, "public");
const srcDir = path.join(frontendRoot, "src");

function pngSize(file: string): { width: number; height: number } {
  const bytes = readFileSync(file);
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return sourceFiles(full);
    return /\.(ts|tsx|js|jsx|mjs)$/.test(name) ? [full] : [];
  });
}

describe("Cody installable on the phone", () => {
  it("every manifest icon exists in public/ with the declared size", async () => {
    const { default: manifest } = await import("./manifest");
    const icons = manifest().icons ?? [];

    expect(icons.length).toBeGreaterThan(0);
    for (const icon of icons) {
      const file = path.join(publicDir, icon.src);
      expect(existsSync(file), icon.src).toBe(true);
      const [width, height] = (icon.sizes ?? "").split("x").map(Number);
      expect(pngSize(file), icon.src).toEqual({ width, height });
    }
  });

  it("ships no service worker (pages are per-request with a nonce)", () => {
    const registerCall = ["serviceWorker", "register"].join(".");
    const offenders = sourceFiles(srcDir).filter((file) =>
      readFileSync(file, "utf8").includes(registerCall),
    );

    expect(offenders).toEqual([]);
    expect(existsSync(path.join(publicDir, "sw.js"))).toBe(false);
    expect(existsSync(path.join(publicDir, "service-worker.js"))).toBe(false);
  });
});
