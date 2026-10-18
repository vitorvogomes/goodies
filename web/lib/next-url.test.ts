import { describe, expect, it } from "vitest";

import { loginUrl, safeNext } from "./next-url";

describe("loginUrl", () => {
  it("leva rota e query (período) no next", () => {
    expect(loginUrl("/caixa/orcamento", "?periodo=2026-09")).toBe(
      "/login?next=%2Fcaixa%2Forcamento%3Fperiodo%3D2026-09",
    );
  });

  it("raiz e o próprio login não viram next", () => {
    expect(loginUrl("/")).toBe("/login");
    expect(loginUrl("/login", "?next=%2Fx")).toBe("/login");
  });
});

describe("safeNext", () => {
  it("aceita só caminho relativo do app", () => {
    expect(safeNext("/caixa/orcamento?periodo=2026-09")).toBe("/caixa/orcamento?periodo=2026-09");
    expect(safeNext("//evil.com")).toBeNull();
    expect(safeNext("https://evil.com")).toBeNull();
    expect(safeNext("/\\evil.com")).toBeNull();
    expect(safeNext(null)).toBeNull();
    expect(safeNext("/login?next=/x")).toBeNull();
  });

  it("recusa caracteres que o parser de URL remove (open redirect)", () => {
    expect(safeNext("/\t/evil.com")).toBeNull();
    expect(safeNext("/\n/evil.com")).toBeNull();
    expect(safeNext("/\r/evil.com")).toBeNull();
    expect(safeNext("/caixa\\..\\x")).toBeNull();
  });
});
