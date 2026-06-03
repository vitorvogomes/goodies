"use client";

// STORY-00-07 — tela de login. Sem lib de form (2 campos). access_token em
// memória (ADR-006, nunca localStorage); o refresh vem em cookie httpOnly do backend.
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";
import { setAccessToken } from "@/lib/auth";
import type { LoginRequest, LoginResponse } from "@/types/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await apiFetch<LoginResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password } satisfies LoginRequest),
      });
      setAccessToken(res.access_token);
      router.push("/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "Email ou senha inválidos"
          : "Não foi possível conectar. Tente novamente.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative flex flex-1 items-center justify-center overflow-hidden px-4">
      {/* atmosfera: glow sutil do accent */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-accent/20 blur-3xl"
      />
      <div className="relative w-full max-w-sm rounded-2xl border border-border bg-muted/60 p-8 shadow-2xl backdrop-blur">
        <div className="mb-8 text-center">
          <h1 className="font-mono text-2xl font-semibold tracking-tight text-foreground">
            Goodies
          </h1>
          <p className="mt-1 text-sm text-foreground/50">Controle financeiro pessoal</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5" noValidate>
          <div className="space-y-1.5">
            <label htmlFor="email" className="text-sm font-medium text-foreground/80">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-foreground outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/40"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="text-sm font-medium text-foreground/80">
              Senha
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-foreground outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/40"
            />
          </div>

          {error && (
            <p role="alert" className="text-sm text-loss">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-accent py-2.5 font-medium text-white transition hover:bg-accent/90 focus:outline-none focus:ring-2 focus:ring-accent/50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </div>
    </main>
  );
}
