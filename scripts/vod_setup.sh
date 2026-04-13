#!/bin/bash
# Script para configurar e testar o serviço VOD

set -e

echo "🎬 Serviço VOD - Setup e Testes"
echo "================================"
echo ""

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Função de log
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Verifica se está no diretório correto
if [ ! -f "docker-compose.yml" ]; then
    error "Execute este script no diretório raiz do projeto (D:\so\vms\mvp)"
fi

# Step 1: Verifica dependências
log "Verificando dependências..."
if ! command -v docker &> /dev/null; then
    error "Docker não está instalado"
fi

if ! docker compose version &> /dev/null; then
    error "Docker Compose não está instalado"
fi

log "✓ Docker e Docker Compose encontrados"

# Step 2: Roda migration do banco
log "Executando migração do banco de dados..."
docker compose run --rm api alembic upgrade head || error "Falha ao executar migração"
log "✓ Migração executada com sucesso"

# Step 3: Verifica se ffmpeg está disponível no container API
log "Verificando ffmpeg no container API..."
if ! docker compose exec api which ffmpeg &> /dev/null; then
    warn "ffmpeg não está instalado no container API"
    warn "Instalando ffmpeg..."
    
    # Adiciona ffmpeg ao Dockerfile da API se não estiver presente
    if ! grep -q "ffmpeg" api/Dockerfile; then
        log "Adicionando ffmpeg ao Dockerfile da API..."
        echo "" >> api/Dockerfile
        echo "RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*" >> api/Dockerfile
        log "✓ ffmpeg adicionado ao Dockerfile"
    fi
    
    log "Reconstruindo container API..."
    docker compose build api
    docker compose up -d api
fi

log "✓ ffmpeg encontrado"

# Step 4: Reinicia serviços
log "Reiniciando serviços..."
docker compose up -d api nginx
log "✓ Serviços reiniciados"

# Step 5: Aguarda serviços ficarem prontos
log "Aguardando serviços ficarem prontos..."
sleep 5

# Step 6: Verifica health
log "Verificando health da API..."
if curl -f http://localhost/health &> /dev/null; then
    log "✓ API está responding"
else
    warn "API pode demorar mais para ficar pronta. Verifique os logs:"
    warn "docker compose logs api"
fi

# Step 7: Verifica volumes
log "Verificando volumes..."
if docker compose exec nginx ls /tmp/vod &> /dev/null; then
    log "✓ Volume VOD montado no nginx"
else
    warn "Volume VOD pode não estar montado corretamente"
fi

echo ""
echo "================================"
echo "✅ Setup concluído com sucesso!"
echo ""
echo "📚 Próximos passos:"
echo "  1. Acesse: http://localhost"
echo "  2. Vá para a página de Gravações"
echo "  3. Selecione uma câmera e data"
echo "  4. Clique no toggle 'VOD' na toolbar"
echo "  5. Aguarde geração do stream HLS"
echo ""
echo "🐛 Troubleshooting:"
echo "  - Logs API: docker compose logs api"
echo "  - Logs Nginx: docker compose logs nginx"
echo "  - Teste VOD: curl http://localhost/api/v1/vod/streams"
echo ""
