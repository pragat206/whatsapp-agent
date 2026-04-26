import "../styles/globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Terra Rex WhatsApp Agent",
  description: "Terra Rex Energy AI support & campaigns dashboard"
};

// Runs before React hydrates, so the chosen theme is applied on first paint
// and there's no white-flash when the page loads in dark mode (or vice versa).
const NO_FLASH_THEME_SCRIPT = `
(function(){try{
  var t = localStorage.getItem('trx_theme');
  if (t !== 'dark' && t !== 'light') {
    t = matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }
  document.documentElement.setAttribute('data-theme', t);
}catch(e){
  document.documentElement.setAttribute('data-theme','dark');
}})();
`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" data-theme="dark">
      <head>
        <script dangerouslySetInnerHTML={{ __html: NO_FLASH_THEME_SCRIPT }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
