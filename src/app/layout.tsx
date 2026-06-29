import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import { AuthProvider } from "@/context/AuthContext";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Dx LIS",
  description: "Laboratory Information System",
};

import AlertBanner from "@/components/AlertBanner";

import { readDb } from "@/lib/db";

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const db = await readDb();
  const settings = db.settings || {};
  const themeClass = `theme-${settings.themeColor || 'blue'}`;
  const modeClass = settings.themeMode === 'dark' ? 'mode-dark' : '';

  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} ${themeClass} ${modeClass}`} suppressHydrationWarning>
        <AuthProvider>
          <div className="flex min-h-screen bg-slate-50">
            <Sidebar />
            <div className="flex-1 flex flex-col min-w-0">
              <AlertBanner />
              <main className="flex-1 p-8 overflow-y-auto">
                {children}
              </main>
            </div>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
