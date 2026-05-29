import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Codrut Platform",
  description: "Assessment and coaching platform for Codrut.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
