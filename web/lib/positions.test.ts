import { describe, expect, it } from "vitest";

import { reconciliationSummary } from "@/lib/positions";
import type { Reconciliation } from "@/types/positions";

const row = { symbol: "BTC", cls: "cripto", app: "1", origin: "1", diff: "0", status: "conferido" as const };

function recon(over: Partial<Reconciliation> = {}): Reconciliation {
  return {
    b3: { ref_date: "2026-09-30", rows: [] },
    wallets: { scanned_at: "2026-10-18T01:30:00+00:00", attempt_at: null, stale: false, rows: [row] },
    all_ok: true,
    ...over,
  };
}

describe("reconciliationSummary", () => {
  it("cita o consolidado e a data BRT do scan", () => {
    expect(reconciliationSummary(recon())).toBe(
      "Tudo bate com o consolidado B3 de 30/09/2026 e com as carteiras de 17/10/2026.",
    );
  });
  it("sem carteiras cita só o consolidado", () => {
    const r = recon({ wallets: { scanned_at: null, attempt_at: null, stale: false, rows: [] } });
    expect(reconciliationSummary(r)).toBe("Tudo bate com o consolidado B3 de 30/09/2026.");
  });
  it("nada quando algo diverge ou não há consolidado", () => {
    expect(reconciliationSummary(recon({ all_ok: false }))).toBeNull();
    expect(reconciliationSummary(recon({ b3: { ref_date: null, rows: [] } }))).toBeNull();
  });
});
