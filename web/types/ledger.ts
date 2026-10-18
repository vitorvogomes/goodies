// Espelha os schemas do backend (api/engines/ledger). m1.

export type AccountType = "bank" | "broker" | "crypto" | "manual";

export interface Account {
  id: string;
  name: string;
  type: AccountType;
  currency: string;
  account_number: string | null;
  holder: "pf" | "mei" | null; // Story 10.1
  fonte: string | null;
  conferencia: boolean; // saldo conferido (só a PF)
}

export interface AccountCreate {
  name: string;
  type: AccountType;
  currency?: string;
  account_number?: string;
  holder?: "pf" | "mei";
}

export interface FixedCost {
  id: string;
  name: string;
  amount: number;
  due_day: number;
  category: string;
  is_active: boolean;
}

// ---- v2: /api/v1/ledger/* (Story 2.7) ----
export type CategorySource = "rule" | "suggestion" | "manual";

export interface LedgerTransaction {
  id: string;
  date: string;
  description: string | null;
  amount: number;
  kind: string;
  kind_label: string;
  category_id: string;
  category_name: string;
  category_key: string;
  group_name: string;
  category_source: CategorySource;
  review_status: "pending" | "confirmed";
  payer: string | null;
  account_id: string;
  account_name: string;
  source: string;
  batch_id: string | null;
  file_name: string | null;
  rule_pattern: string | null;
  asset_id: string | null; // caixinha/CDB da transação (Story 7.5)
  rule_id: string | null; // a regra que categorizou
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface CategoryOption {
  id: string;
  key: string;
  name: string;
  label: string;
  group_key: string;
  group_name: string;
  kind: string;
  role: string;
  is_active: boolean;
}

// ---- v2: Ajustes › Categorias (Story 2.9) ----
export type GroupKind = "income" | "expense" | "investment" | "transfer";

export interface CategoryNode {
  id: string;
  key: string;
  name: string;
  group_id: string;
  kind: GroupKind;
  role: string;
  role_label: string;
  is_active: boolean;
  is_system: boolean;
  transaction_count: number;
}

export interface CategoryGroupNode {
  id: string;
  key: string;
  name: string;
  kind: GroupKind;
  kind_label: string;
  is_active: boolean;
  is_system: boolean;
  transaction_count: number;
  categories: CategoryNode[];
}

// ---- v2: Ajustes › Regras (Story 2.10) ----
export type RuleDirection = "entrada" | "saida" | "ambos";

export interface CategoryRule {
  id: string;
  pattern: string;
  direction: RuleDirection;
  category_id: string;
  category_label: string;
  is_active: boolean;
  origin: string;
  created_at: string;
}

export interface RuleMatch {
  id: string;
  date: string;
  description: string | null;
  amount: number;
  category_label: string;
}

export interface RulePreview {
  total: number;
  items: RuleMatch[];
}

export interface ReapplyChange {
  transaction_id: string;
  date: string;
  description: string | null;
  amount: number;
  before: string;
  after: string;
  rule_pattern: string;
}

export interface ReapplyPreview {
  changes: ReapplyChange[];
  manual_unchanged: number;
  closed_months: number;
}

// ---- v2: Revisão de transações (Story 3.10) ----
export type ReviewOrigin = "regra" | "sugestao" | "sem_sugestao" | "manual";

export interface ReviewItem {
  id: string;
  date: string;
  month: string;
  description: string | null;
  amount: number;
  account_name: string;
  category_id: string;
  category_label: string;
  category_kind: string;
  origin: ReviewOrigin;
  rule_pattern: string | null;
  // Story 7.6: aporte em debênture sugerido (só saída sem operação ligada)
  debenture: { contribution_id: string; label: string; amount: number } | null;
}

export interface ReviewMonth {
  month: string;
  count: number;
  entradas: number;
  saidas: number;
}

export interface ReviewList {
  items: ReviewItem[];
  months: ReviewMonth[];
  total: number;
}

export interface RuleProposal {
  pattern: string;
  direction: RuleDirection;
  category_id: string;
  category_label: string;
  affected: number;
}

// ---- v2: conferência de saldo (Story 3.13) ----
export interface BalanceCandidates {
  start: string;
  end: string;
  difference: number;
  items: {
    id: string;
    date: string;
    description: string | null;
    amount: number;
    category_label: string;
  }[];
}

// Custos fixos v2 (Story 6.1) — Ajustes › Custos fixos.
export interface FixedCostItem {
  id: string;
  name: string;
  amount: number;
  due_day: number;
  category_id: string | null;
  category_label: string;
  valid_from: string;
  valid_to: string | null;
}

export interface FixedCostItemIn {
  name?: string;
  amount?: string; // "123.45" (Money em string, AD-4)
  due_day?: number;
  category_id?: string;
}

// Caixa › Custos fixos (Story 6.2): o mês com casamento.
export interface FixedCostTx {
  id: string;
  date: string;
  description: string | null;
  amount: number;
}

export type FixedCostStatus = "pago" | "manual" | "pendente" | "vencendo" | "atrasado";

export interface FixedCostMonthItem {
  id: string;
  name: string;
  amount: number;
  due_date: string;
  category_label: string;
  status: FixedCostStatus;
  source: "decisao" | "auto" | null;
  transaction: FixedCostTx | null;
  candidates: FixedCostTx[];
}

export interface FixedCostMonth {
  month: string;
  closed: boolean;
  items: FixedCostMonthItem[];
  count: number;
  paid_count: number;
  total: number;
  paid_total: number;
  pending_total: number;
  as_of: string | null;
}

export type FixedCostDecisionKind = "confirmado" | "corrigido" | "manual" | "desfeito";
