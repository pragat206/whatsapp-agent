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

type SystemDiag = {
  database: { ok: boolean; latency_ms: number; error: string | null };
  redis: { ok: boolean; latency_ms: number; error: string | null };
  worker_queue: {
    queue_name: string;
    queued_jobs: number | null;
    error: string | null;
    hint: string | null;
  };
  llm: {
    provider: string;
    model: string;
    api_key_configured: boolean;
    probe: {
      ok: boolean;
      reply_preview?: string;
      error?: string;
      latency_ms?: number;
    } | null;
    ai_runs_last_24h: { sent: number; failed: number };
  };
  embeddings: {
    provider: string;
    openai_api_key_configured: boolean;
    hint: string | null;
  };
  summary: { healthy: boolean; notes: string[] };
};

type AiSensyDiag = {
  summary: string;
  config: {
    aisensy_api_key_configured: boolean;
    aisensy_base_url: string;
    webhook_signature_enforced: boolean;
  };
  database: {
    contacts: number;
    conversations: number;
    aisensy_inbound_webhook_events_total: number;
    aisensy_inbound_webhook_events_last_24h: number;
    aisensy_inbound_webhook_normalize_errors: number;
  };
  suggested_webhook_urls: { inbound: string; status: string } | null;
  hints: string[];
};

export default function Dashboard() {
  const [data, setData] = useState<Overview | null>(null);
  const [aisensy, setAisensy] = useState<AiSensyDiag | null>(null);
  const [system, setSystem] = useState<SystemDiag | null>(null);
  const [systemLoading, setSystemLoading] = useState(false);

  async function loadSystem(probeLlm: boolean) {
    setSystemLoading(true);
    try {
      const q = probeLlm ? "?probe_llm=true" : "";
      setSystem(await api<SystemDiag>(`/integrations/system${q}`));
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setSystemLoading(false);
    }
  }

  useEffect(() => {
    api<Overview>("/analytics/overview").then(setData);
    api<AiSensyDiag>("/integrations/aisensy")
      .then(setAisensy)
      .catch(() => setAisensy(null));
    api<SystemDiag>("/integrations/system")
      .then(setSystem)
      .catch(() => setSystem(null));
  }, []);

  return (
    <Shell>
      <h2>Overview</h2>
      {system && (
        <div
          className="card col"
          style={{
            marginTop: 16,
            maxWidth: 900,
            borderColor: !system.summary.healthy ? "#f87171" : undefined
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <div style={{ fontWeight: 600 }}>Backend &amp; LLM</div>
            <span className="small muted">
              Overall: {system.summary.healthy ? "OK" : "needs attention"}
            </span>
            <button
              type="button"
              className="primary"
              disabled={systemLoading}
              onClick={() => loadSystem(true)}
            >
              {systemLoading ? "Checking…" : "Test LLM call"}
            </button>
            <span className="small muted">Uses your provider API (small cost)</span>
          </div>
          <div className="small" style={{ marginTop: 8 }}>
            <strong>Database:</strong> {system.database.ok ? "ok" : "fail"}{" "}
            ({system.database.latency_ms} ms)
            {system.database.error ? ` — ${system.database.error}` : ""}
            {" · "}
            <strong>Redis:</strong> {system.redis.ok ? "ok" : "fail"}{" "}
            ({system.redis.latency_ms} ms)
            {system.redis.error ? ` — ${system.redis.error}` : ""}
          </div>
          <div className="small" style={{ marginTop: 4 }}>
            <strong>LLM:</strong> {system.llm.provider} / {system.llm.model} · key:{" "}
            {system.llm.api_key_configured ? "set" : "missing"} · AI runs 24h: sent{" "}
            {system.llm.ai_runs_last_24h.sent}, failed {system.llm.ai_runs_last_24h.failed}
          </div>
          <div className="small" style={{ marginTop: 4 }}>
            <strong>Queue ({system.worker_queue.queue_name}):</strong>{" "}
            {system.worker_queue.queued_jobs ?? "—"} jobs waiting
            {system.worker_queue.error ? ` — ${system.worker_queue.error}` : ""}
            {system.worker_queue.hint ? ` — ${system.worker_queue.hint}` : ""}
          </div>
          <div className="small" style={{ marginTop: 4 }}>
            <strong>Embeddings (KB):</strong> {system.embeddings.provider} · OpenAI key:{" "}
            {system.embeddings.openai_api_key_configured ? "set" : "missing"}
            {system.embeddings.hint ? ` — ${system.embeddings.hint}` : ""}
          </div>
          {system.llm.probe && (
            <div className="small" style={{ marginTop: 8 }}>
              <strong>LLM probe:</strong>{" "}
              {system.llm.probe.ok
                ? `ok (${system.llm.probe.latency_ms} ms) — ${system.llm.probe.reply_preview ?? ""}`
                : `failed — ${system.llm.probe.error ?? ""}`}
            </div>
          )}
          <ul style={{ marginTop: 8, paddingLeft: 18, fontSize: "0.85rem" }} className="muted">
            {system.summary.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </div>
      )}
      {aisensy && (
        <div
          className="card col"
          style={{
            marginTop: 16,
            maxWidth: 900,
            borderColor: aisensy.hints.length ? "#ca8a04" : undefined
          }}
        >
          <div style={{ fontWeight: 600 }}>AiSensy ↔ this app</div>
          <p className="small muted" style={{ marginTop: 6 }}>
            {aisensy.summary}
          </p>
          <div className="small" style={{ marginTop: 8 }}>
            <strong>API key set:</strong>{" "}
            {aisensy.config.aisensy_api_key_configured ? "yes" : "no"} ·{" "}
            <strong>Base URL:</strong> {aisensy.config.aisensy_base_url} ·{" "}
            <strong>Webhook signature required:</strong>{" "}
            {aisensy.config.webhook_signature_enforced ? "yes" : "no"}
          </div>
          <div className="small" style={{ marginTop: 6 }}>
            <strong>DB:</strong> {aisensy.database.contacts} contacts,{" "}
            {aisensy.database.conversations} conversations ·{" "}
            <strong>Inbound webhooks stored:</strong>{" "}
            {aisensy.database.aisensy_inbound_webhook_events_total} (last 24h:{" "}
            {aisensy.database.aisensy_inbound_webhook_events_last_24h})
            {aisensy.database.aisensy_inbound_webhook_normalize_errors > 0
              ? ` · normalize errors: ${aisensy.database.aisensy_inbound_webhook_normalize_errors}`
              : ""}
          </div>
          {aisensy.suggested_webhook_urls && (
            <div className="small col" style={{ marginTop: 8 }}>
              <span className="muted">Paste these in AiSensy webhook settings:</span>
              <code style={{ wordBreak: "break-all", fontSize: "0.8rem" }}>
                inbound: {aisensy.suggested_webhook_urls.inbound}
              </code>
              <code style={{ wordBreak: "break-all", fontSize: "0.8rem" }}>
                status: {aisensy.suggested_webhook_urls.status}
              </code>
            </div>
          )}
          {aisensy.hints.length > 0 && (
            <ul style={{ marginTop: 8, paddingLeft: 18, fontSize: "0.9rem" }}>
              {aisensy.hints.map((h, i) => (
                <li key={i}>{h}</li>
              ))}
            </ul>
          )}
        </div>
      )}
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
