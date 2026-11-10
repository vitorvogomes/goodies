// ADR-018 — produção no Railway: o web é a única porta pública.
// - `apiRewrites`: repassa /api/v1/* à api pela rede privada (API_INTERNAL_URL). Mesma origem → o cookie
//   httpOnly de refresh e o `proxy.ts` funcionam como em localhost (ADR-006). Os rewrites são resolvidos
//   no BUILD: a variável precisa existir no build do Railway. Sem ela (dev local), nada é repassado e o
//   browser fala direto com NEXT_PUBLIC_API_URL.
// - `securityHeaders`: cabeçalhos de segurança de todas as rotas.

export type Rewrite = { source: string; destination: string };
export type HeaderRule = { source: string; headers: Array<{ key: string; value: string }> };

export function apiRewrites(internalUrl: string | undefined): Rewrite[] {
  const base = internalUrl?.trim().replace(/\/+$/, "");
  if (!base) return [];
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
