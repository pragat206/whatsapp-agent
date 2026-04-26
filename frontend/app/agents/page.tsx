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

type Kb = {
  id: string;
  name: string;
  description?: string | null;
  published: boolean;
};

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [active, setActive] = useState<Agent | null>(null);
  const [kbs, setKbs] = useState<Kb[]>([]);
  const [attached, setAttached] = useState<Kb[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function report(err: unknown) {
    setError(err instanceof Error ? err.message : String(err));
  }

  async function loadAgents() {
    try {
      const r = await api<Agent[]>("/agents");
      setAgents(r);
      if (!active && r[0]) {
        setActive(r[0]);
      } else if (active) {
        setActive(r.find((a) => a.id === active.id) || r[0] || null);
      }
    } catch (e) {
      report(e);
    }
  }

  async function loadKbs() {
    try {
      setKbs(await api<Kb[]>("/kb"));
    } catch (e) {
      report(e);
    }
  }

  async function loadAttached() {
    if (!active) {
      setAttached([]);
      return;
    }
    try {
      setAttached(await api<Kb[]>(`/agents/${active.id}/kbs`));
    } catch (e) {
      report(e);
    }
  }

  useEffect(() => {
    loadAgents();
    loadKbs();
  }, []);
  useEffect(() => {
    loadAttached();
  }, [active?.id]);

  async function save() {
    if (!active) return;
    setBusy(true);
    try {
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
      setError("Saved.");
      await loadAgents();
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  }

  async function attachKb(kb_id: string) {
    if (!active) return;
    setBusy(true);
    try {
      await api(`/agents/${active.id}/kbs`, {
        method: "POST",
        body: JSON.stringify({ kb_id })
      });
      await loadAttached();
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  }

  async function detachKb(kb_id: string) {
    if (!active) return;
    setBusy(true);
    try {
      await api(`/agents/${active.id}/kbs/${kb_id}`, { method: "DELETE" });
      await loadAttached();
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  }

  const unattached = kbs.filter((k) => !attached.find((a) => a.id === k.id));

  return (
    <Shell>
      <h2>Agent profiles</h2>
      {error && (
        <div
          className="card"
          style={{
            borderColor: "var(--danger)",
            background: "var(--danger-soft)",
            color: "var(--danger-text)",
            marginBottom: 12
          }}
        >
          <div className="small">{error}</div>
          <button className="small" onClick={() => setError(null)}>
            dismiss
          </button>
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 16 }}>
        <div className="card col">
          {agents.map((a) => (
            <div
              key={a.id}
              onClick={() => setActive(a)}
              style={{
                padding: 6,
                borderRadius: 6,
                cursor: "pointer",
                background:
                  active?.id === a.id ? "var(--panel-selected)" : "transparent"
              }}
            >
              {a.name}{" "}
              {a.is_default && <span className="pill">default</span>}
            </div>
          ))}
        </div>
        {active && (
          <div className="col" style={{ gap: 16 }}>
            <div className="card col">
              <Field label="Purpose">
                <textarea
                  rows={2}
                  value={active.purpose}
                  onChange={(e) => setActive({ ...active, purpose: e.target.value })}
                />
              </Field>
              <Field label="Tone">
                <input
                  value={active.tone}
                  onChange={(e) => setActive({ ...active, tone: e.target.value })}
                />
              </Field>
              <Field label="Response style">
                <input
                  value={active.response_style}
                  onChange={(e) =>
                    setActive({ ...active, response_style: e.target.value })
                  }
                />
              </Field>
              <Field label="Greeting">
                <input
                  value={active.greeting_style}
                  onChange={(e) =>
                    setActive({ ...active, greeting_style: e.target.value })
                  }
                />
              </Field>
              <Field label="Languages (csv)">
                <input
                  value={active.languages_supported.join(",")}
                  onChange={(e) =>
                    setActive({
                      ...active,
                      languages_supported: e.target.value
                        .split(",")
                        .map((x) => x.trim())
                        .filter(Boolean)
                    })
                  }
                />
              </Field>
              <Field label="Escalation keywords (csv)">
                <input
                  value={active.escalation_keywords.join(",")}
                  onChange={(e) =>
                    setActive({
                      ...active,
                      escalation_keywords: e.target.value
                        .split(",")
                        .map((x) => x.trim())
                        .filter(Boolean)
                    })
                  }
                />
              </Field>
              <Field label="Forbidden claims (one per line)">
                <textarea
                  rows={3}
                  value={active.forbidden_claims.join("\n")}
                  onChange={(e) =>
                    setActive({
                      ...active,
                      forbidden_claims: e.target.value
                        .split("\n")
                        .map((x) => x.trim())
                        .filter(Boolean)
                    })
                  }
                />
              </Field>
              <Field label="Fallback message">
                <textarea
                  rows={2}
                  value={active.fallback_message}
                  onChange={(e) =>
                    setActive({ ...active, fallback_message: e.target.value })
                  }
                />
              </Field>
              <Field label="Human handoff message">
                <textarea
                  rows={2}
                  value={active.human_handoff_message}
                  onChange={(e) =>
                    setActive({ ...active, human_handoff_message: e.target.value })
                  }
                />
              </Field>
              <Field label="Instructions (system prompt addendum)">
                <textarea
                  rows={5}
                  value={active.instructions}
                  onChange={(e) =>
                    setActive({ ...active, instructions: e.target.value })
                  }
                />
              </Field>
              <label className="row" style={{ alignItems: "center", gap: 6 }}>
                <input
                  type="checkbox"
                  checked={active.is_default}
                  onChange={(e) =>
                    setActive({ ...active, is_default: e.target.checked })
                  }
                  style={{ width: "auto" }}
                />
                <span>Default agent</span>
              </label>
              <button className="primary" onClick={save} disabled={busy}>
                Save
              </button>
            </div>

            <div className="card col">
              <div style={{ fontWeight: 600 }}>Attached knowledge bases</div>
              <div className="small muted">
                These KBs are searched when this agent composes replies.
              </div>
              {attached.length === 0 && (
                <div className="muted small">
                  No KBs attached yet — the agent will answer from its prompt only.
                </div>
              )}
              <table className="table">
                <tbody>
                  {attached.map((k) => (
                    <tr key={k.id}>
                      <td>
                        <div>{k.name}</div>
                        {k.description && (
                          <div className="muted small">{k.description}</div>
                        )}
                      </td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        <button className="small" onClick={() => detachKb(k.id)}>
                          Detach
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {unattached.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <div className="small muted">Attach another KB</div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {unattached.map((k) => (
                      <button
                        key={k.id}
                        className="small"
                        disabled={busy}
                        onClick={() => attachKb(k.id)}
                      >
                        + {k.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
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
