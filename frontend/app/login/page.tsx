"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";
import BraneMindFooter from "@/components/BraneMindFooter";
import ThemeToggle from "@/components/ThemeToggle";

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
      });
      setToken(r.access_token);
      router.replace("/dashboard");
    } catch (ex: any) {
      setErr(ex.message || "login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        display: "grid",
        placeItems: "center",
        minHeight: "100vh",
        padding: "1.5rem"
      }}
    >
      <div style={{ position: "absolute", top: 16, right: 16, width: 160 }}>
        <ThemeToggle />
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 16,
          width: "100%",
          maxWidth: 360
        }}
      >
        <form onSubmit={submit} className="card col">
          <div>
            <div
              style={{
                fontSize: "1.3rem",
                fontWeight: 700,
                color: "var(--text-strong)"
              }}
            >
              Terra Rex Energy
            </div>
            <div className="muted small">WhatsApp agent dashboard</div>
          </div>
          <label className="col" style={{ gap: 4 }}>
            <span className="small muted">Email</span>
            <input
              type="email"
              autoComplete="username"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label className="col" style={{ gap: 4 }}>
            <span className="small muted">Password</span>
            <input
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {err && (
            <div
              style={{
                color: "var(--danger-text)",
                background: "var(--danger-soft)",
                border: "1px solid var(--danger)",
                padding: "0.5rem 0.7rem",
                borderRadius: 6,
                fontSize: "0.85rem"
              }}
            >
              {err}
            </div>
          )}
          <button className="primary" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <BraneMindFooter align="center" />
      </div>
    </div>
  );
}
