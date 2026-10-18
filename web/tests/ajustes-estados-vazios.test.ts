// Story 10.4 — as 10 abas de Ajustes seguem os estados vazios do EXPERIENCE (Navigation › Ajustes):
// cada aba existe como página própria e traz a frase exata do estado vazio.
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const AJUSTES = join(__dirname, "..", "app", "(app)", "ajustes");

const VAZIOS: Record<string, string | null> = {
  categorias: "Nenhuma categoria. Crie o primeiro grupo.",
  regras: "Nenhuma regra. Regras nascem na revisão quando você corrige uma categoria.",
  "custos-fixos": "Nenhum custo fixo. Cadastre para acompanhar pago × pendente.",
  contas: "Nenhuma conta. Cadastre a conta Nubank PF.",
  objetivos: "Nenhum objetivo além da reserva de emergência.",
  debentures: "Nenhuma debênture. Cadastre para valorar pela taxa.",
  metas: "Nenhuma meta. Sem metas, a distribuição do aporte não tem base.",
  "precos-manuais": "Nenhum ativo sem fonte de mercado.",
  "posicoes-manuais": "Nenhuma posição manual. Cadastre o que nenhum scan alcança.",
  atualizacao: null, // sem estado vazio no EXPERIENCE (os jobs sempre existem)
};

describe("Ajustes › estados vazios", () => {
  for (const [aba, frase] of Object.entries(VAZIOS)) {
    it(aba, () => {
      const page = join(AJUSTES, aba, "page.tsx");
      expect(existsSync(page)).toBe(true);
      if (!frase) return;
      // o estado vazio pode vir como título + frase (DESIGN › empty-state): cada frase está lá
      const source = readFileSync(page, "utf8");
      for (const sentence of frase.match(/[^.]+\./g) ?? []) expect(source).toContain(sentence.trim());
    });
  }
});
