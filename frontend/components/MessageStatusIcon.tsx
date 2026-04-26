// Renders the small WhatsApp-style status indicator next to outbound message
// timestamps. Maps directly to the `message.status` value the backend already
// stores (sent | delivered | read | failed | queued / pending). No fake states.

type Props = {
  status?: string | null;
  size?: number;
};

const SIZE_DEFAULT = 14;

function color(status?: string | null): string {
  if (status === "failed") return "var(--danger)";
  if (status === "read") return "var(--info)";
  return "var(--muted)";
}

function Tick({ size }: { size: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M2 9 L6 13 L14 4" />
    </svg>
  );
}

function DoubleTick({ size }: { size: number }) {
  return (
    <svg
      width={size + 6}
      height={size}
      viewBox="0 0 22 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M2 9 L6 13 L14 4" />
      <path d="M8 13 L12 13 L20 4" />
    </svg>
  );
}

export default function MessageStatusIcon({ status, size = SIZE_DEFAULT }: Props) {
  if (!status) return null;
  if (status === "failed") {
    return (
      <span
        style={{ color: color(status), fontSize: size, lineHeight: 1 }}
        title="Failed to deliver"
        aria-label="Failed to deliver"
      >
        ✕
      </span>
    );
  }
  if (status === "read") {
    return (
      <span style={{ color: color(status), display: "inline-flex" }} title="Read">
        <DoubleTick size={size} />
      </span>
    );
  }
  if (status === "delivered") {
    return (
      <span style={{ color: color(status), display: "inline-flex" }} title="Delivered">
        <DoubleTick size={size} />
      </span>
    );
  }
  if (status === "sent") {
    return (
      <span style={{ color: color(status), display: "inline-flex" }} title="Sent">
        <Tick size={size} />
      </span>
    );
  }
  // pending / queued / unknown — show a small clock-ish dot.
  return (
    <span
      style={{
        color: "var(--muted)",
        fontSize: size - 2,
        lineHeight: 1,
        opacity: 0.7
      }}
      title={status}
    >
      ⏱
    </span>
  );
}
