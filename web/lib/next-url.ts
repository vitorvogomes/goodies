// Volta ao lugar depois do login (Story 1.9 — AD-17): `/login?next=<rota+query>`.
// Só aceita caminho relativo do próprio app (nunca `//host`, URL absoluta ou o próprio /login).

const ORIGIN = "http://goodies.local";

export function safeNext(raw: string | null | undefined): string | null {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return null;
  // Tab/quebra de linha/controle e barra invertida somem ou viram "/" no parser de URL do navegador
  // ("/\t/evil.com" → "//evil.com"): recusa e confere que o destino continua na mesma origem.
  if (/[\u0000-\u001f\u007f\\]/.test(raw)) return null;
  if (new URL(raw, ORIGIN).origin !== ORIGIN) return null;
  if (raw === "/login" || raw.startsWith("/login?") || raw.startsWith("/login/")) return null;
  return raw;
}

export function loginUrl(pathname: string, search = ""): string {
  const next = safeNext(`${pathname}${search}`);
  return next && next !== "/" ? `/login?next=${encodeURIComponent(next)}` : "/login";
}
