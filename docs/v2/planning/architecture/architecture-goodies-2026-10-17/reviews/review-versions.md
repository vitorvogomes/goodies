# Review — versões e checagem de realidade da Stack

- **Alvo:** `../ARCHITECTURE-SPINE.md` (§ Stack + tecnologias citadas em AD-17/AD-18)
- **Lente:** cada decisão foi pesquisada ou conferida (lockfile, registry, docs atuais), e não só afirmada?
- **Data:** 2026-10-17
- **Fontes conferidas:** `api/uv.lock`, `api/pyproject.toml`, `api/Dockerfile`, `.github/workflows/deploy.yml`,
  `web/package.json`, `web/pnpm-lock.yaml`, `web/next.config.ts`, `web/eslint.config.mjs` (config
  resolvida), `web/app/providers.tsx`, `web/app/globals.css`, `docker-compose.yml`; npm registry
  (`npm view … version/time/peerDependencies`), PyPI JSON, GitHub Advisory DB (`gh api /advisories`),
  registry do shadcn (`ui.shadcn.com/r/styles/*/*.json`), tarball do `shadcn@4.22.0`, docs do shadcn,
  TanStack e react.dev.

## Veredito

As linhas do backend e as versões já instaladas do web batem com os lockfiles. Mas quatro decisões
do frontend não foram conferidas na realidade atual: a versão travada do Next tem advisories
críticos; o shadcn CLI 4.x agora usa Base UI por padrão, não Radix; TanStack Table v8 não é
compatível com o React Compiler, que está ligado; e o next-themes tem um bug aberto no Next 16.2+.
Corrigir antes de a 1ª story de frontend rodar `shadcn init`.

## Conferência linha a linha

| Linha da Stack | Spine | Realidade (lock / registry) | Status |
| --- | --- | --- | --- |
| Python | 3.12 | `requires-python >=3.12`, `python:3.12-slim`, CI via uv | OK |
| FastAPI | 0.136.3 | uv.lock 0.136.3 (Starlette 1.2.1); PyPI latest 0.143.3 | OK (lock) |
| asyncpg | 0.31.0 | uv.lock 0.31.0; latest 0.32.0 | OK (lock) |
| Alembic | 1.18.4 | uv.lock 1.18.4; latest 1.20.0 | OK (lock) |
| APScheduler | 3.11.2 | uv.lock 3.11.2; 4.x ainda só alpha (4.0.0a6) | OK, escolha certa |
| redis-py | 8.0.0 | uv.lock 8.0.0; latest 8.1.0 | OK (lock) |
| Pydantic | 2.13.4 | uv.lock 2.13.4; latest 2.14.1 | OK (lock) |
| SciPy | 1.17.1 | uv.lock 1.17.1; latest 1.18.1 | OK (lock) |
| structlog | 25.5.0 | uv.lock 25.5.0; latest 26.1.0 | OK (lock) |
| uv | 0.11.12 | Dockerfile `uv:0.11.12`, CI `version: "0.11.12"`; latest 0.13.1 | OK |
| PostgreSQL | 15 | compose `postgres:15-alpine` | OK |
| Redis | 7 | compose `redis:7-alpine` | OK |
| Next.js | 16.2.7 | lock 16.2.7; **advisories críticos**; latest 16.4.2 | **F1** |
| React | 19.2.4 | lock 19.2.4; linha 19.2 vai até 19.2.9 | **F1** |
| TypeScript | 5.9.3 | lock 5.9.3; npm `latest` = 7.0.2 (nativo) | OK, ver nota N3 |
| @tanstack/react-query | 5.100.14 | lock 5.100.14, peer react 19 ok; latest 5.104.4 | OK |
| @tanstack/react-table | 8.21.3 | não instalado; v8 é incompatível com o React Compiler | **F3** |
| Tailwind CSS | 4.3.0 | lock 4.3.0 (`tailwindcss` e `@tailwindcss/postcss`) | OK |
| shadcn (CLI) | 4.22.0 | publicado 2026-10-16; padrão = Base UI | **F2**, **F6** |
| radix-ui | 1.8.1 | não instalado; publicado 2026-10-12, peer react ^19 | depende de F2; F6 |
| lucide-react | 1.59.0 | não instalado; publicado **hoje** (2026-10-17) | F6 |
| Recharts | 3.8.1 | lock 3.8.1, peer react ^19, já em uso com o Compiler | OK, ver F5 |
| next-themes | 0.4.6 | lock 0.4.6 (mar/2025, sem release desde então) | **F4** |
| pnpm | "lockfile do repo" | o lock não fixa o pnpm; CI usa `version: 11`; sem `packageManager` | F6 |

