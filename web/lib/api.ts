// Cliente HTTP base para o FastAPI — STORY-00-06.
// Injeta o Authorization Bearer (access token em memória) e envia o cookie
// httpOnly do refresh (credentials: "include"). Base URL via NEXT_PUBLIC_API_URL.
import { clearAccessToken, getAccessToken, setAccessToken } from "@/lib/auth";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// Renova o access token usando o cookie httpOnly de refresh. Deduplicado: várias
// requisições que tomam 401 ao mesmo tempo compartilham uma única chamada em voo.
// Não passa pelo apiFetch (evita recursão).
let refreshInFlight: Promise<boolean> | null = null;

export function refreshAccessToken(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include", // envia o cookie refresh_token (httpOnly)
    })
      .then(async (res) => {
        if (!res.ok) {
          clearAccessToken();
          return false;
        }
        const data = (await res.json()) as { access_token: string };
        setAccessToken(data.access_token);
        return true;
      })
      .catch(() => {
        clearAccessToken();
        return false;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  // Access token expirado: tenta renovar via cookie e repete a requisição 1x.
  // Não tenta refresh nas próprias rotas de auth (login/refresh).
  if (res.status === 401 && retry && !path.startsWith("/api/v1/auth/")) {
    const refreshed = await refreshAccessToken();
    if (refreshed) return apiFetch<T>(path, options, false);
    // refresh falhou (sessão realmente expirou) → volta pro login.
    if (typeof window !== "undefined") window.location.href = "/login";
  }

  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    throw new ApiError(res.status, `Request failed with ${res.status}`, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
