"use client";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import StatePill from "@/components/StatePill";
import { api } from "@/lib/api";
import type {
  ConversationDetail,
  ConversationState,
  ConversationSummary,
  Page
} from "@/lib/types";

const FILTERS: { label: string; state?: ConversationState; unread?: boolean; campaign?: boolean }[] = [
  { label: "All" },
  { label: "Unread", unread: true },
  { label: "AI active", state: "AI_ACTIVE" },
  { label: "Paused", state: "AI_PAUSED" },
  { label: "Human", state: "HUMAN_ACTIVE" },
  { label: "Campaign replies", campaign: true }
];

export default function InboxPage() {
  const [filter, setFilter] = useState(FILTERS[0]);
  const [convs, setConvs] = useState<ConversationSummary[]>([]);
  const [selected, setSelected] = useState<ConversationDetail | null>(null);
  const [body, setBody] = useState("");

  async function load() {
    const params = new URLSearchParams();
    if (filter.state) params.set("state", filter.state);
    if (filter.unread) params.set("unread_only", "true");
    if (filter.campaign) params.set("campaign_only", "true");
    const r = await api<Page<ConversationSummary>>(`/inbox/conversations?${params}`);
    setConvs(r.items);
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 7000);
    return () => clearInterval(t);
  }, [filter]);

  async function open(id: string) {
    const r = await api<ConversationDetail>(`/inbox/conversations/${id}`);
    setSelected(r);
  }

  async function act(path: string, body_: object = {}) {
    if (!selected) return;
    await api(`/inbox/conversations/${selected.id}/${path}`, {
      method: "POST",
      body: JSON.stringify(body_)
    });
    await open(selected.id);
    await load();
  }

  async function send() {
    if (!selected || !body.trim()) return;
    await api(`/inbox/conversations/${selected.id}/messages`, {
      method: "POST",
      body: JSON.stringify({ body })
    });
    setBody("");
    await open(selected.id);
    await load();
  }

  return (
    <Shell>
      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr 280px", gap: 16, height: "calc(100vh - 3rem)" }}>
        <div className="card col" style={{ overflow: "hidden" }}>
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {FILTERS.map((f, i) => (
              <button
                key={i}
                className={f === filter ? "primary" : ""}
                onClick={() => setFilter(f)}
                style={{ fontSize: "0.75rem", padding: "0.25rem 0.55rem" }}
              >
                {f.label}
              </button>
            ))}
          </div>
          <div style={{ overflow: "auto", flex: 1 }}>
            {convs.map((c) => (
              <div
                key={c.id}
                onClick={() => open(c.id)}
                style={{
                  padding: "0.7rem 0.5rem",
                  borderBottom: "1px solid var(--border)",
                  cursor: "pointer",
                  background: selected?.id === c.id ? "#1a2332" : "transparent"
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <strong style={{ fontSize: "0.9rem" }}>
                    {c.contact.name || c.contact.phone_e164}
                  </strong>
                  <StatePill state={c.state} />
                </div>
                <div className="muted small" style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {c.last_message_preview || "—"}
                </div>
                {c.source_campaign_id && (
                  <span className="pill" style={{ marginTop: 4 }}>campaign</span>
                )}
              </div>
            ))}
            {convs.length === 0 && <div className="muted small" style={{ padding: 12 }}>No conversations.</div>}
          </div>
        </div>

        <div className="card col" style={{ overflow: "hidden" }}>
          {!selected ? (
            <div className="muted">Select a conversation.</div>
          ) : (
            <>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <strong>{selected.contact.name || selected.contact.phone_e164}</strong>
                <StatePill state={selected.state} />
                <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                  <button onClick={() => act("takeover")}>Take over</button>
                  <button onClick={() => act("pause-ai", { reason: "manual" })}>Pause AI</button>
                  <button onClick={() => act("resume-ai")}>Resume AI</button>
                  <button onClick={() => act("close")}>Close</button>
                </div>
              </div>
              <div style={{ flex: 1, overflow: "auto", display: "flex", flexDirection: "column", gap: 6, padding: "8px 0" }}>
                {selected.messages.map((m) => (
                  <div
                    key={m.id}
                    style={{
                      alignSelf: m.direction === "inbound" ? "flex-start" : "flex-end",
                      background: m.direction === "inbound" ? "#1e293b" : m.sender_kind === "ai" ? "#2b1d57" : "#14532d",
                      padding: "0.5rem 0.7rem",
                      borderRadius: 8,
                      maxWidth: "70%",
                      fontSize: "0.9rem",
                      whiteSpace: "pre-wrap"
                    }}
                  >
                    <div className="muted small" style={{ marginBottom: 2 }}>
                      {m.direction === "inbound" ? "user" : m.sender_kind} · {m.status}
                    </div>
                    {m.body}
                  </div>
                ))}
              </div>
              <div className="row">
                <input
                  placeholder={
                    selected.state === "HUMAN_ACTIVE"
                      ? "Type reply (AI is paused)…"
                      : "Type reply — sending will take over from AI"
                  }
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      send();
                    }
                  }}
                />
                <button className="primary" onClick={send}>Send</button>
              </div>
            </>
          )}
        </div>

        <div className="card col">
          <div style={{ fontWeight: 600 }}>Contact</div>
          {selected && (
            <>
              <div className="small muted">Phone</div>
              <div>{selected.contact.phone_e164}</div>
              <div className="small muted">Name</div>
              <div>{selected.contact.name || "—"}</div>
              <div className="small muted">City</div>
              <div>{selected.contact.city || "—"}</div>
              <div className="small muted">Campaign</div>
              <div>{selected.source_campaign_id || "—"}</div>
              <div className="small muted">Unsubscribed</div>
              <div>{selected.contact.unsubscribed ? "yes" : "no"}</div>
            </>
          )}
        </div>
      </div>
    </Shell>
  );
}
