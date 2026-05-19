"use client";

/**
 * Renders the customer-shared file attached to a Message.
 *
 * The backend stores inbound media under user_uploads/<phone>/... and
 * serves it through an authenticated endpoint, so we can't just point an
 * <img src> at it — we have to fetch with the JWT and feed the bytes
 * into a blob URL. We also fall back to the raw provider CDN URL when no
 * local copy exists (e.g. for outbound messages or when downloads are
 * disabled in config).
 */
import { useEffect, useState } from "react";
import { getApiBase, getToken } from "@/lib/api";
import type { Message } from "@/lib/types";

type Kind = "image" | "audio" | "video" | "document";

function classify(mediaType: string | null | undefined, fallbackName?: string): Kind {
  const mt = (mediaType || "").toLowerCase();
  if (mt.startsWith("image/") || mt === "image" || /\.(jpe?g|png|gif|webp)$/i.test(fallbackName || "")) {
    return "image";
  }
  if (mt.startsWith("audio/") || mt === "audio" || mt === "voice" || /\.(mp3|ogg|m4a|wav|amr)$/i.test(fallbackName || "")) {
    return "audio";
  }
  if (mt.startsWith("video/") || mt === "video" || /\.(mp4|mov|webm|3gp)$/i.test(fallbackName || "")) {
    return "video";
  }
  return "document";
}

function basenameOf(p: string | null | undefined): string {
  if (!p) return "attachment";
  const parts = p.split(/[/\\]/);
  return parts[parts.length - 1] || "attachment";
}

export default function MediaAttachment({ message }: { message: Message }) {
  const hasLocal = !!message.local_media_path;
  const hasRemote = !!message.media_url;
  if (!hasLocal && !hasRemote) return null;

  const filename = basenameOf(message.local_media_path) || basenameOf(message.media_url || undefined);
  const kind = classify(message.media_type, filename);
  const [src, setSrc] = useState<string | null>(hasLocal ? null : message.media_url || null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(hasLocal);

  useEffect(() => {
    if (!hasLocal) return;
    let revokeUrl: string | null = null;
    let cancelled = false;
    const run = async () => {
      try {
        const token = getToken();
        const res = await fetch(`${getApiBase()}/inbox/messages/${message.id}/media`, {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined
        });
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        const blob = await res.blob();
        if (cancelled) return;
        revokeUrl = URL.createObjectURL(blob);
        setSrc(revokeUrl);
        setLoading(false);
      } catch (e) {
        if (cancelled) return;
        setErr(e instanceof Error ? e.message : String(e));
        setLoading(false);
        // Fall back to the provider URL so the operator can still try
        // clicking through to the CDN if the local copy is missing.
        if (hasRemote) setSrc(message.media_url || null);
      }
    };
    void run();
    return () => {
      cancelled = true;
      if (revokeUrl) URL.revokeObjectURL(revokeUrl);
    };
  }, [hasLocal, hasRemote, message.id, message.media_url]);

  const wrapStyle: React.CSSProperties = {
    marginTop: 6,
    marginBottom: 4,
    borderRadius: 8,
    overflow: "hidden",
    border: "1px solid var(--border)",
    background: "var(--bg-soft, rgba(0,0,0,0.03))"
  };

  if (loading) {
    return (
      <div style={{ ...wrapStyle, padding: "0.5rem 0.6rem", fontSize: "0.78rem", color: "var(--muted)" }}>
        Loading attachment…
      </div>
    );
  }

  if (!src) {
    return (
      <div style={{ ...wrapStyle, padding: "0.5rem 0.6rem", fontSize: "0.78rem", color: "var(--muted)" }}>
        Attachment unavailable {err ? `(${err})` : ""}
      </div>
    );
  }

  if (kind === "image") {
    return (
      <a href={src} target="_blank" rel="noopener noreferrer" style={{ display: "block", ...wrapStyle }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={filename}
          style={{ display: "block", maxWidth: "100%", maxHeight: 280, objectFit: "cover" }}
        />
      </a>
    );
  }
  if (kind === "audio") {
    return (
      <div style={{ ...wrapStyle, padding: "0.4rem 0.5rem" }}>
        <audio controls src={src} style={{ width: "100%", maxWidth: 320 }} />
      </div>
    );
  }
  if (kind === "video") {
    return (
      <video
        controls
        src={src}
        style={{ ...wrapStyle, display: "block", maxWidth: "100%", maxHeight: 320 }}
      />
    );
  }
  // Document / unknown
  return (
    <a
      href={src}
      target="_blank"
      rel="noopener noreferrer"
      download={filename}
      style={{
        ...wrapStyle,
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "0.55rem 0.65rem",
        textDecoration: "none",
        color: "var(--text)",
        fontSize: "0.85rem"
      }}
    >
      <span
        aria-hidden
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 28,
          height: 28,
          borderRadius: 6,
          background: "var(--info-soft)",
          color: "var(--info-text)",
          fontWeight: 600,
          fontSize: "0.7rem",
          letterSpacing: 0.3
        }}
      >
        DOC
      </span>
      <span style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <span style={{ fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {filename}
        </span>
        <span className="small" style={{ color: "var(--muted)", fontSize: "0.72rem" }}>
          Open / download
        </span>
      </span>
    </a>
  );
}
