"use client";
/**
 * Documents — single-pane browser for every customer-shared attachment.
 *
 * The Inbox renders attachments inside each conversation, which is great
 * for chat context but bad for triage ("show me every electricity bill
 * uploaded today"). This page lists each inbound file with the sender's
 * name, phone, timestamp, and a thumbnail/preview, with filtering by
 * media kind and contact text search.
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import MediaAttachment from "@/components/MediaAttachment";
import Shell from "@/components/Shell";
import { api } from "@/lib/api";
import { formatListTimestamp } from "@/lib/time";
import type { Message, Page as PageT } from "@/lib/types";

type Kind = "image" | "document" | "audio" | "video";

interface DocumentEntry {
  message_id: string;
  conversation_id: string;
  contact_id: string;
  contact_name: string | null;
  contact_phone: string;
  media_type: string | null;
  local_media_path: string | null;
  media_url: string | null;
  body_preview: string;
  created_at: string;
}

const KINDS: { label: string; value: Kind | "" }[] = [
  { label: "All", value: "" },
  { label: "Images", value: "image" },
  { label: "Documents", value: "document" },
  { label: "Voice / audio", value: "audio" },
  { label: "Video", value: "video" }
];

export default function DocumentsPage() {
  const [kind, setKind] = useState<Kind | "">("");
  const [q, setQ] = useState("");
  const [qDebounced, setQDebounced] = useState("");
  const [items, setItems] = useState<DocumentEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  // Debounce search input so we're not blasting the API on every keystroke.
  useEffect(() => {
    const id = setTimeout(() => setQDebounced(q.trim()), 250);
    return () => clearTimeout(id);
  }, [q]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (kind) params.set("kind", kind);
    if (qDebounced) params.set("q", qDebounced);
    params.set("limit", "100");
    setLoading(true);
    setErr(null);
    api<PageT<DocumentEntry>>(`/documents?${params}`)
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [kind, qDebounced]);

  return (
    <Shell>
      <header style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 18 }}>
        <h1 style={{ margin: 0, fontSize: "1.4rem" }}>Documents</h1>
        <div className="muted small">
          Files customers have shared with the chatbot on WhatsApp —
          electricity bills, Aadhaar, photos, voice notes.
        </div>
      </header>

      <div
        className="card"
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          alignItems: "center",
          marginBottom: 14
        }}
      >
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {KINDS.map((k) => (
            <button
              key={k.value || "all"}
              onClick={() => setKind(k.value)}
              className={kind === k.value ? "primary" : ""}
              style={{ fontSize: "0.85rem" }}
            >
              {k.label}
            </button>
          ))}
        </div>
        <input
          placeholder="Search by name or phone"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ flex: "1 1 220px", minWidth: 200 }}
        />
        <div className="muted small">
          {loading ? "Loading…" : `${items.length} of ${total} shown`}
        </div>
      </div>

      {err && (
        <div
          className="card"
          style={{
            color: "var(--danger-text)",
            background: "var(--danger-soft)",
            borderColor: "var(--danger-text)",
            marginBottom: 14
          }}
        >
          {err}
        </div>
      )}

      {!loading && items.length === 0 && !err && (
        <div className="card muted" style={{ padding: "1.25rem" }}>
          No documents yet. Anything customers share on WhatsApp (bills,
          Aadhaar photos, voice notes) will appear here automatically.
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
          gap: 14
        }}
      >
        {items.map((d) => (
          <DocumentCard key={d.message_id} entry={d} />
        ))}
      </div>
    </Shell>
  );
}

function DocumentCard({ entry }: { entry: DocumentEntry }) {
  // MediaAttachment expects a Message shape; build the minimal one we need.
  const synthetic: Message = {
    id: entry.message_id,
    conversation_id: entry.conversation_id,
    direction: "inbound",
    sender_kind: "user",
    body: entry.body_preview,
    media_url: entry.media_url,
    media_type: entry.media_type,
    local_media_path: entry.local_media_path,
    status: "received",
    created_at: entry.created_at
  };
  const senderLabel = entry.contact_name?.trim() || entry.contact_phone || "Unknown";
  return (
    <div
      className="card"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        padding: "0.85rem"
      }}
    >
      <MediaAttachment message={synthetic} />
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <div style={{ fontWeight: 600, fontSize: "0.92rem" }}>{senderLabel}</div>
        {entry.contact_name && (
          <div className="muted small">{entry.contact_phone}</div>
        )}
        <div className="muted small" style={{ fontSize: "0.72rem" }}>
          {formatListTimestamp(entry.created_at)}
        </div>
      </div>
      {entry.body_preview && (
        <div
          className="small"
          style={{
            color: "var(--muted)",
            fontStyle: "italic",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis"
          }}
        >
          “{entry.body_preview}”
        </div>
      )}
      <Link
        href={`/inbox?conversation=${entry.conversation_id}`}
        className="small"
        style={{ marginTop: 4 }}
      >
        Open conversation →
      </Link>
    </div>
  );
}
