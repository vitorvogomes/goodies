---
tipo: story
epico: EPIC-00
story: STORY-00-07
titulo: Tela de login no frontend
status: pendente
estimativa: S (1-2h)
tags: [goodies, story, foundation, login, frontend]
skills: [next-best-practices, frontend-design, ui-ux-pro-max]  # login custom JWT — ADR-006
skills_evitar: [supabase]
---

# STORY-00-07 — Tela de Login

**Como** usuário  
**Quero** fazer login no Goodies via interface web  
**Para** acessar meus dados financeiros com segurança

---

## Critérios de aceite

- [ ] Rota `app/(auth)/login/page.tsx` com formulário de email/senha
- [ ] POST para `/api/v1/auth/login` ao submeter
- [ ] Em caso de sucesso: armazena token e redireciona para `/dashboard`
- [ ] Em caso de erro: exibe mensagem "Email ou senha inválidos"
- [ ] Loading state durante request
- [ ] Rota protegida: qualquer rota que não seja `/login` redireciona para `/login` se não autenticado
- [ ] Não usa localStorage para o access_token (armazenar em memória React)

## Notas de implementação
- Middleware do Next.js para proteção de rotas (verificar cookie de refresh_token)
- Formulário simples sem biblioteca de form management (react-hook-form é overkill para 2 campos)

## Dependências
STORY-00-05 (auth JWT no backend), STORY-00-06 (Next.js setup).
