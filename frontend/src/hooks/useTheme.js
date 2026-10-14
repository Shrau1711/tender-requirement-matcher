import { useEffect, useState } from "react";

const KEY = "tender-matcher-theme";

function remembered() {
  try { return window.localStorage.getItem(KEY); } catch { return null; }
}

/** Light or dark: what the person chose last time, otherwise what their system prefers. */
export function useTheme() {
  const [theme, setTheme] = useState(() => remembered() ?? (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { window.localStorage.setItem(KEY, theme); } catch { /* the choice just is not remembered */ }
  }, [theme]);
  return [theme, () => setTheme(theme === "dark" ? "light" : "dark")];
}
