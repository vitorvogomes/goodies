import { describe, expect, it } from "vitest";

import { apiErrorMessage } from "./errors";

describe("apiErrorMessage", () => {
  it("lê a mensagem do contrato de erro", () => {
    const body = { detail: { error: "too_many_attempts", message: "Muitas tentativas. Tente de novo em 15 minutos." } };
    expect(apiErrorMessage(body, "x")).toBe("Muitas tentativas. Tente de novo em 15 minutos.");
  });

  it("aceita o detail direto", () => {
    expect(apiErrorMessage({ error: "e", message: "Falha ao gravar" }, "x")).toBe("Falha ao gravar");
  });

  it("cai no fallback com detail texto, vazio ou ausente", () => {
    expect(apiErrorMessage({ detail: "email ou senha inválidos" }, "padrão")).toBe("padrão");
    expect(apiErrorMessage(undefined, "padrão")).toBe("padrão");
    expect(apiErrorMessage({ detail: { message: "  " } }, "padrão")).toBe("padrão");
  });
});
