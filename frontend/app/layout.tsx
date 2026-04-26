import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "K-Shorts",
  description: "Korean variety shorts auto-editor",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="dark">
      <body className="font-sans antialiased">
        <header className="border-b border-border px-6 py-4">
          <nav className="flex items-center gap-6">
            <span className="text-lg font-semibold text-accent">K-Shorts</span>
            <NavLink href="/">Edit</NavLink>
            <NavLink href="/history">History</NavLink>
            <NavLink href="/evolution">Evolution</NavLink>
            <NavLink href="/settings">Settings</NavLink>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} className="text-sm text-muted hover:text-white transition">
      {children}
    </a>
  );
}
