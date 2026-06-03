// Gestão do access token — ADR-006: em memória, NUNCA em localStorage.
// O refresh token vive em httpOnly cookie setado pelo backend (não acessível ao JS).

let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function clearAccessToken(): void {
  accessToken = null;
}
