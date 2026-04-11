#!/bin/bash
# seed.sh — Cria tenant inicial e usuário admin
# Uso: ./scripts/seed.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}═══ Seed Inicial — VMS MVP ═══${NC}"
echo ""

# Verifica se containers estão rodando
if ! docker compose ps api --quiet | xargs docker inspect -f '{{.State.Running}}' | grep -q true; then
    echo -e "${RED}ERRO: Container da API não está rodando.${NC}"
    echo "Execute: docker compose up -d --build"
    exit 1
fi

# Parâmetros (com defaults para dev)
TENANT_NAME="${1:-Ops Solutions}"
TENANT_SLUG="${2:-ops-solutions}"
ADMIN_EMAIL="${3:-admin@vms.com}"
ADMIN_PASSWORD="${4:-admin123}"

echo "Tenant:     $TENANT_NAME ($TENANT_SLUG)"
echo "Admin:      $ADMIN_EMAIL"
echo "Senha:      $ADMIN_PASSWORD"
echo ""

# Executa dentro do container
docker compose exec api python -m vms.scripts.create_tenant \
    --name "$TENANT_NAME" \
    --slug "$TENANT_SLUG" \
    --admin-email "$ADMIN_EMAIL" \
    --admin-password "$ADMIN_PASSWORD"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}═══ Seed concluído com sucesso! ═══${NC}"
    echo ""
    echo "Faça login com:"
    echo "  Email: $ADMIN_EMAIL"
    echo "  Senha: $ADMIN_PASSWORD"
else
    echo ""
    echo -e "${RED}═══ Seed falhou (exit code: $EXIT_CODE) ═══${NC}"
    echo "Possível causa: tenant já existe (slug duplicado)."
fi

exit $EXIT_CODE
