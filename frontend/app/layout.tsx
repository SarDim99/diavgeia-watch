import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Diavgeia Watch — Public Spending Intelligence",
  description: "AI-powered analysis of Greek government spending data",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="el">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}