"use client";
import { useEffect, useRef, useState } from "react";
import Shell from "@/components/Shell";
import StatePill from "@/components/StatePill";
import { api } from "@/lib/api";
import type {
  ConversationDetail,
  ConversationState,
  ConversationSummary,
  Page
} from "@/lib/types";

const FILTERS: {
  label: string;
  state?: ConversationState;
  unread?: boolean;
  campaign?: boolean;
}[] = [
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
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showNewChat, setShowNewChat] = useState(false);
  const [newPhone, setNewPhone] = useState("");
  const [newName, setNewName] = useState("");
  const [newBody, setNewBody] = useState("");
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const selectedIdRef = useRef<string | null>(null);

  function report(err: unknown) {
    setError(err instanceof Error ? err.message : String(err));
  }

  async function load() {
    const params = new URLSearchParams();
    if (filter.state) params.set("state", filter.state);
    if (filter.unread) params.set("unread_only", "true");
    if (filter.campaign) params.set("campaign_only", "true");
    try {
      const r = await api<Page<ConversationSummary>>(
        `/inbox/conversations?${params}`
      );
      setConvs(r.items);
    } catch (e) {
      report(e);
    }
  }

  async function open(id: string) {
    selectedIdRef.current = id;
    try {
      const r = await api<ConversationDetail>(`/inbox/conversations/${id}`);
      setSelected(r);
    } catch (e) {
      report(e);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 7000);
    return () => clearInterval(t);
  }, [filter]);

  // Poll the open conversation so AI replies / delivery updates appear live.
  useEffect(() => {
    if (!selected) return;
    const id = selected.id;
    const t = setInterval(() => {
      if (selectedIdRef.current !== id) return;
      api<ConversationDetail>(`/inbox/conversations/${id}`)
        .then((r) => {
          if (selectedIdRef.current === id) setSelected(r);
        })
        .catch(() => {
          /* silent; next tick will try again */
        });
    }, 4000);
    return () => clearInterval(t);
  }, [selected?.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [selected?.messages?.length]);

  async function act(path: string, body_: object = {}) {
    if (!selected) return;
    try {
      await api(`/inbox/conversations/${selected.id}/${path}`, {
        method: "POST",
        body: JSON.stringify(body_)
      });
      await open(selected.id);
      await load();
    } catch (e) {
      report(e);
    }
  }

  async function send() {
    if (!selected || !body.trim() || sending) return;
    setSending(true);
    try {
      await api(`/inbox/conversations/${selected.id}/messages`, {
        method: "POST",
        body: JSON.stringify({ body })
      });
      setBody("");
      await open(selected.id);
      await load();
    } catch (e) {
      report(e);
    } finally {
      setSending(false);
    }
  }

  async function startChat(e: React.FormEvent) {
    e.preventDefault();
    if (!newPhone.trim() || !newBody.trim() || sending) return;
    setSending(true);
    try {
      const r = await api<ConversationDetail>("/inbox/start", {
        method: "POST",
        body: JSON.stringify({
          phone: newPhone.trim(),
          name: newName.trim() || null,
          body: newBody
        })
      });
      setSelected(r);
      selectedIdRef.current = r.id;
      setShowNewChat(false);
      setNewPhone("");
      setNewName("");
      setNewBody("");
      await load();
    } catch (e) {
      report(e);
    } finally {
      setSending(false);
    }
  }

  return (
    <Shell>
      {error && (
        <div
          className="card"
          style={{
            borderColor: "var(--danger)",
            background: "var(--danger-soft)",
            color: "var(--danger-text)",
            marginBottom: 8,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}
        >
          <div className="small">{error}</div>
          <button className="small" onClick={() => setError(null)}>
            dismiss
          </button>
        </div>
      )}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "320px 1fr 280px",
          gap: 16,
          height: "calc(100vh - 3rem)"
        }}
      >
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
          <button
            className="primary"
            style={{ fontSize: "0.8rem" }}
            onClick={() => setShowNewChat(true)}
          >
            + New chat
          </button>
          <div style={{ overflow: "auto", flex: 1 }}>
            {convs.map((c) => (
              <div
                key={c.id}
                onClick={() => open(c.id)}
                style={{
                  padding: "0.7rem 0.5rem",
                  borderBottom: "1px solid var(--border)",
                  cursor: "pointer",
                  background:
                    selected?.id === c.id ? "var(--panel-selected)" : "transparent"
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <strong style={{ fontSize: "0.9rem" }}>
                    {c.contact.name || c.contact.phone_e164}
                  </strong>
                  <StatePill state={c.state} />
                </div>
                <div
                  className="muted small"
                  style={{
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis"
                  }}
                >
                  {c.last_message_preview || "—"}
                </div>
                {c.source_campaign_id && (
                  <span className="pill" style={{ marginTop: 4 }}>
                    campaign
                  </span>
                )}
                {c.unread_count > 0 && (
                  <span className="pill" style={{ marginTop: 4, marginLeft: 6 }}>
                    {c.unread_count} new
                  </span>
                )}
              </div>
            ))}
            {convs.length === 0 && (
              <div className="muted small" style={{ padding: 12 }}>
                No conversations.
              </div>
            )}
          </div>
        </div>

        <div className="card col" style={{ overflow: "hidden" }}>
          {!selected ? (
            <div className="muted">Select a conversation or start a new chat.</div>
          ) : (
            <>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <strong>{selected.contact.name || selected.contact.phone_e164}</strong>
                <StatePill state={selected.state} />
                <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                  <button onClick={() => act("takeover")}>Take over</button>
                  <button onClick={() => act("pause-ai", { reason: "manual" })}>
                    Pause AI
                  </button>
                  <button onClick={() => act("resume-ai")}>Resume AI</button>
                  <button onClick={() => act("close")}>Close</button>
                </div>
              </div>
              <div
                style={{
                  flex: 1,
                  overflow: "auto",
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  padding: "8px 0"
                }}
              >
                {selected.messages.map((m) => (
                  <div
                    key={m.id}
                    style={{
                      alignSelf: m.direction === "inbound" ? "flex-start" : "flex-end",
                      background:
                        m.direction === "inbound"
                          ? "var(--bubble-in)"
                          : m.sender_kind === "ai"
                          ? "var(--info-soft)"
                          : "var(--bubble-out)",
                      color: "var(--text)",
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
                <div ref={messagesEndRef} />
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
                  disabled={sending}
                />
                <button
                  className="primary"
                  onClick={send}
                  disabled={sending || !body.trim()}
                >
                  {sending ? "Sending…" : "Send"}
                </button>
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

      {showNewChat && (
        <div
          onClick={() => setShowNewChat(false)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100
          }}
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={startChat}
            className="card col"
            style={{ width: 420 }}
          >
            <div style={{ fontWeight: 600 }}>Start a new chat</div>
            <div className="small muted">
              The recipient must have messaged you in the last 24 hours, or you must
              use an approved template campaign for cold outreach.
            </div>
            <input
              placeholder="Phone (e.g. +91 98xxxxxxxx)"
              value={newPhone}
              onChange={(e) => setNewPhone(e.target.value)}
              required
            />
            <input
              placeholder="Name (optional)"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <textarea
              rows={3}
              placeholder="Message"
              value={newBody}
              onChange={(e) => setNewBody(e.target.value)}
              required
            />
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button type="button" onClick={() => setShowNewChat(false)}>
                Cancel
              </button>
              <button
                className="primary"
                type="submit"
                disabled={sending || !newPhone.trim() || !newBody.trim()}
              >
                {sending ? "Sending…" : "Send"}
              </button>
            </div>
          </form>
        </div>
      )}
    </Shell>
  );
}
