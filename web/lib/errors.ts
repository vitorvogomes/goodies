// Mensagem pt-BR de um erro da API (AD-15: detail = {"error": "<codigo>", "message": "<pt-BR>"}).
// Aceita o corpo cru da resposta ({detail: {...}}) ou o próprio detail; sem mensagem → fallback.
export function apiErrorMessage(body: unknown, fallback: string): string {
  const detail =
    body && typeof body === "object" && "detail" in body ? (body as { detail: unknown }).detail : body;
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as { message: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return fallback;
}
