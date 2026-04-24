import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/components/ui/toast-simple";
import { ClientProviders } from "@/components/layout/ClientProviders";

export const metadata: Metadata = {
  title: "Planet Ops Dashboard",
  description: "Compute Platform operations dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="font-sans bg-zinc-950 text-zinc-100 antialiased">
        <TooltipProvider>
          <ToastProvider>
            <ClientProviders>
              <div className="flex h-screen overflow-hidden">
                <Sidebar />
                <main className="flex-1 min-w-0 overflow-auto px-4 py-4">
                  <Suspense fallback={<div className="text-zinc-500 text-sm p-4">Loading...</div>}>{children}</Suspense>
                </main>
              </div>
            </ClientProviders>
          </ToastProvider>
        </TooltipProvider>
      </body>
    </html>
  );
}
