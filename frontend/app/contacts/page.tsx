"use client";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api } from "@/lib/api";
import type { Contact, Page } from "@/lib/types";

export default function ContactsPage() {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Contact[]>([]);

  async function load() {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    const r = await api<Page<Contact>>(`/contacts?${params}`);
    setItems(r.items);
  }

  useEffect(() => { load(); }, []);

  return (
    <Shell>
      <h2>Contacts</h2>
      <div className="row" style={{ marginBottom: 12 }}>
        <input placeholder="Search phone, name, city" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="primary" onClick={load}>Search</button>
      </div>
      <table className="table">
        <thead>
          <tr><th>Phone</th><th>Name</th><th>City</th><th>Unsubscribed</th></tr>
        </thead>
        <tbody>
          {items.map((c) => (
            <tr key={c.id}>
              <td>{c.phone_e164}</td>
              <td>{c.name || "—"}</td>
              <td>{c.city || "—"}</td>
              <td>{c.unsubscribed ? "yes" : "no"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Shell>
  );
}
