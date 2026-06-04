// Espelha os schemas do backend (api/engines/ledger). m1.

export type AccountType = "bank" | "broker" | "crypto" | "manual";

export interface Account {
  id: string;
  name: string;
  type: AccountType;
  currency: string;
}

export interface AccountCreate {
  name: string;
  type: AccountType;
  currency?: string;
}

export type CategoryKind = "income" | "expense" | "investment" | "transfer";

export interface Category {
  id: string;
  name: string;
  kind: CategoryKind;
  is_active: boolean;
}

export interface Transaction {
  id: string;
  account_id: string;
  date: string;
  amount: number;
  category: string;
  description: string | null;
  is_recurring: boolean;
  external_id: string | null;
}

export interface TransactionList {
  items: Transaction[];
  total: number;
  limit: number;
  offset: number;
}

export interface TransactionCreate {
  account_id: string;
  date: string;
  amount: number;
  category: string;
  description?: string;
  is_recurring?: boolean;
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
  savings_rate: number;
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
