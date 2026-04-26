"use client";
import { useEffect, useRef, useState } from "react";
import Shell from "@/components/Shell";
import StatePill from "@/components/StatePill";
import Avatar from "@/components/Avatar";
import MessageStatusIcon from "@/components/MessageStatusIcon";
import { api } from "@/lib/api";
import { formatDateLabel, formatListTimestamp, formatTime, isSameDay } from "@/lib/time";
import type {
  ConversationDetail,
  ConversationState,
  ConversationSummary,
  Message,
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
  { label: "AI", state: "AI_ACTIVE" },
  { label: "Paused", state: "AI_PAUSED" },
  { label: "Human", state: "HUMAN_ACTIVE" },
  { label: "Campaigns", campaign: true }
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
  const [menuOpen, setMenuOpen] = useState(false);
  const [showInfo, setShowInfo] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
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
    setMenuOpen(false);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    const container = messagesContainerRef.current;
    if (!container) return;
    container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  }, [selected?.messages?.length, selected?.id]);

  // Close kebab menu when clicking outside.
  useEffect(() => {
    if (!menuOpen) return;
    const handler = () => setMenuOpen(false);
    window.addEventListener("click", handler);
    return () => window.removeEventListener("click", handler);
  }, [menuOpen]);

  async function act(path: string, body_: object = {}) {
    if (!selected) return;
    setMenuOpen(false);
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
            marginBottom: 12,
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
          gridTemplateColumns: showInfo ? "320px 1fr 280px" : "320px 1fr",
          gridTemplateRows: "minmax(0, 1fr)",
          gap: 0,
          height: "calc(100vh - 3rem)",
          border: "1px solid var(--border)",
          borderRadius: 10,
          overflow: "hidden",
          background: "var(--panel)"
        }}
      >
        {/* ============= Conversations list ============= */}
        <aside
          style={{
            display: "flex",
            flexDirection: "column",
            borderRight: "1px solid var(--border)",
            minWidth: 0,
            minHeight: 0,
            height: "100%",
            background: "var(--bg-soft)"
          }}
        >
          <div
            style={{
              padding: "12px 12px 8px",
              borderBottom: "1px solid var(--border)"
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 8
              }}
            >
              <div style={{ fontWeight: 700, fontSize: "1rem" }}>Chats</div>
              <button
                onClick={() => setShowNewChat(true)}
                style={{ padding: "0.3rem 0.6rem", fontSize: "0.8rem" }}
                title="Start a new chat"
              >
                + New
              </button>
            </div>
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {FILTERS.map((f, i) => (
                <button
                  key={i}
                  className={f === filter ? "primary" : ""}
                  onClick={() => setFilter(f)}
                  style={{
                    fontSize: "0.72rem",
                    padding: "0.22rem 0.55rem",
                    borderRadius: 999
                  }}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          <div style={{ overflowY: "auto", flex: 1, minHeight: 0 }}>
            {convs.map((c) => {
              const active = selected?.id === c.id;
              const unread = c.unread_count > 0;
              const lastAt =
                c.last_inbound_at || c.last_outbound_at || c.updated_at;
              return (
                <div
                  key={c.id}
                  onClick={() => open(c.id)}
                  style={{
                    display: "flex",
                    gap: 10,
                    padding: "10px 12px",
                    cursor: "pointer",
                    background: active ? "var(--panel-selected)" : "transparent",
                    borderBottom: "1px solid var(--border)",
                    transition: "background-color 100ms ease"
                  }}
                >
                  <Avatar name={c.contact.name} phone={c.contact.phone_e164} size={42} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        gap: 6,
                        alignItems: "baseline"
                      }}
                    >
                      <span
                        style={{
                          fontWeight: unread ? 700 : 500,
                          color: "var(--text-strong)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap"
                        }}
                      >
                        {c.contact.name || c.contact.phone_e164}
                      </span>
                      <span
                        className="small muted"
                        style={{ flexShrink: 0, fontSize: "0.7rem" }}
                      >
                        {formatListTimestamp(lastAt)}
                      </span>
                    </div>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        gap: 6,
                        alignItems: "center",
                        marginTop: 2
                      }}
                    >
                      <span
                        className={unread ? "" : "muted"}
                        style={{
                          fontSize: "0.82rem",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          flex: 1,
                          color: unread ? "var(--text)" : "var(--muted)",
                          fontWeight: unread ? 500 : 400
                        }}
                      >
                        {c.last_message_preview || "—"}
                      </span>
                      <span
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 4,
                          flexShrink: 0
                        }}
                      >
                        {c.source_campaign_id && (
                          <span
                            className="pill"
                            style={{ fontSize: "0.62rem", padding: "0.05rem 0.4rem" }}
                          >
                            campaign
                          </span>
                        )}
                        {unread && (
                          <span
                            style={{
                              background: "var(--accent)",
                              color: "var(--accent-text)",
                              borderRadius: 999,
                              padding: "0.05rem 0.45rem",
                              fontSize: "0.7rem",
                              fontWeight: 700,
                              minWidth: 18,
                              textAlign: "center"
                            }}
                          >
                            {c.unread_count}
                          </span>
                        )}
                        <StatePill state={c.state} />
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
            {convs.length === 0 && (
              <div className="muted small" style={{ padding: 16, textAlign: "center" }}>
                No conversations match this filter.
              </div>
            )}
          </div>
        </aside>

        {/* ============= Chat panel ============= */}
        <section
          style={{
            display: "flex",
            flexDirection: "column",
            minWidth: 0,
            minHeight: 0,
            height: "100%",
            background: "var(--bg)"
          }}
        >
          {!selected ? (
            <EmptyChatState />
          ) : (
            <>
              {/* Sticky chat header */}
              <header
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 14px",
                  borderBottom: "1px solid var(--border)",
                  background: "var(--bg-soft)",
                  position: "relative"
                }}
              >
                <Avatar
                  name={selected.contact.name}
                  phone={selected.contact.phone_e164}
                  size={40}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontWeight: 600,
                      color: "var(--text-strong)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap"
                    }}
                  >
                    {selected.contact.name || selected.contact.phone_e164}
                  </div>
                  <div
                    className="muted small"
                    style={{
                      fontSize: "0.78rem",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap"
                    }}
                  >
                    {selected.contact.phone_e164}
                    {selected.contact.city ? ` · ${selected.contact.city}` : ""}
                  </div>
                </div>
                <StatePill state={selected.state} />
                <button
                  onClick={() => setShowInfo((v) => !v)}
                  className={showInfo ? "primary" : ""}
                  style={{ fontSize: "0.78rem", padding: "0.3rem 0.6rem" }}
                  title="Toggle contact details"
                >
                  Info
                </button>
                <div style={{ position: "relative" }}>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setMenuOpen((v) => !v);
                    }}
                    aria-label="Conversation actions"
                    style={{
                      padding: "0.3rem 0.55rem",
                      fontSize: "1rem",
                      lineHeight: 1
                    }}
                  >
                    ⋮
                  </button>
                  {menuOpen && (
                    <div
                      onClick={(e) => e.stopPropagation()}
                      style={{
                        position: "absolute",
                        right: 0,
                        top: "calc(100% + 4px)",
                        background: "var(--panel)",
                        border: "1px solid var(--border)",
                        borderRadius: 8,
                        minWidth: 180,
                        boxShadow: "var(--shadow)",
                        zIndex: 20,
                        overflow: "hidden"
                      }}
                    >
                      <MenuItem
                        label="Take over"
                        disabled={selected.state === "HUMAN_ACTIVE"}
                        onClick={() => act("takeover")}
                      />
                      <MenuItem
                        label="Pause AI"
                        disabled={selected.state === "AI_PAUSED"}
                        onClick={() => act("pause-ai", { reason: "manual" })}
                      />
                      <MenuItem
                        label="Resume AI"
                        disabled={selected.state === "AI_ACTIVE"}
                        onClick={() => act("resume-ai")}
                      />
                      <MenuItem
                        label="Close conversation"
                        disabled={selected.state === "CLOSED"}
                        onClick={() => act("close")}
                      />
                    </div>
                  )}
                </div>
              </header>

              {/* Messages */}
              <div
                ref={messagesContainerRef}
                style={{
                  flex: 1,
                  minHeight: 0,
                  overflowY: "auto",
                  display: "flex",
                  flexDirection: "column",
                  padding: "14px 16px",
                  gap: 4
                }}
              >
                {selected.messages.length === 0 && (
                  <div className="muted small" style={{ textAlign: "center", marginTop: 24 }}>
                    No messages yet.
                  </div>
                )}
                {selected.messages.map((m, i) => {
                  const prev = selected.messages[i - 1];
                  const showDateSeparator =
                    !prev || !isSameDay(prev.created_at, m.created_at);
                  return (
                    <div key={m.id}>
                      {showDateSeparator && (
                        <DateSeparator label={formatDateLabel(m.created_at)} />
                      )}
                      <Bubble m={m} />
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>

              {/* Composer */}
              <Composer
                disabled={sending}
                value={body}
                onChange={setBody}
                onSubmit={send}
                placeholder={
                  selected.state === "HUMAN_ACTIVE"
                    ? "Type a message…"
                    : "Type a message — sending will pause the AI"
                }
                textareaRef={composerRef}
                sending={sending}
              />
            </>
          )}
        </section>

        {/* ============= Contact info side panel ============= */}
        {showInfo && selected && (
          <aside
            style={{
              borderLeft: "1px solid var(--border)",
              padding: "16px",
              overflow: "auto",
              background: "var(--bg-soft)"
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
              <Avatar
                name={selected.contact.name}
                phone={selected.contact.phone_e164}
                size={72}
              />
              <div
                style={{
                  fontWeight: 600,
                  fontSize: "1.05rem",
                  color: "var(--text-strong)",
                  textAlign: "center"
                }}
              >
                {selected.contact.name || selected.contact.phone_e164}
              </div>
              <StatePill state={selected.state} />
            </div>

            <div style={{ marginTop: 18, display: "flex", flexDirection: "column", gap: 10 }}>
              <InfoRow label="Phone" value={selected.contact.phone_e164} />
              <InfoRow label="Name" value={selected.contact.name || "—"} />
              <InfoRow label="City" value={selected.contact.city || "—"} />
              <InfoRow
                label="Campaign"
                value={selected.source_campaign_id || "—"}
              />
              <InfoRow
                label="Unsubscribed"
                value={selected.contact.unsubscribed ? "yes" : "no"}
              />
              <InfoRow
                label="Last inbound"
                value={
                  selected.last_inbound_at
                    ? new Date(selected.last_inbound_at).toLocaleString()
                    : "—"
                }
              />
            </div>
          </aside>
        )}
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
            zIndex: 100,
            padding: 16
          }}
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={startChat}
            className="card col"
            style={{ width: "min(420px, 100%)" }}
          >
            <div style={{ fontWeight: 600 }}>Start a new chat</div>
            <div className="small muted">
              The recipient must have messaged you in the last 24 hours, or you
              must use an approved template campaign for cold outreach.
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

/* --------------------- Subcomponents --------------------- */

function EmptyChatState() {
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        textAlign: "center",
        padding: 24,
        color: "var(--muted)"
      }}
    >
      <div
        style={{
          width: 60,
          height: 60,
          borderRadius: "50%",
          background: "var(--panel-hover)",
          display: "grid",
          placeItems: "center",
          fontSize: 28
        }}
        aria-hidden
      >
        💬
      </div>
      <div style={{ fontWeight: 600, color: "var(--text)" }}>No chat selected</div>
      <div className="small">
        Pick a conversation from the list or start a new chat.
      </div>
    </div>
  );
}

