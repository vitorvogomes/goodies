// STORY-00-07 — proteção de rota (Next 16 renomeou middleware -> proxy).
// Sem o cookie httpOnly de refresh, redireciona p/ /login. Checa presença
// (não validade) — a validação real do JWT é no backend (ADR-006).
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  if (request.cookies.has("refresh_token")) {
    return NextResponse.next();
  }
  const url = request.nextUrl.clone();
  url.pathname = "/login";
  return NextResponse.redirect(url);
}

export const config = {
  // Tudo exceto /login, rotas de api e assets do Next.
  matcher: ["/((?!login|api|_next/static|_next/image|favicon.ico).*)"],
};
