// ADR-018 — produção no Railway: o web é a única porta pública.
// - `apiRewrites`: o browser só fala com a própria origem (/api/v1/...) e o Next repassa à api —
//   no Railway pela rede privada (API_INTERNAL_URL), no dev para a api do compose (127.0.0.1:8000, a porta
//   publicada só em IPv4). Mesma origem → o cookie httpOnly de refresh e o `proxy.ts` funcionam igual nos
//   dois (ADR-006) e não há CORS. No `next build` o destino é gravado no BUILD: a variável precisa
//   existir no build do Railway.
// - `API_PROXY_TIMEOUT_MS`: quanto o rewrite espera a api. O padrão do Next (30 s) corta o "Atualizar tudo"
//   (POST /jobs/refresh roda os jobs em série, com backup e restore_check) e o browser recebe 500.
// - `securityHeaders`: cabeçalhos de segurança de todas as rotas.

export type Rewrite = { source: string; destination: string };
export type HeaderRule = { source: string; headers: Array<{ key: string; value: string }> };

export const LOCAL_API_URL = "http://127.0.0.1:8000";
export const API_PROXY_TIMEOUT_MS = 300_000;

export function apiRewrites(internalUrl: string | undefined): Rewrite[] {
  const base = internalUrl?.trim().replace(/\/+$/, "") || LOCAL_API_URL;
  return [{ source: "/api/v1/:path*", destination: `${base}/api/v1/:path*` }];
}

export function securityHeaders(): HeaderRule[] {
  return [
    {
      source: "/:path*",
      headers: [
        { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      ],
    },
  ];
}
