"use client";
import { useEffect, useMemo, useState } from "react";
import Shell from "@/components/Shell";
import { api } from "@/lib/api";
import type { Lead, LeadDetail, LeadStatus, Page } from "@/lib/types";

const STATUSES: { label: string; value: LeadStatus | "" }[] = [
  { label: "All", value: "" },
  { label: "New", value: "new" },
  { label: "Contacted", value: "contacted" },
  { label: "Interested", value: "interested" },
  { label: "Qualified", value: "qualified" },
  { label: "Hot", value: "hot" },
  { label: "Converted", value: "converted" },
  { label: "Lost", value: "lost" },
  { label: "Nurturing", value: "nurturing" }
];

const STATUS_COLORS: Record<string, { bg: string; fg: string }> = {
  new: { bg: "#1a2433", fg: "#7ab7ff" },
  contacted: { bg: "#1a2030", fg: "#9aa6c2" },
  interested: { bg: "#1f2a14", fg: "#b6db7a" },
  qualified: { bg: "#1f2a14", fg: "#cfe88c" },
  hot: { bg: "#33180f", fg: "#ff9e6a" },
  converted: { bg: "#102a1f", fg: "#6ddfa5" },
  lost: { bg: "#2b1414", fg: "#e88080" },
  nurturing: { bg: "#231a2b", fg: "#c69aff" }
};

function StatusPill({ value }: { value?: string | null }) {
  if (!value) return <span className="muted small">—</span>;
  const c = STATUS_COLORS[value] || { bg: "#1d1d1d", fg: "#ddd" };
  return (
    <span
      className="pill"
      style={{ background: c.bg, color: c.fg, textTransform: "capitalize" }}
    >
      {value}
    </span>
  );
}

