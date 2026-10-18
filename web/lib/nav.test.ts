import { describe, expect, it } from "vitest";

import { AREAS, areaOf, tabHref } from "./nav";

describe("areaOf", () => {
  it("marca a área pela rota nova", () => {
    expect(areaOf("/caixa/orcamento")).toBe("caixa");
    expect(areaOf("/ajustes")).toBe("ajustes");
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

  it("sem telas da v1 (Story 10.6)", () => {
    expect(AREAS.every((a) => !("v1" in a))).toBe(true);
    expect(areaOf("/dashboard")).toBeNull(); // o endereço antigo só redireciona
  });
});
