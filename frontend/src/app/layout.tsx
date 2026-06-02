import type { Metadata } from "next";
import { Fraunces, Inter_Tight } from "next/font/google";
import "./globals.css";

const interTight = Inter_Tight({
  subsets: ["latin"],
  variable: "--font-inter-tight",
  weight: ["400", "500", "600", "700"],
});

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  weight: ["500", "700"],
});

export const metadata: Metadata = {
  title: "Codrut Platform",
  description: "Assessment, coaching, and rollout management platform for Codrut.",
  applicationName: "Codrut",
  icons: {
    icon: [
      { url: "/icons/favicon-32.png", type: "image/png", sizes: "32x32" },
      { url: "/icons/favicon-16.png", type: "image/png", sizes: "16x16" },
    ],
    apple: "/icons/apple-touch-icon.png",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ro">
      <body className={`${interTight.variable} ${fraunces.variable}`}>
        <div className="app-min-height bg-background text-foreground selection:bg-burgundy selection:text-white">
          {children}
        </div>
      </body>
    </html>
  );
}