function formatRelative(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const min = Math.floor(diffMs / 60_000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d ago`;
  return d.toLocaleDateString();
}

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<LeadStatus | "">("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<LeadDetail | null>(null);
  const [savingStatus, setSavingStatus] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (q.trim()) params.set("q", q.trim());
      params.set("limit", "100");
      const res = await api<Page<Lead>>(`/leads?${params.toString()}`);
      setLeads(res.items);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    api<LeadDetail>(`/leads/${selectedId}`).then(setDetail);
  }, [selectedId]);

  async function updateStatus(newStatus: LeadStatus) {
    if (!detail) return;
    setSavingStatus(true);
    try {
      const updated = await api<Lead>(`/leads/${detail.contact_id}`, {
        method: "PATCH",
        body: JSON.stringify({ lead_status: newStatus })
      });
      setDetail({ ...detail, ...updated });
      setLeads((prev) =>
        prev.map((l) =>
          l.contact_id === detail.contact_id ? { ...l, lead_status: newStatus } : l
        )
      );
    } finally {
      setSavingStatus(false);
    }
  }

  const counts = useMemo(() => {
    const out: Record<string, number> = {};
    leads.forEach((l) => {
      const k = l.lead_status || "—";
      out[k] = (out[k] || 0) + 1;
    });
    return out;
  }, [leads]);

  return (
    <Shell>
      <div style={{ display: "flex", gap: 16, alignItems: "baseline", marginBottom: 12 }}>
        <h1 style={{ margin: 0 }}>Leads</h1>
        <span className="muted small">{total} total</span>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        {STATUSES.map((s) => (
          <button
            key={s.value || "all"}
            className={status === s.value ? "primary" : ""}
            onClick={() => setStatus(s.value)}
          >
            {s.label}
            {s.value && counts[s.value] !== undefined ? ` (${counts[s.value]})` : ""}
          </button>
        ))}
        <input
          placeholder="Search name / phone / city / summary…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") refresh();
          }}
          style={{ flex: 1, minWidth: 240 }}
        />
        <button onClick={refresh}>Refresh</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: selectedId ? "1.5fr 1fr" : "1fr", gap: 16 }}>
        <div className="card" style={{ overflow: "auto" }}>
          {loading ? (
            <div className="muted">Loading…</div>
          ) : leads.length === 0 ? (
            <div className="muted">
              No leads yet. As soon as customers start messaging, the AI will summarise them
              here automatically.
            </div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
              <thead>
                <tr style={{ textAlign: "left", color: "var(--muted)" }}>
                  <th style={{ padding: "6px 8px" }}>Name / Phone</th>
                  <th style={{ padding: "6px 8px" }}>City</th>
                  <th style={{ padding: "6px 8px" }}>Status</th>
                  <th style={{ padding: "6px 8px" }}>Next action</th>
                  <th style={{ padding: "6px 8px" }}>Last message</th>
                  <th style={{ padding: "6px 8px" }}>Score</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((l) => (
                  <tr
                    key={l.contact_id}
                    onClick={() => setSelectedId(l.contact_id)}
                    style={{
                      cursor: "pointer",
                      background: selectedId === l.contact_id ? "#1a1f28" : "transparent",
                      borderTop: "1px solid var(--border)"
                    }}
                  >
                    <td style={{ padding: "8px" }}>
                      <div>{l.name || "(no name)"}</div>
                      <div className="muted small">{l.phone_e164}</div>
                    </td>
                    <td style={{ padding: "8px" }}>{l.city || "—"}</td>
                    <td style={{ padding: "8px" }}>
                      <StatusPill value={l.lead_status} />
                    </td>
                    <td style={{ padding: "8px" }}>{l.lead_next_action || "—"}</td>
                    <td style={{ padding: "8px" }}>{formatRelative(l.last_message_at)}</td>
                    <td style={{ padding: "8px" }}>{l.lead_score ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {selectedId && (
          <div className="card" style={{ overflow: "auto" }}>
            {!detail ? (
              <div className="muted">Loading…</div>
            ) : (
              <>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "start"
                  }}
                >
                  <div>
                    <div style={{ fontSize: "1.1rem", fontWeight: 600 }}>
                      {detail.name || "(no name)"}
                    </div>
                    <div className="muted small">{detail.phone_e164}</div>
                  </div>
                  <button onClick={() => setSelectedId(null)}>Close</button>
                </div>

                <div className="muted small" style={{ marginTop: 10 }}>
                  Status
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
                  {STATUSES.filter((s) => s.value).map((s) => (
                    <button
                      key={s.value}
                      disabled={savingStatus}
                      className={detail.lead_status === s.value ? "primary" : ""}
                      onClick={() => updateStatus(s.value as LeadStatus)}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>

                {detail.lead_summary && (
                  <>
                    <div className="muted small" style={{ marginTop: 14 }}>
                      AI summary
                    </div>
                    <div style={{ whiteSpace: "pre-wrap" }}>{detail.lead_summary}</div>
                  </>
                )}

                {detail.lead_next_action && (
                  <>
                    <div className="muted small" style={{ marginTop: 14 }}>
                      Next action
                    </div>
                    <div>{detail.lead_next_action}</div>
                  </>
                )}

                <div className="muted small" style={{ marginTop: 14 }}>
                  Known facts
                </div>
                <ul style={{ margin: "4px 0", paddingLeft: 18 }}>
                  {detail.city && <li>City: {detail.city}</li>}
                  {detail.state && <li>State: {detail.state}</li>}
                  {detail.property_type && <li>Property: {detail.property_type}</li>}
                  {detail.monthly_bill && <li>Monthly bill: {detail.monthly_bill}</li>}
                  {Object.entries(detail.lead_extracted_attributes || {}).map(([k, v]) => (
                    <li key={k}>
                      {k.replace(/_/g, " ")}: {String(v)}
                    </li>
                  ))}
                  {!detail.city &&
                    !detail.state &&
                    !detail.property_type &&
                    !detail.monthly_bill &&
                    Object.keys(detail.lead_extracted_attributes || {}).length === 0 && (
                      <li className="muted">Nothing captured yet</li>
                    )}
                </ul>

                <div className="muted small" style={{ marginTop: 14 }}>
                  Recent messages
                </div>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 6,
                    marginTop: 4,
                    maxHeight: 360,
                    overflow: "auto",
                    border: "1px solid var(--border)",
                    borderRadius: 6,
                    padding: 8
                  }}
                >
                  {detail.recent_messages.length === 0 && (
                    <div className="muted small">No messages yet.</div>
                  )}
                  {detail.recent_messages.map((m) => (
                    <div
                      key={m.id}
                      style={{
                        alignSelf: m.direction === "inbound" ? "flex-start" : "flex-end",
                        background:
                          m.direction === "inbound" ? "#1d2230" : "#1d271d",
                        padding: "6px 10px",
                        borderRadius: 8,
                        maxWidth: "85%",
                        fontSize: "0.88rem"
                      }}
                    >
                      <div>{m.body}</div>
                      <div className="muted small" style={{ marginTop: 2 }}>
                        {formatRelative(m.created_at)} ·{" "}
                        {m.direction === "inbound" ? "customer" : m.sender_kind || "agent"}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </Shell>
  );
}
