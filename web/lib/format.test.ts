import { describe, expect, it } from "vitest";

import {
  fmtWhen,
  formatBRL,
  formatDate,
  formatMonth,
  formatPercent,
  formatPP,
  formatRate,
  formatSignedBRL,
} from "./format";

const NBSP = " ";
const MINUS = "−";

describe("formatBRL", () => {
  it("moeda completa com centavos e espaço não separável após R$", () => {
    expect(formatBRL(68695.66)).toBe(`R$${NBSP}68.695,66`);
    expect(formatBRL(1234567890.12)).toBe(`R$${NBSP}1.234.567.890,12`);
  });

  it("negativo com menos tipográfico antes da moeda", () => {
    expect(formatBRL(-163.8)).toBe(`${MINUS}R$${NBSP}163,80`);
  });

  it("zero (inclusive −0) sem sinal", () => {
    expect(formatBRL(0)).toBe(`R$${NBSP}0,00`);
    expect(formatBRL(-0)).toBe(`R$${NBSP}0,00`);
  });

  it("ruído que arredonda para zero não leva sinal", () => {
    expect(formatBRL(-0.004)).toBe(`R$${NBSP}0,00`);
    expect(formatBRL(-1e-12)).toBe(`R$${NBSP}0,00`);
    expect(formatSignedBRL(0.001)).toBe(`R$${NBSP}0,00`);
    expect(formatPercent(-0.001)).toBe("0,00%");
    expect(formatPP(-0.001)).toBe(`0,00${NBSP}p.p.`);
  });

  it("nunca abrevia", () => {
    expect(formatBRL(60000)).toBe(`R$${NBSP}60.000,00`);
    expect(formatBRL(2_500_000)).not.toMatch(/mil|k|MM/i);
  });
});

describe("formatSignedBRL (variação e resultado)", () => {
  it("sinal explícito nos dois lados", () => {
    expect(formatSignedBRL(682.1)).toBe(`+R$${NBSP}682,10`);
    expect(formatSignedBRL(-163.8)).toBe(`${MINUS}R$${NBSP}163,80`);
    expect(formatSignedBRL(0)).toBe(`R$${NBSP}0,00`);
  });
});

describe("formatPercent", () => {
  it("duas casas e sufixo de período opcional", () => {
    expect(formatPercent(55.48)).toBe("55,48%");
    expect(formatPercent(10.9, "a.a.")).toBe("10,90% a.a.");
    expect(formatPercent(0.87, "a.m.")).toBe("0,87% a.m.");
    expect(formatPercent(-2.5)).toBe(`${MINUS}2,50%`);
    expect(formatPercent(0)).toBe("0,00%");
  });
});

describe("formatRate (fração)", () => {
  it("0,0853 → 8,53%", () => {
    expect(formatRate(0.0853)).toBe("8,53%");
    expect(formatRate(-0.012)).toBe(`${MINUS}1,20%`);
    expect(formatRate(null)).toBe("—");
  });
});

describe("formatPP (desvio)", () => {
  it("p.p. com sinal e sem seta", () => {
    expect(formatPP(-3.6)).toBe(`${MINUS}3,60${NBSP}p.p.`);
    expect(formatPP(8.7)).toBe(`+8,70${NBSP}p.p.`);
    expect(formatPP(0)).toBe(`0,00${NBSP}p.p.`);
  });
});

describe("datas", () => {
  it("dd/mm/aaaa e mês minúsculo", () => {
    expect(formatDate("2026-10-14")).toBe("14/10/2026");
    expect(formatMonth("2026-10")).toBe("out/2026");
    expect(formatMonth("2024-07")).toBe("jul/2024");
  });
});

describe("normalizeMoneyInput", () => {
  it("pt-BR, en e sinal, sem float", async () => {
    const { normalizeMoneyInput } = await import("./format");
    expect(normalizeMoneyInput("1.234,56")).toBe("1234.56");
    expect(normalizeMoneyInput("42,9")).toBe("42.90");
    expect(normalizeMoneyInput("R$ 10")).toBe("10.00");
    expect(normalizeMoneyInput("-10")).toBe("-10.00");
    expect(normalizeMoneyInput("−42,90")).toBe("-42.90");
    expect(normalizeMoneyInput("0.5")).toBe("0.50");
    expect(normalizeMoneyInput("1.234.567")).toBe("1234567.00");
    expect(normalizeMoneyInput("12345678901234.99")).toBe("12345678901234.99");
  });

  it("recusa o que não é valor", async () => {
    const { normalizeMoneyInput } = await import("./format");
    for (const bad of ["", "abc", "1,2,3", "1.234,567", "--1"]) expect(normalizeMoneyInput(bad)).toBeNull();
  });
});

describe("fmtWhen", () => {
  it("mostra o horário de Brasília, qualquer que seja o fuso do navegador", () => {
    expect(fmtWhen("2026-10-18T01:30:00+00:00")).toBe("17/10/2026, 22:30");
    expect(fmtWhen(null)).toBe("—");
  });
});
