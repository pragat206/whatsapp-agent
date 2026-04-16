"use client";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api } from "@/lib/api";

type Kb = { id: string; name: string; description?: string | null; published: boolean };
type Doc = { id: string; kb_id: string; title: string; category?: string | null; source_kind: string; published: boolean };
type Faq = { id: string; kb_id: string; question: string; answer: string; category?: string | null };

export default function KbPage() {
  const [kbs, setKbs] = useState<Kb[]>([]);
  const [active, setActive] = useState<Kb | null>(null);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [faqs, setFaqs] = useState<Faq[]>([]);
  const [q, setQ] = useState("");
  const [result, setResult] = useState<any[]>([]);

  const [docTitle, setDocTitle] = useState("");
  const [docCat, setDocCat] = useState("");
  const [docBody, setDocBody] = useState("");

  const [faqQ, setFaqQ] = useState("");
  const [faqA, setFaqA] = useState("");
  const [faqCat, setFaqCat] = useState("");

  async function loadKbs() {
    const r = await api<Kb[]>("/kb");
    setKbs(r);
    if (!active && r.length) setActive(r[0]);
  }

  async function loadDetail() {
    if (!active) return;
    setDocs(await api<Doc[]>(`/kb/${active.id}/documents`));
    setFaqs(await api<Faq[]>(`/kb/${active.id}/faqs`));
  }

  useEffect(() => { loadKbs(); }, []);
  useEffect(() => { loadDetail(); }, [active?.id]);

  async function addDoc(e: React.FormEvent) {
    e.preventDefault();
    if (!active) return;
    await api(`/kb/${active.id}/documents`, {
      method: "POST",
      body: JSON.stringify({ title: docTitle, category: docCat, content: docBody, source_kind: "text" })
    });
    setDocTitle(""); setDocCat(""); setDocBody("");
    loadDetail();
  }

  async function addFaq(e: React.FormEvent) {
    e.preventDefault();
    if (!active) return;
    await api(`/kb/${active.id}/faqs`, {
      method: "POST",
      body: JSON.stringify({ question: faqQ, answer: faqA, category: faqCat })
    });
    setFaqQ(""); setFaqA(""); setFaqCat("");
    loadDetail();
  }

  async function testQuery() {
    const r = await api<{ items: any[] }>("/kb/test-query", {
      method: "POST",
      body: JSON.stringify({ query: q, top_k: 5 })
    });
    setResult(r.items);
  }

  return (
    <Shell>
      <h2>Knowledge base</h2>
      <div style={{ display: "grid", gridTemplateColumns: "220px 1fr 1fr", gap: 16 }}>
        <div className="card col">
          <div style={{ fontWeight: 600 }}>KBs</div>
          {kbs.map((k) => (
            <div
              key={k.id}
              onClick={() => setActive(k)}
              style={{ padding: 6, borderRadius: 6, cursor: "pointer", background: active?.id === k.id ? "#1a2332" : "transparent" }}
            >
              {k.name}
            </div>
          ))}
        </div>

        <div className="card col">
          <div style={{ fontWeight: 600 }}>Documents</div>
          <form onSubmit={addDoc} className="col">
            <input placeholder="Title" value={docTitle} onChange={(e) => setDocTitle(e.target.value)} />
            <input placeholder="Category" value={docCat} onChange={(e) => setDocCat(e.target.value)} />
            <textarea placeholder="Content" rows={4} value={docBody} onChange={(e) => setDocBody(e.target.value)} />
            <button className="primary">Add document</button>
          </form>
          <table className="table">
            <tbody>
              {docs.map((d) => (
                <tr key={d.id}>
                  <td>{d.title}</td>
                  <td className="muted small">{d.category}</td>
                  <td className="muted small">{d.source_kind}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card col">
          <div style={{ fontWeight: 600 }}>FAQs</div>
          <form onSubmit={addFaq} className="col">
            <input placeholder="Question" value={faqQ} onChange={(e) => setFaqQ(e.target.value)} />
            <textarea placeholder="Answer" rows={2} value={faqA} onChange={(e) => setFaqA(e.target.value)} />
            <input placeholder="Category" value={faqCat} onChange={(e) => setFaqCat(e.target.value)} />
            <button className="primary">Add FAQ</button>
          </form>
          <table className="table">
            <tbody>
              {faqs.map((f) => (
                <tr key={f.id}>
                  <td>{f.question}</td>
                  <td className="muted small">{f.category}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card col" style={{ marginTop: 16 }}>
        <div style={{ fontWeight: 600 }}>Test a query</div>
        <div className="row">
          <input placeholder="e.g. How much subsidy?" value={q} onChange={(e) => setQ(e.target.value)} />
          <button className="primary" onClick={testQuery}>Search</button>
        </div>
        {result.map((r, i) => (
          <div key={i} className="card" style={{ marginTop: 8 }}>
            <div className="small muted">score {r.score.toFixed(3)} · {r.category || "—"}</div>
            <div style={{ whiteSpace: "pre-wrap" }}>{r.text}</div>
          </div>
        ))}
      </div>
    </Shell>
  );
}