Os números do backend estão certos porque vieram do lock. Ficar atrás do latest é
aceitável num brownfield. O `.memlog.md` registra a consulta ao npm, mas não a compatibilidade nem
a segurança. É aí que estão os problemas.

## Achados

### F1 — HIGH — Next.js 16.2.7 tem 3 advisories críticos (RCE) sem backport na linha 16.2

`gh api /advisories?affects=next@16.2.7` retorna 17 advisories. Os mais graves:

| GHSA | Severidade | Resumo | Corrigido em |
| --- | --- | --- | --- |
| GHSA-vcvr-r3jv-pc5j | critical | RCE em `next/og` ImageResponse | 16.3.6 |
| GHSA-2xp9-vwfh-vxw4 | critical | RCE não autenticado no Image Optimization (AVIF) | 16.3.3 |
| GHSA-p293-qw3h-jr36 (CVE-2026-75604) | critical | RCE não autenticado em servidor Windows | 16.3.3 |
| GHSA-cjq9-62q9-8jv4 (CVE-2026-94483) | high | SSRF no Image Optimization | 16.3.8 |
| CVE-2026-64641…64649 (lote de julho) | high/medium | proxy bypass, DoS em Server Actions etc. | 16.2.11 |

A linha 16.2 parou em 16.2.12 (2026-07-25). As correções de setembro e outubro só existem em
16.3.x/16.4.x. Hoje não há nenhum 16.2.x sem advisory crítico. Nas mesmas datas, o React publicou
19.2.5–19.2.8 com correções de DoS em RSC (GHSA-wx67-qw84-cm4g, GHSA-rv78-f8rc-xrxh,
GHSA-479c-33wc-g2pg, em `react-server-dom-*`). O `react-dom@19.2.4` em si não tem advisory.

O AD-18 (v2.0 só local) reduz a exposição, mas não justifica travar a arquitetura numa versão com
RCE conhecido: o `pnpm dev` escuta na rede local e a v2.1 vai para a nuvem.

**Correção:** na Stack, `Next.js 16.3.8` (publicado 2026-09-30, sem advisories) ou 16.4.x
depois de um período de uso (16.4.0 saiu em 2026-10-06; 16.4.2, em 2026-10-15). Também
`eslint-config-next` na mesma versão e `react`/`react-dom` 19.2.9 (mesma minor, não 19.3). Fazer o
bump numa story própria, antes do marco 1, rodando `pnpm build` e `pnpm lint`.

### F2 — HIGH — shadcn CLI 4.x usa Base UI por padrão; spine e DESIGN pressupõem Radix + new-york

- Changelog do shadcn, julho/2026: "Base UI as the Default". O `npx shadcn init` usa Base UI, e
  Radix exige `-b radix`. Radix "is not being deprecated".
- Conferido no tarball `shadcn@4.22.0`: `-d, --defaults` = `--template=next --preset=base-nova`.
  `-b, --base <base>` aceita `base | radix | aria`.
- Registry atual: `styles/new-york-v4/select.json` importa `{ Select as SelectPrimitive } from
  "radix-ui"` (o pacote unificado, desde fev/2026; não mais `@radix-ui/react-*`).
  `styles/base-nova/select.json` importa de `@base-ui/react/select`.
- O `web/` não tem `components.json`. Na prática, o `init` é greenfield e cai no padrão atual.
- DESIGN.md (l.7, l.450) e EXPERIENCE.md (l.16, l.121, l.188) dizem "shadcn/ui (estilo new-york) +
  Radix". O AD-17 só diz "gerados pelo CLI". Um agente que rodar `shadcn init -d` (o atalho
  documentado para CI e agentes) gera componentes Base UI, e a linha `radix-ui 1.8.1` fica órfã.

O resto da compatibilidade foi conferido: o CLI 4.x tem template `next` e gera para Tailwind v4
(registry `new-york-v4`); `radix-ui@1.8.1` aceita React `^19`; o engine do CLI é Node `>=20.18.1`
(CI e local estão em Node 24).

**Correção:** no AD-17, escrever o comando: `pnpm dlx shadcn@<versão> init -b radix` com o estilo
new-york (ou o preset radix equivalente), e `components.json` versionado na 1ª story de frontend.
Proibir `init -d`. Alternativa: adotar Base UI e trocar a linha `radix-ui` por `@base-ui/react`,
mas isso contradiz DESIGN/EXPERIENCE e exigiria revisá-los.

