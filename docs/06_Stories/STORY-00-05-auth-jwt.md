---
tipo: story
epico: EPIC-00
story: STORY-00-05
titulo: Implementar auth JWT (login, refresh, middleware)
status: pendente
estimativa: M (3-4h)
tags: [goodies, story, foundation, auth, jwt]
---

# STORY-00-05 — Auth JWT

**Como** usuário (Vitor)  
**Quero** fazer login com email/senha e ter requisições autenticadas com JWT  
**Para** que meus dados financeiros não sejam acessíveis sem autenticação

---

## Critérios de aceite

- [ ] `POST /api/v1/auth/login` com `{ email, password }` retorna `{ access_token, refresh_token, expires_in }`
- [ ] `POST /api/v1/auth/refresh` com `{ refresh_token }` retorna novo `access_token`
- [ ] Dependency injection `get_current_user` para proteger rotas
- [ ] Middleware valida Bearer token em todas as rotas protegidas — 401 se inválido ou expirado
- [ ] Token de usuário: 15min de expiração, scope `user`
- [ ] Token de serviço Hermes: 90 dias de expiração, scope `hermes`, gerado via script
- [ ] Senha armazenada com bcrypt (nunca em texto plano)
- [ ] Testes: login correto, login errado, token expirado, token inválido

## Notas de implementação
- `python-jose[cryptography]` para JWT
- `passlib[bcrypt]` para hashing
- `refresh_token`: armazenado em `users.refresh_token_hash` (hash do token, não o token em si) com expiração
- Hermes service token: gerado uma única vez via `python -c "import secrets; print(secrets.token_hex(32))"` e configurado em Fly.io secrets

## Dependências
STORY-00-03 concluída (tabela users existe).
