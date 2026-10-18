// Espelha os schemas do backend (api/engines/ledger). m1.

export type AccountType = "bank" | "broker" | "crypto" | "manual";

export interface Account {
  id: string;
  name: string;
  type: AccountType;
  currency: string;
  account_number: string | null;
}

export interface AccountCreate {
  name: string;
  type: AccountType;
  currency?: string;
  account_number?: string;
}

export type CategoryKind = "income" | "expense" | "investment" | "transfer";

export interface Category {
  id: string;
  name: string;
  kind: CategoryKind;
  is_active: boolean;
  match_patterns: string[];
}

export interface CategoryCreate {
  name: string;
  kind: CategoryKind;
  match_patterns?: string[];
}

export interface CategoryUpdate {
  name?: string;
  kind?: CategoryKind;
  is_active?: boolean;
  match_patterns?: string[];
}

export interface FixedCost {
  id: string;
  name: string;
  amount: number;
  due_day: number;
  category: string;
  is_active: boolean;
}

export interface FixedCostCreate {
  name: string;
  amount: number;
  due_day: number;
  category: string;
  is_active?: boolean;
}

export interface CategoryBreakdownRow {
  category: string;
  total: number;
  pct: number;
}

export interface CategoryBreakdown {
  month: string | null;
  income_total: number;
  expense_total: number;
  investment_total: number;
  income: CategoryBreakdownRow[];
  expense: CategoryBreakdownRow[];
  investment: CategoryBreakdownRow[];
}

export interface Transaction {
  id: string;
  account_id: string;
  date: string;
  amount: number;
  category: string;
  kind: CategoryKind;
  description: string | null;
  is_recurring: boolean;
  external_id: string | null;
  notes: string | null;
}

export interface TransactionList {
  items: Transaction[];
  total: number;
  limit: number;
  offset: number;
  total_income: number;
  total_expense: number;
  total_invested: number;
  total_transfer: number;
  transfer_count: number;
}

export interface TransactionCreate {
  account_id: string;
  date: string;
  amount: number;
  category: string;
  kind?: CategoryKind;
  description?: string;
  is_recurring?: boolean;
  notes?: string;
}

export interface TransactionFilters {
  account_id?: string;
  category?: string;
  from?: string;
  to?: string;
  limit?: number;
  offset?: number;
}

export interface MonthlySummary {
  month: string;
  total_income: number;
  total_expense: number;
  net_cashflow: number;
  savings_rate: number | null; // null = sem receita do trabalho (Story 2.6)
  total_invested: number;
  investment_rate: number;
}

export interface ProjectionPoint {
  days: number;
  fixed_income: number;
  fixed_expenses: number;
  projected_balance: number;
}

export interface CashflowProjection {
  current_balance: number;
  monthly_income: number;
  monthly_expenses: number;
  projections: ProjectionPoint[];
}

export interface Alert {
  type: string;
  severity: string;
  title: string;
  message: string;
  data: Record<string, string | number>;
}

export interface ImportReport {
  parsed: number;
  imported: number;
  duplicates: number;
  skipped: number;
  errors: number;
  by_kind: Record<string, number>; // novas por kind (income/expense/investment/transfer)
}

// D — sugestão híbrida: despesa em "outros" + categoria proposta pelo histórico.
export interface Suggestion {
  transaction_id: string;
  date: string;
  description: string;
  amount: number;
  suggested_category: string;
  score: number;
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
