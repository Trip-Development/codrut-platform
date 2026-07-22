import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { headers } from "next/headers";
import { THEME_PREPAINT_SCRIPT } from "@/lib/theme-prepaint";
import "./globals.css";

export const dynamic = "force-dynamic";

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-geist",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Cody Platform",
  description: "Platformă pentru assessment, coaching și management de rollout Cody.",
  applicationName: "Cody",
  icons: {
    icon: [
      { url: "/icons/favicon-32.png", type: "image/png", sizes: "32x32" },
      { url: "/icons/favicon-16.png", type: "image/png", sizes: "16x16" },
    ],
    apple: "/icons/apple-touch-icon.png",
  },
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const nonce = (await headers()).get("x-nonce") ?? undefined;

  return (
    <html lang="ro" data-scroll-behavior="smooth" suppressHydrationWarning>
      <body className={geist.variable}>
        <script
          id="codrut-theme-prepaint"
          nonce={nonce}
          suppressHydrationWarning
          dangerouslySetInnerHTML={{
            __html: THEME_PREPAINT_SCRIPT,
          }}
        />
        <div className="app-min-height bg-background text-foreground selection:bg-burgundy selection:text-white">
          {children}
        </div>
      </body>
    </html>
  );
}
