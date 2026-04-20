"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Shell from "@/components/Shell";
import { api, API_BASE_URL, getToken } from "@/lib/api";
import type { Campaign, CampaignMetrics } from "@/lib/types";

type Preview = {
  upload_id: string;
  columns: string[];
  preview_rows: Record<string, any>[];
  total_rows: number;
  suggested_mapping: Record<string, string>;
};

const INTERNAL = [
  "name",
  "phone",
  "city",
  "state",
  "property_type",
  "monthly_bill",
  "roof_type",
  "notes",
  "source"
];

export default function CampaignDetail() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [c, setC] = useState<Campaign | null>(null);
  const [metrics, setMetrics] = useState<CampaignMetrics | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [paramCols, setParamCols] = useState<string>("");

  async function load() {
    setC(await api<Campaign>(`/campaigns/${id}`));
    setMetrics(await api<CampaignMetrics>(`/campaigns/${id}/metrics`));
  }

  useEffect(() => {
    load();
  }, [id]);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    const form = new FormData();
    form.append("file", f);
    const res = await fetch(`${API_BASE_URL}/campaigns/${id}/upload`, {
      method: "POST",
      body: form,
      headers: { Authorization: `Bearer ${getToken()}` }
    });
    if (!res.ok) { alert(await res.text()); return; }
    const p = (await res.json()) as Preview;
    setPreview(p);
    setMapping(p.suggested_mapping || {});
    load();
  }

  async function confirmMapping() {
    if (!preview) return;
    const tParams = paramCols.split(",").map((s) => s.trim()).filter(Boolean);
    try {
      await api(`/campaigns/${id}/uploads/${preview.upload_id}/confirm`, {
        method: "POST",
        body: JSON.stringify({
          mapping,
          template_param_columns: tParams,
          dedupe: true
        })
      });
      setPreview(null);
      load();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }

  async function act(path: string) {
    try {
      await api(`/campaigns/${id}/${path}`, {
        method: "POST",
        body: JSON.stringify({})
      });
      load();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }

  if (!c) return <Shell><div className="muted">Loading…</div></Shell>;

  const canSendOrSchedule = ["mapped", "scheduled", "paused"].includes(c.status);
  const sendScheduleHint =
    c.status === "draft"
      ? "Upload a CSV, map columns (phone required), then click Confirm mapping before Schedule or Send now."
      : c.status === "sending"
        ? "Sending in progress — use Pause to stop."
        : ["completed", "cancelled", "failed"].includes(c.status)
          ? "This campaign has finished. Create a new campaign to send again."
          : !canSendOrSchedule
            ? `Actions are limited while status is ${c.status}.`
            : null;

  return (
    <Shell>
      <h2>{c.name}</h2>
      <div className="small muted">Template: {c.template_name} · Status: {c.status}</div>
      {sendScheduleHint && (
        <p className="small muted" style={{ marginTop: 8, maxWidth: 640 }}>
          {sendScheduleHint}
        </p>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 12, marginTop: 16 }}>
        {metrics && Object.entries(metrics).map(([k, v]) => (
          <div key={k} className="card">
            <div className="muted small">{k}</div>
            <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>{v as number}</div>
          </div>
        ))}
      </div>

      <div className="row" style={{ marginTop: 16, gap: 8 }}>
        <label className="primary" style={{ cursor: "pointer", padding: "0.5rem 0.9rem", borderRadius: 6 }}>
          Upload CSV / Excel
          <input type="file" accept=".csv,.xlsx,.xls" style={{ display: "none" }} onChange={onUpload} />
        </label>
        <button
          type="button"
          onClick={() => act("schedule")}
          disabled={!canSendOrSchedule}
          title={!canSendOrSchedule ? "Confirm CSV mapping first" : undefined}
        >
          Schedule
        </button>
        <button
          type="button"
          className="primary"
          onClick={() => act("send-now")}
          disabled={!canSendOrSchedule}
          title={!canSendOrSchedule ? "Confirm CSV mapping first" : undefined}
        >
          Send now
        </button>
        <button onClick={() => act("pause")}>Pause</button>
        <button className="danger" onClick={() => act("cancel")}>Cancel</button>
      </div>

      {preview && (
        <div className="card col" style={{ marginTop: 16 }}>
          <div style={{ fontWeight: 600 }}>Map columns → fields ({preview.total_rows} rows)</div>
          <table className="table">
            <thead>
              <tr>
                <th>CSV column</th>
                <th>Maps to</th>
                <th>Sample</th>
              </tr>
            </thead>
            <tbody>
              {preview.columns.map((col) => (
                <tr key={col}>
                  <td>{col}</td>
                  <td>
                    <select value={mapping[col] || ""} onChange={(e) => setMapping({ ...mapping, [col]: e.target.value })}>
                      <option value="">— ignore —</option>
                      {INTERNAL.map((i) => <option key={i} value={i}>{i}</option>)}
                    </select>
                  </td>
                  <td className="muted small">{String(preview.preview_rows[0]?.[col] ?? "")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <label className="col small muted">
            Template parameter columns (comma-separated, in order):
            <input value={paramCols} onChange={(e) => setParamCols(e.target.value)} placeholder="Name,City" />
          </label>
          <button className="primary" onClick={confirmMapping}>Confirm mapping</button>
        </div>
      )}
    </Shell>
  );
}
