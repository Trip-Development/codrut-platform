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

  it("the only service worker is public/sw.js: notifications only, no page cache (plicul 252)", () => {
    const registerCall = ["serviceWorker", "register"].join(".");
    const callers = sourceFiles(srcDir)
      .filter((file) => !file.endsWith(".test.ts") && !file.endsWith(".test.tsx"))
      .filter((file) => readFileSync(file, "utf8").includes(registerCall))
      .map((file) => path.relative(srcDir, file));
    expect(callers).toEqual([path.join("lib", "notificare-browser.ts")]);

    const lib = readFileSync(path.join(srcDir, "lib", "notificare-browser.ts"), "utf8");
    expect(lib.split("register(").length - 1).toBe(1);
    expect(lib).toContain('register("/sw.js"');

    const sw = readFileSync(path.join(publicDir, "sw.js"), "utf8");
    const listeners = [...sw.matchAll(/addEventListener\("([a-z]+)"/g)].map((m) => m[1]);
    expect(listeners).toEqual(["push", "notificationclick"]);
    expect(sw.split("addEventListener").length - 1).toBe(2);
    for (const forbidden of ["fetch", "caches", "importScripts", "event.data", "onfetch", "oninstall", "onactivate", "onmessage", "onsync"]) {
      expect(sw, forbidden).not.toContain(forbidden);
    }

    const publicJs = readdirSync(publicDir).filter((name) => name.endsWith(".js"));
    expect(publicJs).toEqual(["sw.js"]);
    expect(existsSync(path.join(publicDir, "service-worker.js"))).toBe(false);
  });
});
