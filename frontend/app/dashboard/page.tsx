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
    api<Overview>("/analytics/overview").then(setData);
  }, []);

  return (
    <Shell>
      <h2>Overview</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginTop: 16 }}>
        <Card title="Active conversations" value={data?.active_conversations ?? "—"} />
        <Card title="Takeovers (24h)" value={data?.takeovers_last_24h ?? "—"} />
        <Card title="Active campaigns" value={data?.campaigns_active ?? "—"} />
        <Card
          title="AI replies sent (24h)"
          value={data?.ai_runs_last_24h?.sent ?? "—"}
        />
      </div>

      <div className="row" style={{ marginTop: 24 }}>
        <div className="card col" style={{ flex: 1 }}>
          <div style={{ fontWeight: 600 }}>Conversations by state</div>
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
        </div>
        <div className="card col" style={{ flex: 1 }}>
          <div style={{ fontWeight: 600 }}>Campaign recipients (24h)</div>
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
        </div>
      </div>
    </Shell>
  );
}

function Card({ title, value }: { title: string; value: any }) {
  return (
    <div className="card">
      <div className="muted small">{title}</div>
      <div style={{ fontSize: "1.6rem", fontWeight: 700, marginTop: 4 }}>{value}</div>
    </div>
  );
}
