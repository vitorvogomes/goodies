import { describe, expect, it } from "vitest";

import { AREAS, areaOf, tabHref } from "./nav";

describe("areaOf", () => {
  it("marca a área pela rota nova", () => {
    expect(areaOf("/caixa/orcamento")).toBe("caixa");
    expect(areaOf("/ajustes")).toBe("ajustes");
  });

  it("marca a área das telas v1", () => {
    expect(areaOf("/dashboard")).toBe("visao-geral");
    expect(areaOf("/ledger/import")).toBe("caixa");
    expect(areaOf("/portfolio/positions")).toBe("investimentos");
    expect(areaOf("/wallets/reconciliation")).toBe("investimentos");
    expect(areaOf("/refresh")).toBe("ajustes");
  });

  it("devolve null fora das áreas", () => {
    expect(areaOf("/login")).toBeNull();
    expect(areaOf("/dev/tema")).toBeNull();
  });
});

describe("tabHref", () => {
  it("leva o período e descarta a leitura", () => {
    const q = new URLSearchParams("periodo=2026-10&leitura=tri");
    expect(tabHref("caixa", "orcamento", q)).toBe("/caixa/orcamento?periodo=2026-10");
    expect(tabHref("caixa", "orcamento", null)).toBe("/caixa/orcamento");
  });
});

describe("AREAS", () => {
  it("tem as 4 áreas e as 10 abas de Ajustes", () => {
    expect(AREAS.map((a) => a.label)).toEqual(["Visão geral", "Caixa", "Investimentos", "Ajustes"]);
    expect(AREAS[3].tabs).toHaveLength(10);
  });

  it("cada tela v1 aparece numa área só", () => {
    const hrefs = AREAS.flatMap((a) => a.v1.map((l) => l.href));
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });
});