### F3 — MEDIUM — TanStack Table 8.21.3 com `reactCompiler: true`

- O guia oficial da TanStack ("React Compiler") diz: "TanStack Table V9 is the first version of
  TanStack Table that is compatible with the React Compiler." No v8, `useReactTable` devolve o
  mesmo objeto e muta o estado interno. O guia manda pôr `'use no memo'` nos componentes que o
  chamam.
- O react.dev lista `useReactTable` como exemplo na regra `incompatible-library`. O
  `eslint-plugin-react-hooks@7.1.1` instalado tem `useReactTable` na lista `knownIncompatible`. Na
  config resolvida do projeto, `react-hooks/incompatible-library` está em **warn (1)**. O Compiler
  pula o componente, então não quebra, mas o componente não é otimizado e cada tabela gera um
  aviso no `pnpm lint`.
- A doc atual do shadcn (`docs/components/radix/data-table`) diz "This guide uses **TanStack Table
  v9**" (`useTable`, `tableFeatures()`). Ficar no v8 significa não seguir a receita do shadcn.
- A justificativa do `.memlog.md` é válida: o skill `tanstack-table` documenta v8 ("Current
  Version: v8") e o 9.3.1 tem 5 dias. Mas o trade-off com o Compiler não foi registrado.

**Correção (escolher uma):**
(a) manter `8.21.3` e acrescentar ao AD-17: todo componente que chama `useReactTable` começa com
`'use no memo'`, o aviso de `incompatible-library` é esperado nesses arquivos, e a receita de
data-table do shadcn não vale (está em v9); ou
(b) adotar v9 numa versão com pelo menos 2 semanas (ex.: `9.2.4`, de 2026-08-28; a linha 9.x saiu em
2026-08-04) e atualizar o skill `tanstack-table` para v9.
Como as tabelas da v2.0 são pequenas (Deferred: ~1,5 mil transações), (a) é aceitável, desde que
fique escrito.

### F4 — MEDIUM — next-themes 0.4.6: bug aberto no Next 16.2+, e "seguindo o sistema" contradiz o código atual

- O issue pacocoursey/next-themes#387 (e o #385) relata "Encountered a script tag while rendering
  React component" no Next 16.2.x com 0.4.6. Está aberto, sem resposta do mantenedor, e não há
  release desde 2025-03-11. O efeito descrito é um aviso em dev, sem quebra em produção.
  Contornos citados: `scriptProps={{ type: "application/json" }}`, o fork
  `@teispace/next-themes`, ou script de init via `next/script`. A combinação com a versão
  corrigida do Next (F1) não foi testada.
- O spine diz "claro/escuro via `next-themes` seguindo o sistema" (AD-17), e o DESIGN.md
  (l.450) pede o Switch sistema/claro/escuro. Hoje, `web/app/providers.tsx` usa `defaultTheme="dark"
  enableSystem={false}` (dark-only, ADR-009) e `globals.css` fixa `color-scheme: dark` no
  `:root`. Isso é migração, não ratificação.
- O `sonner` do registry shadcn importa `useTheme` de `next-themes`, então manter a lib é
  coerente com o shadcn.

**Correção:** no AD-17, registrar `ThemeProvider attribute="class" defaultTheme="system"
enableSystem` e `color-scheme` por modo (`:root` claro, `.dark` escuro), e citar o aviso do #387
como conhecido e aceito, com o contorno escolhido. Rever depois do bump do Next.

### F5 — LOW — `shadcn add chart` traz `recharts@3.8.0`

O registry (`new-york-v4/chart.json`, e também `base-nova` e `radix-nova`) declara
`"dependencies": ["cn", "recharts@3.8.0", "lucide-react"]`. Adicionar o `chart` pode reescrever
`"recharts": "^3.8.1"` para `3.8.0`.

Recharts 3.8.1 com React 19 foi conferido: peer `^19.0.0`; o lock tem `immer@11.1.8` (o bug de
"lanes" do React 19 era no immer 11.0.0, corrigido em 11.0.1); e já roda com o Compiler em
`app/(app)/portfolio/allocation/page.tsx`. Não achei relato específico de Recharts 3 × React
Compiler. Há ainda um aviso de terceiros (docs do Chakra): `ResponsiveContainer` pode causar
problemas no React 19, e a recomendação é o prop `responsive` (Recharts ≥3.3).

**Correção:** depois de `shadcn add chart`, conferir o diff do `package.json` e manter `^3.8.1`.
Nos gráficos novos, preferir o prop `responsive` a `ResponsiveContainer`.

### F6 — LOW — Pins de releases desta semana, peças novas do shadcn e linha "pnpm" sem versão

- Versões exatas publicadas há poucos dias: `shadcn 4.22.0` (2026-10-16), `radix-ui 1.8.1`
  (2026-10-12) e `lucide-react 1.59.0` (2026-10-17, hoje; o lucide solta uma minor quase por dia).
  São "o latest de hoje", não uma escolha. Na hora de instalar já serão outras.
- O shadcn agora instala peças que a Stack não lista: o pacote `cn` (shadcn-ui/cn, changelog de
  set/2026), que substitui `clsx` + `tailwind-merge` e é dependência do CLI e de todo item do
  registry. Também `tw-animate-css`.
- `pnpm | lockfile do repo` não é uma versão: o `pnpm-lock.yaml` (lockfileVersion 9.0) não fixa
  o pnpm, o CI usa `pnpm/action-setup` com `version: 11`, o `pnpm-workspace.yaml` usa
  `allowBuilds` (pnpm 11), não há `packageManager` no `package.json`, e o latest é 12.14.0. O Node
  (24 no CI e local) não aparece na tabela, embora o shadcn exija `>=20.18.1` e o TanStack v9,
  `>=20`.

**Correção:** escrever as libs ainda não instaladas como piso de major (`radix-ui ^1`,
`lucide-react ^1`, `shadcn@4` via `pnpm dlx`), deixar o lock fixar na instalação e registrar a
versão resolvida no commit. Acrescentar as linhas `pnpm 11` e `Node 24`, mais
`"packageManager": "pnpm@11.x"` no `web/package.json`. Mencionar `cn` + `tw-animate-css` como parte
do shadcn.

## Notas (sem ação obrigatória)

- **N1 — ADR-006 (auth):** `passlib 1.7.4` não tem release desde 2020-10 (o projeto já trava
  `bcrypt<5` por isso), e `python-jose 3.5.0` é de 2025-05. A doc atual do FastAPI
  (`tutorial/security/oauth2-jwt`) usa `PyJWT` + `pwdlib`. Fica fora da Stack do spine e é decisão
  de ADR. Fica registrado para a v2.1 (nuvem).
- **N2 — Backend atrás do latest:** FastAPI 0.143.3, asyncpg 0.32.0, Alembic 1.20.0, structlog
  26.1.0 e uv 0.13.1 existem. Não é bloqueio: o spine fixa o que o lock tem, o que é coerente com o
  brownfield. Se for desejado, um bump fica em story separada.
- **N3 — TypeScript:** `npm latest` agora é 7.0.2 (compilador nativo). O 5.9.3 bate com o lock e
  é escolha segura. Vale dizer no AD-17 que agentes não devem aceitar o major 7 só porque o
  `typescript@^5` virar alvo de upgrade automático.
- **N4 — PostgreSQL 15:** bate com o compose e com o CLAUDE.md. O suporte do PG 15 termina em
  nov/2027. Projetos Supabase novos já nascem em versões mais novas, o que importa para a v2.1.

## Fontes

- GitHub Advisory DB: `gh api "/advisories?ecosystem=npm&affects=next@16.2.7"` e `react-server-dom-webpack@19.2.4`
- shadcn changelog — https://ui.shadcn.com/docs/changelog (Base UI as the Default, jul/2026; Unified Radix UI Package, fev/2026; cn, set/2026)
- shadcn data table (v9) — https://ui.shadcn.com/docs/components/radix/data-table
- Registry shadcn — https://ui.shadcn.com/r/styles/new-york-v4/select.json, …/base-nova/select.json, …/new-york-v4/chart.json, …/new-york-v4/sonner.json
- TanStack Table × React Compiler — https://tanstack.com/table/latest/docs/framework/react/guide/react-compiler
- react.dev incompatible-library — https://react.dev/reference/eslint-plugin-react-hooks/lints/incompatible-library
- next-themes #387 — https://github.com/pacocoursey/next-themes/issues/387 (e #385)
- FastAPI OAuth2/JWT — https://github.com/fastapi/fastapi/blob/master/docs/en/docs/tutorial/security/oauth2-jwt.md
- Chakra charts (Recharts 3 × React 19) — https://chakra-ui.com/docs/charts/installation
