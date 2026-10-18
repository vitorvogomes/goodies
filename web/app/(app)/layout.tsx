// Layout da área autenticada: aplica o AppShell (4 áreas + gate) às áreas novas e às telas v1.
// Route group (app) não altera as URLs.
import type { ReactNode } from "react";

import { AppShell } from "@/components/AppShell";

export default function AppLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
