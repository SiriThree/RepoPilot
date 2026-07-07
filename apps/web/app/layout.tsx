import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RepoPilot Console",
  description: "Controlled code-repair agent runtime console"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
