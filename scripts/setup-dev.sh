#!/usr/bin/env bash
# Goodies — bootstrap de ambiente de desenvolvimento.
# Rode UMA vez após clonar o repo:  bash scripts/setup-dev.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Configurando git hooks (.githooks/)"
git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || true

echo "==> Verificando gitleaks"
if command -v gitleaks >/dev/null 2>&1; then
  echo "    gitleaks OK: $(gitleaks version)"
else
  echo "    gitleaks NÃO instalado. Instale o binário em ~/.local/bin:"
  echo "      VER=\$(curl -fsSLI -o /dev/null -w '%{url_effective}' https://github.com/gitleaks/gitleaks/releases/latest | sed -E 's#.*/tag/v?([0-9.]+).*#\\1#')"
  echo "      curl -fsSL \"https://github.com/gitleaks/gitleaks/releases/download/v\${VER}/gitleaks_\${VER}_linux_x64.tar.gz\" | tar -xz -C /tmp gitleaks"
  echo "      install -m755 /tmp/gitleaks ~/.local/bin/gitleaks"
fi

echo "==> Verificando .env"
if [ ! -f .env ]; then
  echo "    .env ausente — criando a partir do template:"
  cp .env.example .env
  echo "    ⚠ Preencha .env com os valores reais (fica no .gitignore)."
else
  echo "    .env já existe."
fi

echo "==> Pronto. As chaves de .env e .env.example devem permanecer SINCRONIZADAS."
