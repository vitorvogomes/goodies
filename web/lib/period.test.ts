import { describe, expect, it } from "vitest";

import {
  currentMonthBRT,
  isSelectable,
  MIN_MONTH,
  normalizePeriodo,
  resolvePeriod,
  shiftMonth,
} from "./period";

// 01/11/2026 01:30 UTC = 31/10/2026 22:30 em São Paulo
const NOW = new Date("2026-11-01T01:30:00Z");

describe("currentMonthBRT", () => {
  it("usa o fuso de São Paulo, não UTC", () => {
    expect(currentMonthBRT(NOW)).toBe("2026-10");
  });
});

describe("normalizePeriodo", () => {
  it("sem período → mês atual (BRT)", () => {
    expect(normalizePeriodo(null, NOW)).toBe("2026-10");
    expect(normalizePeriodo("lixo", NOW)).toBe("2026-10");
    expect(normalizePeriodo("2026-13", NOW)).toBe("2026-10");
  });

  it("anterior a jul/2024 cai em jul/2024; futuro cai no mês atual", () => {
    expect(normalizePeriodo("2023-05", NOW)).toBe(MIN_MONTH);
    expect(normalizePeriodo("2027-01", NOW)).toBe("2026-10");
    expect(normalizePeriodo("2025-02", NOW)).toBe("2025-02");
  });
});

describe("isSelectable / shiftMonth", () => {
  it("bloqueia futuro e antes de jul/2024", () => {
    expect(isSelectable("2024-06", NOW)).toBe(false);
    expect(isSelectable("2024-07", NOW)).toBe(true);
    expect(isSelectable("2026-10", NOW)).toBe(true);
    expect(isSelectable("2026-11", NOW)).toBe(false);
  });

  it("anda entre anos", () => {
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
    expect(shiftMonth("2025-12", 1)).toBe("2026-01");
  });
});

describe("resolvePeriod", () => {
  it("mes", () => {
    expect(resolvePeriod("2026-10", "mes")).toEqual(["2026-10"]);
  });

  it("tri = trimestre civil até o período", () => {
    expect(resolvePeriod("2026-11", "tri")).toEqual(["2026-10", "2026-11"]);
    expect(resolvePeriod("2026-03", "tri")).toEqual(["2026-01", "2026-02", "2026-03"]);
    expect(resolvePeriod("2026-07", "tri")).toEqual(["2026-07"]);
  });

  it("ano = jan até o período", () => {
    expect(resolvePeriod("2026-04", "ano")).toEqual(["2026-01", "2026-02", "2026-03", "2026-04"]);
  });

  it("inicio = jul/2024 até o período; o ano de 2024 começa em jul", () => {
    const all = resolvePeriod("2025-01", "inicio");
    expect(all[0]).toBe("2024-07");
    expect(all.at(-1)).toBe("2025-01");
    expect(all).toHaveLength(7);
    expect(resolvePeriod("2024-09", "ano")).toEqual(["2024-07", "2024-08", "2024-09"]);
    expect(resolvePeriod("2024-08", "tri")).toEqual(["2024-07", "2024-08"]);
  });
});
