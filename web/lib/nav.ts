// Navegação em 4 áreas (Story 1.7 — FR36, AD-17, EXPERIENCE › Information Architecture).
// Áreas e abas viram rotas `/(area)/(aba)`; endereços antigos redirecionam para a aba equivalente
// (`next.config.ts`). No celular as áreas vão para a navegação inferior (`BottomNav`, v2.2).

export type AreaKey = "visao-geral" | "caixa" | "investimentos" | "ajustes";

export interface Tab {
  slug: string;
  label: string;
  /** Story que entregou a aba. */
  story: string;
}

export interface Area {
  key: AreaKey;
  label: string;
  tabs: Tab[];
}

export const AREAS: Area[] = [
  {
    key: "visao-geral",
    label: "Visão geral",
    tabs: [
      { slug: "painel", label: "Painel", story: "4.1" },
      { slug: "historico", label: "Histórico", story: "9.1" },
    ],
  },
  {
    key: "caixa",
    label: "Caixa",
    tabs: [
      { slug: "transacoes", label: "Transações", story: "2.7" },
      { slug: "orcamento", label: "Orçamento", story: "6.6" },
      { slug: "custos-fixos", label: "Custos fixos", story: "6.2" },
    ],
  },
  {
    key: "investimentos",
    label: "Investimentos",
    tabs: [
      { slug: "posicoes", label: "Posições", story: "7.1" },
      { slug: "aportes", label: "Aportes", story: "8.4" },
      { slug: "conciliacao", label: "Conciliação", story: "7.9" },
    ],
  },
  {
    key: "ajustes",
    label: "Ajustes",
    tabs: [
      { slug: "categorias", label: "Categorias", story: "2.9" },
      { slug: "regras", label: "Regras", story: "2.10" },
      { slug: "custos-fixos", label: "Custos e receitas", story: "6.2" },
      { slug: "contas", label: "Contas", story: "10.1" },
      { slug: "objetivos", label: "Objetivos", story: "8.1" },
      { slug: "debentures", label: "Debêntures", story: "7.6" },
      { slug: "metas", label: "Metas", story: "8.2" },
      { slug: "precos-manuais", label: "Preços manuais", story: "10.2" },
      { slug: "posicoes-manuais", label: "Posições manuais", story: "7.8" },
      { slug: "atualizacao", label: "Atualização", story: "10.3" },
    ],
  },
];

export const HOME = "/visao-geral/painel";

export function getArea(key: AreaKey): Area {
  const area = AREAS.find((a) => a.key === key);
  if (!area) throw new Error(`área desconhecida: ${key}`);
  return area;
}

/** Área ativa da rota. */
export function areaOf(pathname: string): AreaKey | null {
  const first = pathname.split("/").filter(Boolean)[0] ?? "";
  return AREAS.find((a) => a.key === first)?.key ?? null;
}

/** Link de aba: mantém o período da URL; a leitura vale só para a aba e não é levada. */
export function tabHref(area: AreaKey, slug: string, search: URLSearchParams | null): string {
  const periodo = search?.get("periodo");
  return `/${area}/${slug}${periodo ? `?periodo=${periodo}` : ""}`;
}
