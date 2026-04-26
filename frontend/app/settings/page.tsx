"use client";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api } from "@/lib/api";

export default function SettingsPage() {
  const [items, setItems] = useState<Record<string, any>>({});
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setItems(await api<Record<string, any>>("/settings"));
  }

  useEffect(() => { load(); }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const parsed = JSON.parse(value);
      await api(`/settings/${encodeURIComponent(key)}`, {
        method: "PUT",
        body: JSON.stringify({ value: parsed })
      });
      setKey("");
      setValue("");
      load();
    } catch (ex: any) {
      setError(ex.message);
    }
  }

  return (
    <Shell>
      <h2>Settings</h2>
      <div className="card col" style={{ maxWidth: 600 }}>
        <form onSubmit={save} className="col">
          <div className="small muted">All settings are JSON values. Use this page to tune runtime business rules without redeploying.</div>
          <input placeholder="key (e.g. default_campaign_source)" value={key} onChange={(e) => setKey(e.target.value)} />
          <textarea placeholder='JSON value, e.g. {"enabled": true}' rows={3} value={value} onChange={(e) => setValue(e.target.value)} />
          {error && <div style={{ color: "var(--danger)" }} className="small">{error}</div>}
          <button className="primary">Save</button>
        </form>
        <pre
          className="small muted"
          style={{
            whiteSpace: "pre-wrap",
            background: "var(--bg-soft)",
            border: "1px solid var(--border)",
            padding: 12,
            borderRadius: 6
          }}
        >
          {JSON.stringify(items, null, 2)}
        </pre>
      </div>
    </Shell>
  );
}
