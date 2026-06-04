// Layout da área autenticada (m1): aplica o AppShell (sidebar + gate) a
// /dashboard, /ledger e /ledger/new. Route group (app) não altera as URLs.
import type { ReactNode } from "react";

import { AppShell } from "@/components/AppShell";

export default function AppLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
