// STORY-00-07 — proteção de rota (Next 16 renomeou middleware -> proxy).
// Sem o cookie httpOnly de refresh, redireciona p/ /login. Checa presença
// (não validade) — a validação real do JWT é no backend (ADR-006).
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { loginUrl } from "@/lib/next-url";

export function proxy(request: NextRequest) {
  if (request.cookies.has("refresh_token")) {
    return NextResponse.next();
  }
  // Sem sessão: /login?next=<rota+query> para voltar ao mesmo lugar e período (Story 1.9).
  const { pathname, search } = request.nextUrl;
  return NextResponse.redirect(new URL(loginUrl(pathname, search), request.url));
}

export const config = {
  // Tudo exceto /login, rotas de api e assets do Next.
  matcher: ["/((?!login|api|_next/static|_next/image|favicon.ico).*)"],
};
