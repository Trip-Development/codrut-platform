import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Cody",
    short_name: "Cody",
    description: "Platformă pentru assessment, coaching și management de rollout Cody.",
    lang: "ro",
    dir: "ltr",
    id: "/",
    start_url: "/participant",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#FBF8F4",
    theme_color: "#8A1530",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
