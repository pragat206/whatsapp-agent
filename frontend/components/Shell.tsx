"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "@/lib/api";
import type { Me } from "@/lib/types";
import BraneMindFooter from "./BraneMindFooter";
import ThemeToggle from "./ThemeToggle";

const NAV = [
  { href: "/dashboard", label: "Overview" },
  { href: "/inbox", label: "Inbox" },
  { href: "/leads", label: "Leads" },
  { href: "/campaigns", label: "Campaigns" },
  { href: "/kb", label: "Knowledge Base" },
  { href: "/agents", label: "Agents" },
  { href: "/contacts", label: "Contacts" },
  { href: "/diagnostics", label: "Diagnostics" },
  { href: "/settings", label: "Settings" }
];

export default function Shell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    api<Me>("/auth/me")
      .then(setMe)
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) return <div style={{ padding: 24 }}>Loading…</div>;
  if (!me) return null;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "228px 1fr",
        minHeight: "100vh"
      }}
    >
      <aside
        style={{
          background: "var(--bg-soft)",
          borderRight: "1px solid var(--border)",
          padding: "1.25rem 0.75rem",
          display: "flex",
          flexDirection: "column",
          gap: 8
        }}
      >
        <div style={{ padding: "0 0.5rem 0.75rem" }}>
          <div style={{ fontWeight: 700, fontSize: "1rem", color: "var(--text-strong)" }}>
            Terra Rex
          </div>
          <div className="muted small">WhatsApp agent</div>
        </div>

        <nav style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {NAV.map((n) => {
            const active = pathname === n.href || pathname?.startsWith(n.href + "/");
            return (
              <Link
                key={n.href}
                href={n.href}
                style={{
                  padding: "0.5rem 0.75rem",
                  borderRadius: 6,
                  color: active ? "var(--accent)" : "var(--text)",
                  background: active ? "var(--accent-soft)" : "transparent",
                  fontSize: "0.9rem",
                  fontWeight: active ? 600 : 400,
                  transition: "background-color 120ms ease, color 120ms ease"
                }}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>

        <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
          <ThemeToggle />

          <div
            style={{
              borderTop: "1px solid var(--border)",
              paddingTop: 10,
              fontSize: "0.78rem",
              color: "var(--muted)"
            }}
          >
            <div style={{ color: "var(--text)", fontWeight: 500 }}>{me.name}</div>
            <div>{me.email}</div>
            <div className="pill" style={{ marginTop: 6 }}>{me.role}</div>
            <button
              style={{ marginTop: 10, width: "100%" }}
              onClick={() => {
                setToken(null);
                router.replace("/login");
              }}
            >
              Log out
            </button>
          </div>

          <div style={{ paddingTop: 8, borderTop: "1px solid var(--border)" }}>
            <BraneMindFooter />
          </div>
        </div>
      </aside>
      <main style={{ padding: "1.5rem", overflow: "auto" }}>{children}</main>
    </div>
  );
}
