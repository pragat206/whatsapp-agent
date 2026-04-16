"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@terrarex.local");
  const [password, setPassword] = useState("admin123");
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
    <div style={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
      <form onSubmit={submit} className="card col" style={{ width: 340 }}>
        <div>
          <div style={{ fontSize: "1.25rem", fontWeight: 700 }}>Terra Rex Energy</div>
          <div className="muted small">WhatsApp agent dashboard</div>
        </div>
        <label className="col" style={{ gap: 4 }}>
          <span className="small muted">Email</span>
          <input value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="col" style={{ gap: 4 }}>
          <span className="small muted">Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {err && <div style={{ color: "var(--danger)", fontSize: "0.85rem" }}>{err}</div>}
        <button className="primary" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
