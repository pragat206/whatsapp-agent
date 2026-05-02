"use client";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, apiForm } from "@/lib/api";

type Kb = { id: string; name: string; description?: string | null; published: boolean };
type Doc = {
  id: string;
  kb_id: string;
  title: string;
  category?: string | null;
  source_kind: string;
  published: boolean;
};
type Faq = {
  id: string;
  kb_id: string;
  question: string;
  answer: string;
  category?: string | null;
  published: boolean;
};
type QueryItem = {
  text: string;
  document_id: string;
  score: number;
  category?: string | null;
};

export default function KbPage() {
  const [kbs, setKbs] = useState<Kb[]>([]);
  const [active, setActive] = useState<Kb | null>(null);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [faqs, setFaqs] = useState<Faq[]>([]);
  const [q, setQ] = useState("");
  const [result, setResult] = useState<QueryItem[]>([]);
  const [queryHint, setQueryHint] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Create-KB form
  const [newKbName, setNewKbName] = useState("");
  const [newKbDesc, setNewKbDesc] = useState("");

  // Add-doc form (text)
  const [docTitle, setDocTitle] = useState("");
  const [docCat, setDocCat] = useState("");
  const [docBody, setDocBody] = useState("");

  // Upload-doc form (file)
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadCat, setUploadCat] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  // FAQ form
  const [faqQ, setFaqQ] = useState("");
  const [faqA, setFaqA] = useState("");
  const [faqCat, setFaqCat] = useState("");

  function report(err: unknown) {
    setInfo(null);
    setError(err instanceof Error ? err.message : String(err));
  }

  async function loadKbs() {
    try {
      const r = await api<Kb[]>("/kb");
      setKbs(r);
      if (r.length === 0) {
        setActive(null);
      } else if (!active || !r.find((k) => k.id === active.id)) {
        setActive(r[0]);
      }
    } catch (e) {
      report(e);
    }
  }

  async function loadDetail() {
    if (!active) {
      setDocs([]);
      setFaqs([]);
      return;
    }
    try {
      setDocs(await api<Doc[]>(`/kb/${active.id}/documents`));
      setFaqs(await api<Faq[]>(`/kb/${active.id}/faqs`));
    } catch (e) {
      report(e);
    }
  }

  useEffect(() => {
    loadKbs();
  }, []);
  useEffect(() => {
    loadDetail();
  }, [active?.id]);

  async function createKb(e: React.FormEvent) {
    e.preventDefault();
    if (!newKbName.trim()) return;
    setBusy(true);
    try {
      const kb = await api<Kb>("/kb", {
        method: "POST",
        body: JSON.stringify({ name: newKbName, description: newKbDesc || null })
      });
      setNewKbName("");
      setNewKbDesc("");
      await loadKbs();
      setActive(kb);
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  }

  async function deleteKb() {
    if (!active) return;
    if (!confirm(`Delete KB "${active.name}" and all its documents/FAQs?`)) return;
    setBusy(true);
    try {
      await api(`/kb/${active.id}`, { method: "DELETE" });
      setActive(null);
      await loadKbs();
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  }

  async function addDoc(e: React.FormEvent) {
    e.preventDefault();
    if (!active || !docTitle.trim() || !docBody.trim()) return;
    setBusy(true);
    try {
      await api(`/kb/${active.id}/documents`, {
        method: "POST",
        body: JSON.stringify({
          title: docTitle,
          category: docCat || null,
          content: docBody,
          source_kind: "text"
        })
      });
      setDocTitle("");
      setDocCat("");
      setDocBody("");
      await loadDetail();
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  }

  async function uploadDoc(e: React.FormEvent) {
    e.preventDefault();
    if (!active || !uploadFile || !uploadTitle.trim()) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", uploadFile);
      form.append("title", uploadTitle);
      if (uploadCat) form.append("category", uploadCat);
      await apiForm(`/kb/${active.id}/documents/upload`, form);
      setUploadTitle("");
      setUploadCat("");
      setUploadFile(null);
      await loadDetail();
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  }

  async function togglePublish(doc: Doc) {
    setBusy(true);
    try {
      await api(`/kb/documents/${doc.id}/publish?published=${!doc.published}`, {
        method: "POST"
      });
      await loadDetail();
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  }

  async function deleteDoc(doc: Doc) {
    if (!confirm(`Delete document "${doc.title}"?`)) return;
    setBusy(true);
    try {
      await api(`/kb/documents/${doc.id}`, { method: "DELETE" });
      await loadDetail();
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  }

  async function reindexAll() {
    if (!active) return;
    setBusy(true);
    try {
      await api(`/kb/${active.id}/reindex`, { method: "POST" });
      setError(null);
      setInfo(
        "Reindex queued successfully. Embeddings update in the background; if results still do not appear after a minute, check worker logs."
      );
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  }

  async function addFaq(e: React.FormEvent) {
    e.preventDefault();
    if (!active || !faqQ.trim() || !faqA.trim()) return;
    setBusy(true);
    try {
      await api(`/kb/${active.id}/faqs`, {
        method: "POST",
        body: JSON.stringify({
          question: faqQ,
          answer: faqA,
          category: faqCat || null
        })
      });
      setFaqQ("");
      setFaqA("");
      setFaqCat("");
      await loadDetail();
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  }

  async function deleteFaq(faq: Faq) {
    if (!confirm("Delete this FAQ?")) return;
    setBusy(true);
    try {
      await api(`/kb/faqs/${faq.id}`, { method: "DELETE" });
      await loadDetail();
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  }

  async function testQuery() {
    if (!q.trim()) return;
    setBusy(true);
    try {
      const r = await api<{ items: QueryItem[]; hint?: string | null }>("/kb/test-query", {
        method: "POST",
        body: JSON.stringify({ query: q, top_k: 5 })
      });
      setResult(r.items);
      setQueryHint(r.hint ?? null);
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h2>Knowledge base</h2>
        {active && (
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={reindexAll} disabled={busy}>
              Reindex
            </button>
            <button onClick={deleteKb} disabled={busy}>
              Delete KB
            </button>
          </div>
        )}
      </div>

      {error && (
        <div
          className="card"
          style={{
            borderColor: "var(--danger)",
            background: "var(--danger-soft)",
            color: "var(--danger-text)",
            marginBottom: 12
          }}
        >
          <div className="small">{error}</div>
          <button className="small" onClick={() => setError(null)}>
            dismiss
          </button>
        </div>
      )}

      {info && (
        <div
          className="card"
          style={{
            borderColor: "var(--info)",
            background: "var(--info-soft)",
            color: "var(--info-text)",
            marginBottom: 12
          }}
        >
          <div className="small">{info}</div>
          <button className="small" onClick={() => setInfo(null)}>
            dismiss
          </button>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "260px 1fr 1fr", gap: 16 }}>
        <div className="card col">
          <div style={{ fontWeight: 600 }}>Knowledge bases</div>
          {kbs.length === 0 && <div className="muted small">No KBs yet.</div>}
          {kbs.map((k) => (
            <div
              key={k.id}
              onClick={() => setActive(k)}
              style={{
                padding: 6,
                borderRadius: 6,
                cursor: "pointer",
                background:
                  active?.id === k.id ? "var(--panel-selected)" : "transparent"
              }}
            >
              <div>{k.name}</div>
              {k.description && <div className="muted small">{k.description}</div>}
            </div>
          ))}
          <form onSubmit={createKb} className="col" style={{ marginTop: 12 }}>
            <div className="small muted">Create new KB</div>
            <input
              placeholder="Name (e.g. Product FAQs)"
              value={newKbName}
              onChange={(e) => setNewKbName(e.target.value)}
            />
            <input
              placeholder="Description (optional)"
              value={newKbDesc}
              onChange={(e) => setNewKbDesc(e.target.value)}
            />
            <button className="primary" disabled={busy || !newKbName.trim()}>
              Create KB
            </button>
          </form>
        </div>

        <div className="card col">
          <div style={{ fontWeight: 600 }}>Documents {active && `(${docs.length})`}</div>
          {active ? (
            <>
              <form onSubmit={addDoc} className="col">
                <div className="small muted">Add document (text)</div>
                <input
                  placeholder="Title"
                  value={docTitle}
                  onChange={(e) => setDocTitle(e.target.value)}
                />
                <input
                  placeholder="Category (optional)"
                  value={docCat}
                  onChange={(e) => setDocCat(e.target.value)}
                />
                <textarea
                  placeholder="Content"
                  rows={4}
                  value={docBody}
                  onChange={(e) => setDocBody(e.target.value)}
                />
                <button className="primary" disabled={busy}>
                  Add document
                </button>
              </form>
              <form onSubmit={uploadDoc} className="col" style={{ marginTop: 8 }}>
                <div className="small muted">Upload file (PDF, MD, TXT)</div>
                <input
                  placeholder="Title"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                />
                <input
                  placeholder="Category (optional)"
                  value={uploadCat}
                  onChange={(e) => setUploadCat(e.target.value)}
                />
                <input
                  type="file"
                  accept=".pdf,.md,.txt"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                />
                <button
                  className="primary"
                  disabled={busy || !uploadFile || !uploadTitle.trim()}
                >
                  Upload
                </button>
              </form>
              <table className="table">
                <tbody>
                  {docs.map((d) => (
                    <tr key={d.id}>
                      <td>
                        <div>{d.title}</div>
                        <div className="muted small">
                          {d.category || "—"} · {d.source_kind}
                        </div>
                      </td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        <button
                          onClick={() => togglePublish(d)}
                          className="small"
                          style={{ marginRight: 6 }}
                        >
                          {d.published ? "Unpublish" : "Publish"}
                        </button>
                        <button onClick={() => deleteDoc(d)} className="small">
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <div className="muted small">Select a KB or create one.</div>
          )}
        </div>

        <div className="card col">
          <div style={{ fontWeight: 600 }}>FAQs {active && `(${faqs.length})`}</div>
          {active ? (
            <>
              <form onSubmit={addFaq} className="col">
                <input
                  placeholder="Question"
                  value={faqQ}
                  onChange={(e) => setFaqQ(e.target.value)}
                />
                <textarea
                  placeholder="Answer"
                  rows={2}
                  value={faqA}
                  onChange={(e) => setFaqA(e.target.value)}
                />
                <input
                  placeholder="Category (optional)"
                  value={faqCat}
                  onChange={(e) => setFaqCat(e.target.value)}
                />
                <button className="primary" disabled={busy}>
                  Add FAQ
                </button>
              </form>
              <table className="table">
                <tbody>
                  {faqs.map((f) => (
                    <tr key={f.id}>
                      <td>
                        <div>{f.question}</div>
                        <div className="muted small">{f.answer}</div>
                      </td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        <button onClick={() => deleteFaq(f)} className="small">
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <div className="muted small">Select a KB.</div>
          )}
        </div>
      </div>

      <div className="card col" style={{ marginTop: 16 }}>
        <div style={{ fontWeight: 600 }}>Test retrieval</div>
        <div className="small muted">
          Queries use embeddings across <strong>all published</strong> KB content (needs{" "}
          <code>OPENAI_API_KEY</code> on the server). If that key is missing, a simple text match is used.
        </div>
        <div className="row">
          <input
            placeholder="e.g. How much subsidy do I get on a 3 kW system?"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") testQuery();
            }}
          />
          <button className="primary" onClick={testQuery} disabled={busy || !q.trim()}>
            Search
          </button>
        </div>
        {queryHint && (
          <div
            className="small"
            style={{
              marginTop: 8,
              padding: "8px 10px",
              borderRadius: 6,
              background: "var(--bg-soft)",
              border: "1px solid var(--border)"
            }}
          >
            {queryHint}
          </div>
        )}
        {result.length === 0 && !queryHint && q && !busy && (
          <div className="muted small" style={{ marginTop: 8 }}>
            No results — try another query or use words from your documents.
          </div>
        )}
        {result.map((r, i) => (
          <div key={i} className="card" style={{ marginTop: 8 }}>
            <div className="small muted">
              score {r.score.toFixed(3)} · {r.category || "—"}
            </div>
            <div style={{ whiteSpace: "pre-wrap" }}>{r.text}</div>
          </div>
        ))}
      </div>
    </Shell>
  );
}
