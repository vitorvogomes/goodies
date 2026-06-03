---
tipo: story
epico: EPIC-00
story: STORY-00-06
titulo: Setup Next.js com TypeScript e Tailwind
status: pendente
estimativa: M (2-3h)
tags: [goodies, story, foundation, nextjs, frontend]
---

# STORY-00-06 — Setup Next.js

**Como** desenvolvedor  
**Quero** ter o Next.js 14 configurado com TypeScript, Tailwind e cliente HTTP  
**Para** construir o frontend de forma tipada e estilizada

---

## Critérios de aceite

- [ ] `web/` com `create-next-app` (App Router, TypeScript, Tailwind)
- [ ] `web/lib/api.ts` — cliente HTTP base para o FastAPI (wrapper sobre `fetch` com auth header automático)
- [ ] `web/lib/auth.ts` — gestão de JWT: armazenar `access_token` em memória, `refresh_token` em httpOnly cookie
- [ ] `web/types/` — tipos TypeScript espelhando modelos do backend (começar com `health`, `auth`)
- [ ] React Query (TanStack Query) configurado com `QueryClientProvider`
- [ ] Tema Tailwind customizado (cores do Goodies — dark mode por padrão)
- [ ] Página `app/page.tsx` redirecionando para `/dashboard` (ou `/login` se não autenticado)
- [ ] `next.config.js` com `NEXT_PUBLIC_API_URL` configurado

## Notas de implementação
- `pnpm` para gerenciamento de pacotes
- `next-themes` para dark mode (dark-only no MVP mas preparado para toggle futuro)
- `@tanstack/react-query` versão 5

## Dependências
STORY-00-01 concluída.