function DateSeparator({ label }: { label: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        margin: "12px 0 6px"
      }}
    >
      <span
        style={{
          background: "var(--panel-hover)",
          color: "var(--muted)",
          fontSize: "0.72rem",
          padding: "0.18rem 0.7rem",
          borderRadius: 999,
          letterSpacing: 0.3,
          textTransform: "uppercase"
        }}
      >
        {label}
      </span>
    </div>
  );
}

function Bubble({ m }: { m: Message }) {
  const inbound = m.direction === "inbound";
  const ai = m.sender_kind === "ai";
  const failed = m.status === "failed";
  return (
    <div
      style={{
        display: "flex",
        justifyContent: inbound ? "flex-start" : "flex-end",
        margin: "2px 0"
      }}
    >
      <div
        style={{
          maxWidth: "min(72%, 540px)",
          background: failed
            ? "var(--danger-soft)"
            : inbound
            ? "var(--bubble-in)"
            : ai
            ? "var(--info-soft)"
            : "var(--bubble-out)",
          color: failed ? "var(--danger-text)" : "var(--text)",
          padding: "0.5rem 0.7rem 0.35rem",
          borderRadius: 10,
          borderTopLeftRadius: inbound ? 4 : 10,
          borderTopRightRadius: inbound ? 10 : 4,
          fontSize: "0.92rem",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          boxShadow: "0 1px 0 rgba(0,0,0,0.05)"
        }}
      >
        {!inbound && ai && (
          <div
            className="small"
            style={{
              fontWeight: 600,
              color: "var(--info-text)",
              marginBottom: 2,
              fontSize: "0.7rem",
              letterSpacing: 0.3,
              textTransform: "uppercase"
            }}
          >
            AI
          </div>
        )}
        <div>{m.body}</div>
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            gap: 5,
            marginTop: 3,
            fontSize: "0.68rem",
            color: "var(--muted)"
          }}
        >
          <span>{formatTime(m.created_at)}</span>
          {!inbound && <MessageStatusIcon status={m.status} />}
        </div>
      </div>
    </div>
  );
}

