import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/providers/QueryProvider";
import { SidebarProvider } from "@/providers/SidebarProvider";
import { LaporSarProvider } from "@/providers/LaporSarProvider";
import { LayoutShell } from "@/components/layout/LayoutShell";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Lapor SAR Command Center",
  description: "Sistem Pelaporan Kondisi Marabahaya & Pusat Pengendali Operasi SAR",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="id" suppressHydrationWarning>
      <body className={`${inter.className} bg-gray-50 flex h-screen overflow-hidden`} suppressHydrationWarning>
        <QueryProvider>
          <SidebarProvider>
            <LaporSarProvider>
              <LayoutShell>{children}</LayoutShell>
            </LaporSarProvider>
          </SidebarProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
