// Teste "no raw color" (Story 1.5 — UX-DR3, DESIGN.md › Brand & Style).
// Fora de `app/globals.css` (o arquivo de tokens), nenhum .ts/.tsx/.css pode usar hex, rgb(), hsl(),
// oklch() ou classe de paleta do Tailwind (`text-red-500`, `bg-emerald-*`, `text-white`...).
// Telas v1 ainda não migradas ficam em EXCECOES_V1; a lista só pode diminuir: um arquivo da lista
// que fica limpo faz o teste falhar até sair dela.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = join(__dirname, "..");
const DIRS = ["app", "components", "lib"];
const TOKENS_FILE = "app/globals.css";

const EXCECOES_V1: readonly string[] = [
  "app/(app)/portfolio/allocation/page.tsx", // pizza v1 com paleta própria; sai com a Story 10.6
];

const PALETTE =
  "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose";
const UTIL =
  "text|bg|border|border-[trblxy]|ring|ring-offset|fill|stroke|from|via|to|outline|decoration|divide|placeholder|caret|accent|shadow|inset-shadow";
const RULES: Array<[string, RegExp]> = [
  ["hex", /(?<![\w&/-])#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b/g],
  ["função de cor", /\b(?:rgba?|hsla?|oklch|oklab|lab|lch|hwb)\(/g],
  ["classe de paleta", new RegExp(`(?<![\\w-])(?:[\\w-]+:)*(?:${UTIL})-(?:(?:${PALETTE})-\\d{2,3}|white|black)\\b`, "g")],
];

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return files(path);
    return /\.(tsx?|css)$/.test(name) && !/\.test\.ts$/.test(name) ? [path] : [];
  });
}

function violations(path: string): string[] {
  const out: string[] = [];
  readFileSync(path, "utf8")
    .split("\n")
    .forEach((line, i) => {
      for (const [kind, re] of RULES) {
        for (const m of line.matchAll(re)) out.push(`${relative(ROOT, path)}:${i + 1} ${kind} "${m[0]}"`);
      }
    });
  return out;
}

const all = DIRS.flatMap((d) => files(join(ROOT, d))).filter((p) => relative(ROOT, p) !== TOKENS_FILE);

describe("no raw color", () => {
  it("nenhuma cor crua fora de globals.css (salvo exceções v1)", () => {
    const found = all.filter((p) => !EXCECOES_V1.includes(relative(ROOT, p))).flatMap(violations);
    expect(found, found.join("\n")).toEqual([]);
  });

  it("a lista de exceções v1 só diminui (arquivo limpo sai da lista)", () => {
    const clean = EXCECOES_V1.filter((f) => violations(join(ROOT, f)).length === 0);
    expect(clean, `remova de EXCECOES_V1: ${clean.join(", ")}`).toEqual([]);
  });

  it("o detector pega os casos do DESIGN.md", () => {
    const sample = 'a "#fff" rgb(1,2,3) oklch(0.5 0 0) text-red-500 hover:bg-emerald-600 text-white';
    const hits = RULES.flatMap(([, re]) => [...sample.matchAll(re)].map((m) => m[0]));
    expect(hits).toEqual(["#fff", "rgb(", "oklch(", "text-red-500", "hover:bg-emerald-600", "text-white"]);
  });
});
