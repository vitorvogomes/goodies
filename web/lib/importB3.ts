// A5 — import de relatórios B3 (.xlsx) via corpo cru (octet-stream; sem multipart,
// como o import do ledger). Dois passos: dry-run (prévia) e confirm. O backend
// detecta o tipo pela aba e aplica a regra de cobertura (não dobra trade-vs-liquidação);
// idempotente por hash. Invalida o portfólio só no confirm.
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { ImportB3Report } from "@/types/portfolio";

export function useImportB3() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, dryRun }: { file: File; dryRun: boolean }) =>
      file.arrayBuffer().then((buf) =>
        apiFetch<ImportB3Report>(
          `/api/v1/portfolio/import-b3?dry_run=${dryRun}&filename=${encodeURIComponent(file.name)}`,
          {
            method: "POST",
            body: buf,
            headers: { "Content-Type": "application/octet-stream" },
          },
        ),
      ),
    onSuccess: (_data, vars) => {
      if (!vars.dryRun) {
        queryClient.invalidateQueries({ queryKey: ["portfolio"] });
        queryClient.invalidateQueries({ queryKey: ["market"] });
      }
    },
  });
}
