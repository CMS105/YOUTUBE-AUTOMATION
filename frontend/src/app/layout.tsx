import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";

export const metadata: Metadata = {
  title: "GTA 6 AI Clip Factory",
  description: "Autonomous production engine turning GTA 6 broadcasts into viral vertical clips",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-text-primary antialiased min-h-screen">
        <Sidebar />
        <Header />
        <main className="ml-64 pt-16 min-h-screen p-8 bg-background">
          {children}
        </main>
      </body>
    </html>
  );
}
