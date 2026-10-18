import { describe, expect, it } from "vitest";

import { undoSummary } from "@/components/ingest/ImportHistory";

describe("undoSummary", () => {
  it("diz o efeito em números, como o Diálogo de desfazer mostra", () => {
    expect(
      undoSummary({
        batch_id: "x",
        applied_at: "2026-10-17T12:00:00Z",
        transactions: 43,
        operations: 2,
        categorizations: 38,
        rules: 2,
        balances: 0,
        snapshots: 0,
      }),
    ).toBe("Remove 43 transações, 2 operações, 38 categorizações e 2 regras do lote de 17/10/2026.");
  });
});
