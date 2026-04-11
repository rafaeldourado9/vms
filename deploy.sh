#!/bin/bash
# deploy.sh — Envia o projeto para a EC2 e reinicia os containers
# Uso: ./deploy.sh [--build] [--env-only] [--logs]
set -euo pipefail

TERRAFORM_DIR="infra/terraform"
SSH_KEY="$TERRAFORM_DIR/vms-dev.pem"
REMOTE_USER="ubuntu"
REMOTE_DIR="/opt/vms"

# ─── Cores ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERR]${NC} $*"; exit 1; }

# ─── Pré-checks ──────────────────────────────────────────────────────────────
[ -f "$SSH_KEY" ] || error "Chave SSH não encontrada: $SSH_KEY\nRode: cd $TERRAFORM_DIR && terraform apply"
command -v rsync >/dev/null || error "rsync não encontrado"

# Lê o IP do output do Terraform
REMOTE_IP=$(cd "$TERRAFORM_DIR" && terraform output -raw public_ip 2>/dev/null) \
  || error "IP não encontrado. Rode: cd $TERRAFORM_DIR && terraform apply"

info "Destino: $REMOTE_USER@$REMOTE_IP:$REMOTE_DIR"

SSH_CMD="ssh -i $SSH_KEY -o StrictHostKeyChecking=no -o ConnectTimeout=10"

# ─── Aguarda SSH ficar disponível ────────────────────────────────────────────
info "Verificando conexão SSH..."
RETRIES=0
until $SSH_CMD "$REMOTE_USER@$REMOTE_IP" "echo ok" &>/dev/null; do
  RETRIES=$((RETRIES+1))
  [ $RETRIES -ge 20 ] && error "Servidor não respondeu após 100s. Verifique o Security Group."
  echo -n "."
  sleep 5
done
echo ""
success "SSH conectado"

# ─── Modo --env-only ──────────────────────────────────────────────────────────
if [[ "${1:-}" == "--env-only" ]]; then
  info "Enviando apenas .env..."
  scp -i "$SSH_KEY" -o StrictHostKeyChecking=no .env "$REMOTE_USER@$REMOTE_IP:$REMOTE_DIR/.env"
  $SSH_CMD "$REMOTE_USER@$REMOTE_IP" "cd $REMOTE_DIR && docker compose up -d"
  success "Feito"
  exit 0
fi

# ─── Modo --logs ──────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--logs" ]]; then
  exec $SSH_CMD -t "$REMOTE_USER@$REMOTE_IP" "cd $REMOTE_DIR && docker compose logs -f"
fi

# ─── Sync do código ───────────────────────────────────────────────────────────
info "Sincronizando código..."
rsync -az --progress \
  --exclude='.git/' \
  --exclude='node_modules/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache/' \
  --exclude='*.egg-info/' \
  --exclude='.ruff_cache/' \
  --exclude='legado/' \
  --exclude='*.png' \
  --exclude='*.jpg' \
  --exclude='infra/terraform/vms-dev.pem' \
  --exclude='infra/terraform/.terraform/' \
  --exclude='infra/terraform/*.tfstate*' \
  -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
  . \
  "$REMOTE_USER@$REMOTE_IP:$REMOTE_DIR/"

success "Código sincronizado"

# ─── .env no servidor ─────────────────────────────────────────────────────────
ENV_EXISTS=$($SSH_CMD "$REMOTE_USER@$REMOTE_IP" "[ -f $REMOTE_DIR/.env ] && echo yes || echo no")

if [[ "$ENV_EXISTS" == "no" ]]; then
  warn ".env não encontrado no servidor — gerando a partir do .env.example..."
  # Gera SECRET_KEY aleatória
  SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | base64 | tr -dc 'a-f0-9' | head -c 64)
  VMS_API_KEY=$(openssl rand -hex 16 2>/dev/null || head -c 16 /dev/urandom | base64 | tr -dc 'a-f0-9' | head -c 32)

  scp -i "$SSH_KEY" -o StrictHostKeyChecking=no \
    .env.example "$REMOTE_USER@$REMOTE_IP:$REMOTE_DIR/.env.tmp"

  $SSH_CMD "$REMOTE_USER@$REMOTE_IP" "
    cd $REMOTE_DIR
    cp .env.tmp .env
    # Substitui valores padrão por valores gerados
    sed -i 's|^SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|' .env
    sed -i 's|^VMS_API_KEY=.*|VMS_API_KEY=$VMS_API_KEY|' .env
    sed -i 's|^DOMAIN=.*|DOMAIN=$REMOTE_IP|' .env
    sed -i 's|^ENVIRONMENT=.*|ENVIRONMENT=development|' .env
    sed -i 's|^RTMP_PUBLIC_URL=.*|RTMP_PUBLIC_URL=rtmp://$REMOTE_IP:1935|' .env
    rm .env.tmp
  "
  success ".env gerado com SECRET_KEY e VMS_API_KEY aleatórios"
else
  info ".env já existe no servidor (preservado)"
fi

# ─── Build e start ────────────────────────────────────────────────────────────
BUILD_FLAG=""
[[ "${1:-}" == "--build" ]] && BUILD_FLAG="--build"

info "Iniciando containers..."
$SSH_CMD "$REMOTE_USER@$REMOTE_IP" "
  set -e
  cd $REMOTE_DIR

  # Migrações do banco
  echo '--- Rodando migrações ---'
  docker compose up -d postgres redis rabbitmq
  sleep 8
  docker compose run --rm api alembic upgrade head 2>/dev/null || true

  # Sobe tudo
  echo '--- Subindo stack completa ---'
  docker compose up -d $BUILD_FLAG --remove-orphans

  # Aguarda API ficar healthy
  echo -n 'Aguardando API...'
  for i in \$(seq 1 30); do
    if curl -sf http://localhost/health >/dev/null 2>&1; then
      echo ' OK'
      break
    fi
    echo -n '.'
    sleep 3
  done

  echo ''
  docker compose ps
"

# ─── Resultado ────────────────────────────────────────────────────────────────
echo ""
success "Deploy concluído!"
echo ""
echo -e "  ${GREEN}Frontend:${NC}   http://$REMOTE_IP"
echo -e "  ${GREEN}API Docs:${NC}   http://$REMOTE_IP/docs"
echo -e "  ${GREEN}RabbitMQ:${NC}   http://$REMOTE_IP:15672  (vms / vmsdev)"
echo -e "  ${GREEN}SSH:${NC}        ssh -i $SSH_KEY ubuntu@$REMOTE_IP"
echo ""
echo -e "  ${YELLOW}Hikvision:${NC}  http://$REMOTE_IP/hik_pro_connect?camera_id=<uuid>"
echo -e "  ${YELLOW}Intelbras:${NC}  http://$REMOTE_IP/intelbras_events?camera_id=<uuid>"
echo -e "  ${YELLOW}RTMP:${NC}       rtmp://$REMOTE_IP:1935/live/<stream_key>"
echo ""
echo "  Logs: ./deploy.sh --logs"
