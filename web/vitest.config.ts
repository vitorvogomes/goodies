import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

// Vitest só em utilitários puros e guarda-corpos (AD-19): sem DOM, sem componente.
export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL(".", import.meta.url)) } },
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts", "lib/**/*.test.ts"],
  },
});
