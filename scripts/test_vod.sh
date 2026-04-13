#!/bin/bash
# Script de teste de integração do serviço VOD

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

log_pass() {
    echo -e "${GREEN}✓ PASS${NC} $1"
    PASS=$((PASS + 1))
}

log_fail() {
    echo -e "${RED}✗ FAIL${NC} $1"
    FAIL=$((FAIL + 1))
}

log_warn() {
    echo -e "${YELLOW}⚠ WARN${NC} $1"
    WARN=$((WARN + 1))
}

log_info() {
    echo -e "${BLUE}ℹ INFO${NC} $1"
}

echo "========================================="
echo "  Teste de Integração - Serviço VOD"
echo "========================================="
echo ""

# Teste 1: Verifica se API está no ar
log_info "Teste 1: Health check da API"
if curl -f -s http://localhost/health > /dev/null 2>&1; then
    log_pass "API está respondendo"
else
    log_fail "API não está respondendo"
    echo "   Execute: docker compose up -d api"
    exit 1
fi

# Teste 2: Verifica migração do banco
log_info "Teste 2: Tabela vod_streams no banco"
TABLE_EXISTS=$(docker compose exec -T postgres psql -U vms -d vms -t -c \
    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'vod_streams');" 2>/dev/null | tr -d ' ')

if [ "$TABLE_EXISTS" = "t" ]; then
    log_pass "Tabela vod_streams existe"
else
    log_fail "Tabela vod_streams não existe"
    echo "   Execute: docker compose run --rm api alembic upgrade head"
fi

# Teste 3: Verifica ffmpeg no container API
log_info "Teste 3: ffmpeg instalado no container API"
if docker compose exec -T api which ffmpeg > /dev/null 2>&1; then
    log_pass "ffmpeg está instalado"
    FFMPEG_VERSION=$(docker compose exec -T api ffmpeg -version 2>&1 | head -n 1)
    echo "   $FFMPEG_VERSION"
else
    log_fail "ffmpeg não está instalado"
    echo "   Adicione ffmpeg ao Dockerfile da API"
fi

# Teste 4: Verifica volume VOD
log_info "Teste 4: Volume VOD montado"
if docker compose exec -T api ls -d /tmp/vod > /dev/null 2>&1; then
    log_pass "Volume /tmp/vod existe no container API"
else
    log_warn "Volume /tmp/vod não existe no container API (será criado no primeiro uso)"
fi

# Teste 5: Verifica config nginx para VOD
log_info "Teste 5: Configuração nginx para VOD"
if docker compose exec -T nginx grep -q "vod-streams" /etc/nginx/nginx.conf 2>/dev/null; then
    log_pass "Nginx configurado para VOD"
else
    log_fail "Nginx não está configurado para VOD"
    echo "   Adicione location /vod-streams/ ao nginx.conf"
fi

# Teste 6: Testa endpoint da API (sem auth)
log_info "Teste 6: Endpoint VOD responde"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/v1/vod/streams 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "403" ]; then
    log_pass "Endpoint VOD está respondendo (auth required: $HTTP_CODE)"
elif [ "$HTTP_CODE" = "200" ]; then
    log_pass "Endpoint VOD está respondendo (OK: $HTTP_CODE)"
elif [ "$HTTP_CODE" = "404" ]; then
    log_fail "Endpoint VOD não encontrado (404)"
    echo "   Verifique se o router VOD foi registrado no main.py"
else
    log_warn "Endpoint VOD retornou $HTTP_CODE"
fi

# Teste 7: Verifica módulos Python
log_info "Teste 7: Módulos Python importáveis"
if docker compose exec -T api python -c "from vms.vod.service import VODService" 2>/dev/null; then
    log_pass "Módulo VODService importável"
else
    log_fail "Erro ao importar VODService"
    echo "   Verifique se há erros de sintaxe ou imports faltando"
fi

# Teste 8: Verifica arquivos criados
log_info "Teste 8: Arquivos do serviço VOD"
FILES_OK=true

for file in \
    "api/src/vms/vod/__init__.py" \
    "api/src/vms/vod/domain.py" \
    "api/src/vms/vod/models.py" \
    "api/src/vms/vod/repository.py" \
    "api/src/vms/vod/router.py" \
    "api/src/vms/vod/schemas.py" \
    "api/src/vms/vod/service.py" \
    "api/migrations/versions/010_vod_streams_table.py" \
    "frontend/src/services/vod.ts" \
    "frontend/src/components/camera/RecordingPlayer.tsx" \
    "docs/VOD_SERVICE.md"
do
    if [ -f "$file" ]; then
        echo -e "   ${GREEN}✓${NC} $file"
    else
        echo -e "   ${RED}✗${NC} $file (faltando)"
        FILES_OK=false
    fi
done

if [ "$FILES_OK" = true ]; then
    log_pass "Todos os arquivos existem"
else
    log_fail "Alguns arquivos estão faltando"
fi

# Teste 9: Verifica types TypeScript
log_info "Teste 9: Types TypeScript do VOD"
if grep -q "VODStream" frontend/src/types/index.ts 2>/dev/null; then
    log_pass "Types VODStream definidos"
else
    log_warn "Types VODStream não encontrados em types/index.ts"
fi

# Teste 10: Verifica integração no frontend
log_info "Teste 10: Integração no RecordingsPage"
if grep -q "RecordingPlayer" frontend/src/pages/RecordingsPage.tsx 2>/dev/null; then
    log_pass "RecordingsPage importando RecordingPlayer"
else
    log_warn "RecordingsPage não está importando RecordingPlayer"
fi

if grep -q "useVOD" frontend/src/pages/RecordingsPage.tsx 2>/dev/null; then
    log_pass "Toggle VOD implementado"
else
    log_warn "Toggle VOD não encontrado"
fi

# Resumo
echo ""
echo "========================================="
echo "  Resumo dos Testes"
echo "========================================="
echo -e "  ${GREEN}Pass: $PASS${NC}"
echo -e "  ${RED}Fail: $FAIL${NC}"
echo -e "  ${YELLOW}Warn: $WARN${NC}"
echo "========================================="

if [ $FAIL -eq 0 ]; then
    echo -e "\n${GREEN}✅ Todos os testes críticos passaram!${NC}"
    echo ""
    echo "🎬 O serviço VOD está pronto para uso."
    echo ""
    echo "📚 Próximos passos:"
    echo "   1. Acesse: http://localhost"
    echo "   2. Vá para Gravações"
    echo "   3. Selecione câmera e data"
    echo "   4. Ative o toggle VOD"
    echo "   5. Clique em um segmento para playback"
    echo ""
    exit 0
else
    echo -e "\n${RED}❌ Alguns testes falharam.${NC}"
    echo ""
    echo "Revise os erros acima e corrija antes de usar."
    echo ""
    exit 1
fi
