import type { MetadataRoute } from "next";
import { describe, expect, it } from "vitest";

async function loadManifest(): Promise<MetadataRoute.Manifest> {
  const loaded = await import("./manifest");
  return loaded.default();
}

describe("manifest", () => {
  it("opens Cody as a standalone app at the participant area", async () => {
    const manifest = await loadManifest();

    expect(manifest.name).toBe("Cody");
    expect(manifest.short_name).toBe("Cody");
    expect(manifest.lang).toBe("ro");
    expect(manifest.display).toBe("standalone");
    expect(manifest.start_url).toBe("/participant");
    expect(manifest.scope).toBe("/");
    expect(manifest.background_color).toBe("#FBF8F4");
    expect(manifest.theme_color).toBe("#8A1530");
  });

  it("declares 192 and 512 png icons for both any and maskable purposes", async () => {
    const icons = (await loadManifest()).icons ?? [];

    for (const purpose of ["any", "maskable"] as const) {
      for (const size of ["192x192", "512x512"]) {
        expect(icons).toContainEqual(expect.objectContaining({ purpose, sizes: size }));
      }
    }
    for (const icon of icons) {
      expect(icon.type).toBe("image/png");
      expect(icon.src.startsWith("/icons/")).toBe(true);
    }
  });
});
