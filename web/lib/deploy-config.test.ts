// ADR-018 — o web é a única porta pública: repassa /api/v1 à api pela rede privada e manda os
// cabeçalhos de segurança.
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiRewrites, securityHeaders } from "./deploy-config";

describe("apiRewrites", () => {
  it("sem API_INTERNAL_URL (dev local) repassa para a api do compose", () => {
    const local = [
      { source: "/api/v1/:path*", destination: "http://127.0.0.1:8000/api/v1/:path*" },
    ];
    expect(apiRewrites(undefined)).toEqual(local);
    expect(apiRewrites("  ")).toEqual(local);
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

  it("é sempre a mesma origem: o browser chama /api/v1 e o Next repassa", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://outro-host:9999");
    vi.resetModules();
    const { API_BASE_URL } = await import("./api");
    expect(API_BASE_URL).toBe("");
  });
});
