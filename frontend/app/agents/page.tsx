"use client";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api } from "@/lib/api";

type Agent = {
  id: string;
  name: string;
  purpose: string;
  tone: string;
  response_style: string;
  languages_supported: string[];
  greeting_style: string;
  escalation_keywords: string[];
  forbidden_claims: string[];
  fallback_message: string;
  human_handoff_message: string;
  instructions: string;
  is_default: boolean;
};

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [active, setActive] = useState<Agent | null>(null);

  async function load() {
    const r = await api<Agent[]>("/agents");
    setAgents(r);
    if (!active && r[0]) setActive(r[0]);
    else if (active) setActive(r.find((a) => a.id === active.id) || r[0] || null);
  }

  useEffect(() => { load(); }, []);

  async function save() {
    if (!active) return;
    await api(`/agents/${active.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        purpose: active.purpose,
        tone: active.tone,
        response_style: active.response_style,
        languages_supported: active.languages_supported,
        greeting_style: active.greeting_style,
        escalation_keywords: active.escalation_keywords,
        forbidden_claims: active.forbidden_claims,
        fallback_message: active.fallback_message,
        human_handoff_message: active.human_handoff_message,
        instructions: active.instructions,
        is_default: active.is_default
      })
    });
    load();
  }

  return (
    <Shell>
      <h2>Agent profiles</h2>
      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 16 }}>
        <div className="card col">
          {agents.map((a) => (
            <div
              key={a.id}
              onClick={() => setActive(a)}
              style={{ padding: 6, borderRadius: 6, cursor: "pointer", background: active?.id === a.id ? "#1a2332" : "transparent" }}
            >
              {a.name} {a.is_default && <span className="pill">default</span>}
            </div>
          ))}
        </div>
        {active && (
          <div className="card col">
            <Field label="Purpose">
              <textarea rows={2} value={active.purpose} onChange={(e) => setActive({ ...active, purpose: e.target.value })} />
            </Field>
            <Field label="Tone"><input value={active.tone} onChange={(e) => setActive({ ...active, tone: e.target.value })} /></Field>
            <Field label="Response style"><input value={active.response_style} onChange={(e) => setActive({ ...active, response_style: e.target.value })} /></Field>
            <Field label="Greeting"><input value={active.greeting_style} onChange={(e) => setActive({ ...active, greeting_style: e.target.value })} /></Field>
            <Field label="Languages (csv)">
              <input
                value={active.languages_supported.join(",")}
                onChange={(e) => setActive({ ...active, languages_supported: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) })}
              />
            </Field>
            <Field label="Escalation keywords (csv)">
              <input
                value={active.escalation_keywords.join(",")}
                onChange={(e) => setActive({ ...active, escalation_keywords: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) })}
              />
            </Field>
            <Field label="Forbidden claims (one per line)">
              <textarea rows={3}
                value={active.forbidden_claims.join("\n")}
                onChange={(e) => setActive({ ...active, forbidden_claims: e.target.value.split("\n").map((x) => x.trim()).filter(Boolean) })}
              />
            </Field>
            <Field label="Fallback message">
              <textarea rows={2} value={active.fallback_message} onChange={(e) => setActive({ ...active, fallback_message: e.target.value })} />
            </Field>
            <Field label="Human handoff message">
              <textarea rows={2} value={active.human_handoff_message} onChange={(e) => setActive({ ...active, human_handoff_message: e.target.value })} />
            </Field>
            <Field label="Instructions (system prompt addendum)">
              <textarea rows={5} value={active.instructions} onChange={(e) => setActive({ ...active, instructions: e.target.value })} />
            </Field>
            <label className="row" style={{ alignItems: "center", gap: 6 }}>
              <input type="checkbox" checked={active.is_default}
                onChange={(e) => setActive({ ...active, is_default: e.target.checked })}
                style={{ width: "auto" }} />
              <span>Default agent</span>
            </label>
            <button className="primary" onClick={save}>Save</button>
          </div>
        )}
      </div>
    </Shell>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="col" style={{ gap: 4 }}>
      <span className="small muted">{label}</span>
      {children}
    </label>
  );
}
