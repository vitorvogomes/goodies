// Central de avisos (Story 3.1 — AD-10).
export type AlertSeverity = "divergencia" | "aviso";

export interface AlertAction {
  label: string;
  route: string;
  params: Record<string, string>;
}

export interface AppAlert {
  key: string;
  fingerprint: string;
  severity: AlertSeverity;
  message: string;
  action: AlertAction;
  as_of: string | null;
  dismissible: boolean;
}

export interface AlertList {
  items: AppAlert[];
  total: number;
  data_until: string | null;
}
