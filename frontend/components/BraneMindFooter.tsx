type Props = {
  align?: "left" | "center";
};

export default function BraneMindFooter({ align = "left" }: Props) {
  return (
    <div
      style={{
        fontSize: "0.72rem",
        color: "var(--muted)",
        textAlign: align,
        letterSpacing: 0.2
      }}
    >
      Powered by{" "}
      <a
        href="https://www.branemind.com"
        target="_blank"
        rel="noopener noreferrer"
        style={{ color: "var(--accent)", fontWeight: 500 }}
      >
        BraneMind
      </a>
    </div>
  );
}
