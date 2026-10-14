import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(process.cwd(), "src", "styles", "tokens.css"), "utf8");

function block(selector) {
  const start = css.indexOf(`${selector} {`);
  return css.slice(start, css.indexOf("}", start));
}
const read = (text) => Object.fromEntries([...text.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]));
const light = read(block(":root"));
const dark = { ...light, ...read(block(':root[data-theme="dark"]')) };

const channel = (hex, i) => {
  const c = parseInt(hex.slice(1 + 2 * i, 3 + 2 * i), 16) / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
};
const luminance = (hex) => 0.2126 * channel(hex, 0) + 0.7152 * channel(hex, 1) + 0.0722 * channel(hex, 2);
const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

// [text colour, background colour]: every pair the interface actually uses for text
const PAIRS = [
  ["ink", "page"], ["ink", "surface"], ["ink-soft", "surface"], ["ink-soft", "surface-2"], ["ink-soft", "page"],
  ["on-brand", "brand"], ["brand-text", "surface"], ["brand-text", "page"], ["brand-text", "brand-tint"], ["on-brand-tint", "brand-tint"],
  ["on-slate", "slate"], ["full", "full-soft"], ["partial", "partial-soft"], ["missing", "missing-soft"], ["unsupported", "unsupported-soft"],
  ["missing", "surface"], ["ink", "brand-tint"], ["on-bar", "bar"],
];

describe.each([["light", light], ["dark", dark]])("%s theme", (_, theme) => {
  it.each(PAIRS)("%s on %s meets WCAG AA (4.5:1) for text", (fg, bg) => {
    expect(contrast(theme[fg], theme[bg]), `${fg} ${theme[fg]} on ${bg} ${theme[bg]}`).toBeGreaterThanOrEqual(4.5);
  });
});
