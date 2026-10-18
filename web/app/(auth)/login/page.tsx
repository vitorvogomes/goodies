"use client";

// Login (Story 1.9 — ADR-006, UX-DR45): tokens e componentes do DESIGN.md, mesmo fluxo JWT da v1.
// O access token fica só em memória; o refresh vem no cookie httpOnly. Depois de entrar, volta para
// `?next=` (rota + período) quando a sessão tinha expirado no meio do uso.
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, apiFetch } from "@/lib/api";
import { setAccessToken } from "@/lib/auth";
import { apiErrorMessage } from "@/lib/errors";
import { HOME } from "@/lib/nav";
import { safeNext } from "@/lib/next-url";
import type { LoginRequest, LoginResponse } from "@/types/auth";

function LoginForm() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
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
      router.replace(next ?? HOME);
    } catch (err) {
      const fallback = "Não foi possível conectar. Tente novamente.";
      setError(
        err instanceof ApiError
          ? err.status === 401
            ? "Email ou senha inválidos"
            : apiErrorMessage(err.detail, fallback)
          : fallback,
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-sm space-y-6 rounded-xl border border-border bg-card p-8 shadow-card">
      <div className="flex items-center gap-2">
        <span aria-hidden className="size-3 rounded-xs bg-positive" />
        <h1 className="font-mono text-lg font-semibold">goodies</h1>
      </div>
      {next && (
        <p className="type-body-sm text-muted-foreground">Sua sessão expirou. Entre para voltar de onde parou.</p>
      )}
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="h-10"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">Senha</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="h-10"
          />
        </div>
        {error && (
          <p role="alert" className="type-body-sm text-negative">
            {error}
          </p>
        )}
        <Button type="submit" disabled={loading} className="h-10 w-full">
          {loading ? "Entrando…" : "Entrar"}
        </Button>
      </form>
    </div>
  );
}

export default function LoginPage() {
  return (
    <main className="flex flex-1 items-center justify-center bg-background px-4">
      <Suspense>
        <LoginForm />
      </Suspense>
    </main>
  );
}
