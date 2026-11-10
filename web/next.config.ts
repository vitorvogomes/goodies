import type { NextConfig } from "next";

import { apiRewrites, securityHeaders } from "./lib/deploy-config";

// Story 10.6 — as telas da v1 saíram; cada endereço antigo leva à aba equivalente da v2 (rota v1 →
// substituto, registrado em docs/v2/stories/10.6-fim-das-telas-v1.md).
const V1_REDIRECTS: Array<[string, string]> = [
  ["/dashboard", "/visao-geral/painel"],
  ["/analise-ledger", "/visao-geral/historico"],
  ["/ledger", "/caixa/transacoes"],
  ["/ledger/new", "/caixa/transacoes"],
  ["/ledger/import", "/visao-geral/painel?importar=1"],
  ["/portfolio", "/investimentos/posicoes"],
  ["/portfolio/positions", "/investimentos/posicoes"],
  ["/portfolio/history", "/investimentos/posicoes"],
  ["/portfolio/import", "/visao-geral/painel?importar=1"],
  ["/portfolio/allocation", "/investimentos/posicoes"],
  ["/portfolio/rebalancing", "/investimentos/aportes"],
  ["/portfolio/transit", "/investimentos/conciliacao"],
  ["/market", "/ajustes/precos-manuais"],
  ["/wallets", "/ajustes/posicoes-manuais"],
  ["/wallets/reconciliation", "/investimentos/conciliacao"],
  ["/refresh", "/ajustes/atualizacao"],
];

const nextConfig: NextConfig = {
  reactCompiler: true,
  poweredByHeader: false,
  async redirects() {
    return V1_REDIRECTS.map(([source, destination]) => ({ source, destination, permanent: false }));
  },
  // ADR-018: /api/v1/* vai à api pela rede privada do Railway (só com API_INTERNAL_URL no build).
  async rewrites() {
    return apiRewrites(process.env.API_INTERNAL_URL);
  },
  async headers() {
    return securityHeaders();
  },
};

export default nextConfig;
