import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "QuoteDrive — Compare Ontario Car Insurance",
  description: "Compare Ontario auto insurance rates across direct, broker and specialty carriers in minutes.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="page-bg">{children}</body>
    </html>
  );
}
