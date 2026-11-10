// ADR-018 — o web é a única porta pública: repassa /api/v1 à api pela rede privada e manda os
// cabeçalhos de segurança.
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiRewrites, securityHeaders } from "./deploy-config";

describe("apiRewrites", () => {
  it("sem API_INTERNAL_URL (dev local) não repassa nada", () => {
    expect(apiRewrites(undefined)).toEqual([]);
    expect(apiRewrites("  ")).toEqual([]);
  });

  it("repassa /api/v1/* para a api interna, sem barra dupla", () => {
    expect(apiRewrites("http://api.railway.internal:8000/")).toEqual([
      {
        source: "/api/v1/:path*",
        destination: "http://api.railway.internal:8000/api/v1/:path*",
      },
    ]);
  });
});

describe("securityHeaders", () => {
  it("vale para todas as rotas e bloqueia iframe, sniffing e referrer completo", () => {
    const [rule] = securityHeaders();
    expect(rule.source).toBe("/:path*");
    const byKey = Object.fromEntries(rule.headers.map((h) => [h.key, h.value]));
    expect(byKey["Strict-Transport-Security"]).toContain("max-age=");
    expect(byKey["X-Frame-Options"]).toBe("DENY");
    expect(byKey["Content-Security-Policy"]).toBe("frame-ancestors 'none'");
    expect(byKey["X-Content-Type-Options"]).toBe("nosniff");
    expect(byKey["Referrer-Policy"]).toBe("strict-origin-when-cross-origin");
  });
});

describe("API_BASE_URL", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("NEXT_PUBLIC_API_URL vazio (produção) usa a mesma origem", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.resetModules();
    const { API_BASE_URL } = await import("./api");
    expect(API_BASE_URL).toBe("");
  });

  it("sem NEXT_PUBLIC_API_URL (dev) cai na api local", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", undefined);
    vi.resetModules();
    const { API_BASE_URL } = await import("./api");
    expect(API_BASE_URL).toBe("http://localhost:8000");
  });
});
