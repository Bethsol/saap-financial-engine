import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SaaP — Financial Intelligence Engine",
  description:
    "Service-as-a-Product framework for SME financial intelligence (Thesis prototype, 2026)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-brand-900">
                Financial Intelligence Engine
              </h1>
              <p className="text-xs text-slate-500">
                Service-as-a-Product prototype · Thesis 2026
              </p>
            </div>
            <span className="text-xs px-2 py-1 rounded-full bg-brand-50 text-brand-700">
              MVP · v0.1
            </span>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
