import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ari Emo - ASCII Hamster",
  description: "A cute ASCII hamster with emotions",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        {children}
      </body>
    </html>
  );
}
