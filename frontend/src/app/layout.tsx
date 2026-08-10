import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Modern AI Stack",
  description: "FastAPI + OpenAI + Next.js chat assistant",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
