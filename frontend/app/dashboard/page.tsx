"use client";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api } from "@/lib/api";

type Overview = {
  conversations: Record<string, number>;
  active_conversations: number;
  campaigns_active: number;
  recipients_last_24h: Record<string, number>;
  ai_runs_last_24h: Record<string, number>;
  takeovers_last_24h: number;
};

export default function Dashboard() {
  const [data, setData] = useState<Overview | null>(null);

  useEffect(() => {
    api<Overview>("/analytics/overview").then(setData).catch(() => setData(null));
  }, []);

  return (
    <Shell>
      <h1 style={{ margin: 0 }}>Overview</h1>
      <p className="muted small" style={{ marginTop: 4 }}>
        Live activity across conversations, campaigns, and AI replies. For
        backend health and AiSensy connectivity, see Diagnostics.
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 12,
          marginTop: 16
        }}
      >
        <Card title="Active conversations" value={data?.active_conversations ?? "—"} />
        <Card title="Takeovers (24h)" value={data?.takeovers_last_24h ?? "—"} />
        <Card title="Active campaigns" value={data?.campaigns_active ?? "—"} />
        <Card
          title="AI replies sent (24h)"
          value={data?.ai_runs_last_24h?.sent ?? "—"}
        />
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: 16,
          marginTop: 16
        }}
      >
        <div className="card col">
          <div style={{ fontWeight: 600 }}>Conversations by state</div>
          {Object.keys(data?.conversations ?? {}).length === 0 ? (
            <div className="muted small">No conversations yet.</div>
          ) : (
            <table className="table">
              <tbody>
                {Object.entries(data?.conversations ?? {}).map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td style={{ textAlign: "right" }}>{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="card col">
          <div style={{ fontWeight: 600 }}>Campaign recipients (24h)</div>
          {Object.keys(data?.recipients_last_24h ?? {}).length === 0 ? (
            <div className="muted small">No campaign activity in the last 24 hours.</div>
          ) : (
            <table className="table">
              <tbody>
                {Object.entries(data?.recipients_last_24h ?? {}).map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td style={{ textAlign: "right" }}>{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </Shell>
  );
}

function Card({ title, value }: { title: string; value: any }) {
  return (
    <div className="card">
      <div className="muted small">{title}</div>
      <div
        style={{
          fontSize: "1.7rem",
          fontWeight: 700,
          marginTop: 4,
          color: "var(--text-strong)"
        }}
      >
        {value}
      </div>
    </div>
  );
}
