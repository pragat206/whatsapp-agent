"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "@/lib/api";
import type { Me } from "@/lib/types";

const NAV = [
  { href: "/dashboard", label: "Overview" },
  { href: "/inbox", label: "Inbox" },
  { href: "/leads", label: "Leads" },
  { href: "/campaigns", label: "Campaigns" },
  { href: "/kb", label: "Knowledge Base" },
  { href: "/agents", label: "Agents" },
  { href: "/contacts", label: "Contacts" },
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
    <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", minHeight: "100vh" }}>
      <aside
        style={{
          background: "#0f141b",
          borderRight: "1px solid var(--border)",
          padding: "1.25rem 0.75rem",
          display: "flex",
          flexDirection: "column"
        }}
      >
        <div style={{ padding: "0 0.5rem 1rem" }}>
          <div style={{ fontWeight: 700, fontSize: "1rem" }}>Terra Rex</div>
          <div className="muted small">WhatsApp agent</div>
        </div>
        <nav style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {NAV.map((n) => {
            const active = pathname?.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                style={{
                  padding: "0.45rem 0.7rem",
                  borderRadius: 6,
                  color: active ? "var(--accent)" : "var(--text)",
                  background: active ? "#1d1a10" : "transparent",
                  fontSize: "0.9rem"
                }}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div style={{ marginTop: "auto", fontSize: "0.78rem", color: "var(--muted)" }}>
          <div>{me.name}</div>
          <div>{me.email}</div>
          <div className="pill" style={{ marginTop: 6 }}>{me.role}</div>
          <button
            style={{ marginTop: 12, width: "100%" }}
            onClick={() => {
              setToken(null);
              router.replace("/login");
            }}
          >
            Log out
          </button>
        </div>
      </aside>
      <main style={{ padding: "1.5rem", overflow: "auto" }}>{children}</main>
    </div>
  );
}
