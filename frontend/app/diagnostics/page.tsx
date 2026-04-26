"use client";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api } from "@/lib/api";

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

type RawWebhookEvent = {
  id: string;
  kind: string;
  created_at: string | null;
  processed: boolean;
  error: string | null;
  dedupe_key: string;
  payload: any;
};

type RecentEvents = { count: number; events: RawWebhookEvent[] };

type TestSendResult = {
  ok: boolean;
  raw_response?: any;
  error?: string;
  error_type?: string;
};

export default function DiagnosticsPage() {
  const [aisensy, setAisensy] = useState<AiSensyDiag | null>(null);
  const [system, setSystem] = useState<SystemDiag | null>(null);
  const [systemLoading, setSystemLoading] = useState(false);

  const [sessPhone, setSessPhone] = useState("");
  const [sessBody, setSessBody] = useState("Test from WhatsApp Agent");
  const [sessBusy, setSessBusy] = useState(false);
  const [sessResult, setSessResult] = useState<TestSendResult | null>(null);

  const [tmplPhone, setTmplPhone] = useState("");
  const [tmplName, setTmplName] = useState("");
  const [tmplParams, setTmplParams] = useState("");
  const [tmplBusy, setTmplBusy] = useState(false);
  const [tmplResult, setTmplResult] = useState<TestSendResult | null>(null);

  const [recentBusy, setRecentBusy] = useState(false);
  const [recent, setRecent] = useState<RecentEvents | null>(null);

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

  async function testSendSession() {
    if (!sessPhone.trim() || !sessBody.trim() || sessBusy) return;
    setSessBusy(true);
    setSessResult(null);
    try {
      const r = await api<TestSendResult>(
        "/integrations/aisensy/test-send-session",
        {
          method: "POST",
          body: JSON.stringify({ phone: sessPhone.trim(), body: sessBody })
        }
      );
      setSessResult(r);
    } catch (e) {
      setSessResult({ ok: false, error: e instanceof Error ? e.message : String(e) });
    } finally {
      setSessBusy(false);
    }
  }

  async function testSendCampaign() {
    if (!tmplPhone.trim() || !tmplName.trim() || tmplBusy) return;
    setTmplBusy(true);
    setTmplResult(null);
    try {
      const params = tmplParams
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const r = await api<TestSendResult>(
        "/integrations/aisensy/test-send-campaign",
        {
          method: "POST",
          body: JSON.stringify({
            phone: tmplPhone.trim(),
            template_name: tmplName.trim(),
            template_params: params
          })
        }
      );
      setTmplResult(r);
    } catch (e) {
      setTmplResult({ ok: false, error: e instanceof Error ? e.message : String(e) });
    } finally {
      setTmplBusy(false);
    }
  }

  async function loadRecentWebhooks() {
    setRecentBusy(true);
    try {
      setRecent(
        await api<RecentEvents>(
          "/integrations/aisensy/recent-events?kind=inbound&limit=10"
        )
      );
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setRecentBusy(false);
    }
  }

  useEffect(() => {
    api<AiSensyDiag>("/integrations/aisensy")
      .then(setAisensy)
      .catch(() => setAisensy(null));
    api<SystemDiag>("/integrations/system")
      .then(setSystem)
      .catch(() => setSystem(null));
  }, []);

  return (
    <Shell>
      <h1 style={{ margin: 0 }}>Diagnostics</h1>
      <p className="muted small" style={{ marginTop: 4 }}>
        Backend health, AiSensy connectivity, and tools to send real test
        messages. Useful when the AI isn't replying and you want to know why.
      </p>

      {system && (
        <div
          className="card col"
          style={{
            marginTop: 16,
            maxWidth: 900,
            borderColor: !system.summary.healthy ? "var(--danger)" : undefined
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
            borderColor: aisensy.hints.length ? "var(--warn)" : undefined
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

      <div className="card col" style={{ marginTop: 16, maxWidth: 900 }}>
        <div style={{ fontWeight: 600 }}>AiSensy diagnostics</div>
        <p className="small muted" style={{ marginTop: 4 }}>
          Send real test messages and inspect raw inbound webhooks. Costs apply
          for actual sends.
        </p>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 12,
            marginTop: 8
          }}
        >
          <div className="col" style={{ gap: 6 }}>
            <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>
              Test session send (24h window)
            </div>
            <input
              placeholder="Phone (+919876543210)"
              value={sessPhone}
              onChange={(e) => setSessPhone(e.target.value)}
            />
            <input
              placeholder="Body"
              value={sessBody}
              onChange={(e) => setSessBody(e.target.value)}
            />
            <button
              type="button"
              className="primary"
              disabled={sessBusy || !sessPhone.trim() || !sessBody.trim()}
              onClick={testSendSession}
            >
              {sessBusy ? "Sending…" : "Send test message"}
            </button>
            {sessResult && (
              <pre
                className="small"
                style={{
                  whiteSpace: "pre-wrap",
                  background: "var(--bg-soft)",
                  padding: 8,
                  borderRadius: 6,
                  color: sessResult.ok ? "var(--success-text)" : "var(--danger-text)",
                  maxHeight: 180,
                  overflow: "auto"
                }}
              >
                {JSON.stringify(sessResult, null, 2)}
              </pre>
            )}
          </div>

          <div className="col" style={{ gap: 6 }}>
            <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>
              Test template send (cold outreach)
            </div>
            <input
              placeholder="Phone (+919876543210)"
              value={tmplPhone}
              onChange={(e) => setTmplPhone(e.target.value)}
            />
            <input
              placeholder="Template name (e.g. affiliated_sales)"
              value={tmplName}
              onChange={(e) => setTmplName(e.target.value)}
            />
            <input
              placeholder="Template params, comma-separated (optional)"
              value={tmplParams}
              onChange={(e) => setTmplParams(e.target.value)}
            />
            <button
              type="button"
              className="primary"
              disabled={tmplBusy || !tmplPhone.trim() || !tmplName.trim()}
              onClick={testSendCampaign}
            >
              {tmplBusy ? "Sending…" : "Send test template"}
            </button>
            {tmplResult && (
              <pre
                className="small"
                style={{
                  whiteSpace: "pre-wrap",
                  background: "var(--bg-soft)",
                  padding: 8,
                  borderRadius: 6,
                  color: tmplResult.ok ? "var(--success-text)" : "var(--danger-text)",
                  maxHeight: 180,
                  overflow: "auto"
                }}
              >
                {JSON.stringify(tmplResult, null, 2)}
              </pre>
            )}
          </div>
        </div>

        <div style={{ marginTop: 12 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              flexWrap: "wrap"
            }}
          >
            <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>
              Recent inbound webhooks
            </div>
            <button
              type="button"
              disabled={recentBusy}
              onClick={loadRecentWebhooks}
            >
              {recentBusy ? "Loading…" : "Fetch last 10"}
            </button>
            <span className="small muted">
              Use this to see exactly what AiSensy is POSTing to your webhook URL.
            </span>
          </div>
          {recent && (
            <div className="col" style={{ marginTop: 8, gap: 6 }}>
              {recent.events.length === 0 && (
                <div className="muted small">
                  No inbound webhook events stored. Either AiSensy is not pointing
                  at this server, or the URL is wrong.
                </div>
              )}
              {recent.events.map((ev) => (
                <details
                  key={ev.id}
                  style={{
                    background: "var(--bg-soft)",
                    padding: 8,
                    borderRadius: 6
                  }}
                >
                  <summary
                    style={{
                      cursor: "pointer",
                      fontSize: "0.82rem",
                      color: ev.error ? "var(--danger-text)" : "var(--text)"
                    }}
                  >
                    {ev.created_at} · {ev.kind} ·{" "}
                    {ev.processed ? "processed" : "unprocessed"}
                    {ev.error ? ` · error: ${ev.error}` : ""}
                  </summary>
                  <pre
                    className="small"
                    style={{
                      whiteSpace: "pre-wrap",
                      marginTop: 6,
                      maxHeight: 320,
                      overflow: "auto"
                    }}
                  >
                    {JSON.stringify(ev.payload, null, 2)}
                  </pre>
                </details>
              ))}
            </div>
          )}
        </div>
      </div>
    </Shell>
  );
}
