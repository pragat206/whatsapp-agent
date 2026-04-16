"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Shell from "@/components/Shell";
import { api } from "@/lib/api";
import type { Campaign, Page } from "@/lib/types";

export default function CampaignsPage() {
  const [items, setItems] = useState<Campaign[]>([]);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [template, setTemplate] = useState("");
  const [objective, setObjective] = useState("");

  async function load() {
    const r = await api<Page<Campaign>>("/campaigns");
    setItems(r.items);
  }

  useEffect(() => {
    load();
  }, []);

  async function createCampaign(e: React.FormEvent) {
    e.preventDefault();
    await api("/campaigns", {
      method: "POST",
      body: JSON.stringify({
        name,
        objective,
        template_name: template,
        template_params_schema: []
      })
    });
    setName("");
    setTemplate("");
    setObjective("");
    setCreating(false);
    load();
  }

  return (
    <Shell>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Campaigns</h2>
        <button className="primary" onClick={() => setCreating((v) => !v)}>
          {creating ? "Cancel" : "New campaign"}
        </button>
      </div>
      {creating && (
        <form onSubmit={createCampaign} className="card col" style={{ marginTop: 12, maxWidth: 520 }}>
          <label className="col small muted">Name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label className="col small muted">Approved template name (from AiSensy)
            <input value={template} onChange={(e) => setTemplate(e.target.value)} required />
          </label>
          <label className="col small muted">Objective
            <input value={objective} onChange={(e) => setObjective(e.target.value)} />
          </label>
          <button className="primary">Create draft</button>
        </form>
      )}

      <table className="table" style={{ marginTop: 16 }}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Template</th>
            <th>Status</th>
            <th>Created</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((c) => (
            <tr key={c.id}>
              <td>{c.name}</td>
              <td>{c.template_name}</td>
              <td><span className="pill">{c.status}</span></td>
              <td className="muted small">{new Date(c.created_at).toLocaleString()}</td>
              <td><Link href={`/campaigns/${c.id}`}>Open →</Link></td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr><td colSpan={5} className="muted small">No campaigns yet.</td></tr>
          )}
        </tbody>
      </table>
    </Shell>
  );
}
