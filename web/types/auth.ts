// Espelha o backend de auth (ADR-006 — JWT custom no FastAPI). STORY-00-06.
export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  // ADR-006: o refresh token vem SÓ no cookie httpOnly, nunca no corpo.
  access_token: string;
  expires_in: number;
}

export interface RefreshResponse {
  access_token: string;
  expires_in: number;
}
