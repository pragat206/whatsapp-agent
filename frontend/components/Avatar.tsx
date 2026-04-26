// Initials avatar — purely visual, no fake online indicator or extra UI.
// Hue is derived deterministically from the seed so the same contact always
// gets the same color across sessions and across the dashboard.

type Props = {
  name?: string | null;
  phone?: string | null;
  size?: number;
};

function initials(name?: string | null, phone?: string | null): string {
  const source = (name || "").trim();
  if (source) {
    const parts = source.split(/\s+/).filter(Boolean);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  const digits = (phone || "").replace(/\D/g, "");
  return digits.slice(-2) || "?";
}

function hueFromSeed(seed: string): number {
  let h = 0;
  for (let i = 0; i < seed.length; i++) {
    h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  }
  return h % 360;
}

export default function Avatar({ name, phone, size = 36 }: Props) {
  const seed = (name || phone || "?").toLowerCase();
  const hue = hueFromSeed(seed);
  return (
    <div
      aria-hidden
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        background: `hsl(${hue}, 55%, 35%)`,
        color: "#fff",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: Math.max(11, Math.floor(size * 0.4)),
        fontWeight: 600,
        flexShrink: 0,
        userSelect: "none",
        letterSpacing: 0.3
      }}
    >
      {initials(name, phone)}
    </div>
  );
}
