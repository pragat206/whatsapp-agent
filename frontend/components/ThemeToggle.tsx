"use client";
import { useEffect, useState } from "react";

type Theme = "dark" | "light";

const STORAGE_KEY = "trx_theme";

function applyTheme(theme: Theme) {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", theme);
}

function readTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  const stored = window.localStorage.getItem(STORAGE_KEY) as Theme | null;
  if (stored === "dark" || stored === "light") return stored;
  if (window.matchMedia?.("(prefers-color-scheme: light)").matches) return "light";
  return "dark";
}

export default function ThemeToggle() {
  // Defer to the no-flash inline script (in layout.tsx) for the initial value
  // so SSR markup matches the first client render.
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    setTheme(readTheme());
  }, []);

  function flip() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    applyTheme(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* localStorage unavailable — theme still applies for the session */
    }
  }

  const isDark = theme === "dark";
  return (
    <button
      type="button"
      onClick={flip}
      title={`Switch to ${isDark ? "light" : "dark"} mode`}
      aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0.4rem 0.7rem",
        fontSize: "0.82rem"
      }}
    >
      <span>{isDark ? "Dark mode" : "Light mode"}</span>
      <span aria-hidden="true">{isDark ? "🌙" : "☀️"}</span>
    </button>
  );
}