function Composer({
  disabled,
  value,
  onChange,
  onSubmit,
  placeholder,
  textareaRef,
  sending
}: {
  disabled: boolean;
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  placeholder: string;
  textareaRef: React.RefObject<HTMLTextAreaElement>;
  sending: boolean;
}) {
  // Auto-grow up to ~6 lines.
  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    onChange(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }
  return (
    <div
      style={{
        borderTop: "1px solid var(--border)",
        padding: "10px 12px",
        background: "var(--bg-soft)",
        display: "flex",
        gap: 8,
        alignItems: "flex-end"
      }}
    >
      <textarea
        ref={textareaRef}
        rows={1}
        placeholder={placeholder}
        value={value}
        onChange={handleInput}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSubmit();
          }
        }}
        disabled={disabled}
        style={{
          flex: 1,
          resize: "none",
          minHeight: 38,
          maxHeight: 140,
          borderRadius: 18,
          padding: "0.55rem 0.85rem",
          fontSize: "0.92rem",
          lineHeight: 1.35
        }}
      />
      <button
        onClick={onSubmit}
        disabled={disabled || !value.trim()}
        className="primary"
        title={sending ? "Sending…" : "Send (Enter)"}
        aria-label="Send message"
        style={{
          width: 40,
          height: 40,
          borderRadius: "50%",
          padding: 0,
          display: "grid",
          placeItems: "center",
          flexShrink: 0
        }}
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <path d="M22 2 11 13" />
          <path d="M22 2 15 22 11 13 2 9 22 2z" />
        </svg>
      </button>
    </div>
  );
}

function MenuItem({
  label,
  onClick,
  disabled
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "block",
        width: "100%",
        textAlign: "left",
        background: "transparent",
        border: "none",
        borderRadius: 0,
        padding: "0.55rem 0.9rem",
        fontSize: "0.88rem",
        color: disabled ? "var(--muted)" : "var(--text)",
        cursor: disabled ? "default" : "pointer"
      }}
      onMouseEnter={(e) => {
        if (!disabled) e.currentTarget.style.background = "var(--panel-hover)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
      }}
    >
      {label}
    </button>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="muted small" style={{ fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: 0.4 }}>
        {label}
      </div>
      <div style={{ fontSize: "0.9rem", marginTop: 2, wordBreak: "break-word" }}>
        {value}
      </div>
    </div>
  );
}
