#!/bin/bash
# Script de renovação do certificado Let's Encrypt
# Para: vms-server.duckdns.org
set -e

LOGFILE=/var/log/certbot-renew.log
NGINX_CERT_DIR=/opt/vms/infra/nginx/certs

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a $LOGFILE
}

log "=== Iniciando renovação do certificado ==="

# 1. Para o nginx temporariamente
log "Parando container nginx..."
cd /opt/vms && docker compose stop nginx
sleep 3

# 2. Renova o certificado (usa configuração standalone do arquivo de renovação)
log "Renovando certificado Let's Encrypt..."
if certbot renew --noninteractive 2>&1 | tee -a $LOGFILE; then
    log "Certificado renovado com sucesso!"
    
    # 3. Copia certificados para o diretório do nginx
    log "Copiando certificados para $NGINX_CERT_DIR..."
    cp /etc/letsencrypt/live/vms-server.duckdns.org/fullchain.pem $NGINX_CERT_DIR/
    cp /etc/letsencrypt/live/vms-server.duckdns.org/privkey.pem $NGINX_CERT_DIR/
    chmod 644 $NGINX_CERT_DIR/fullchain.pem
    chmod 600 $NGINX_CERT_DIR/privkey.pem
    
    # 4. Reinicia o nginx com o novo certificado
    log "Reiniciando nginx..."
    cd /opt/vms && docker compose start nginx
    sleep 5
    
    # 5. Verifica se está funcionando
    if curl -sk https://localhost/health | grep -q healthy; then
        log "HTTPS verificado com sucesso!"
    else
        log "ERRO: HTTPS não está respondendo corretamente"
    fi
else
    log "ERRO: Falha na renovação do certificado"
    # Reinicia o nginx mesmo em caso de erro
    cd /opt/vms && docker compose start nginx
    exit 1
fi

log "=== Renovação concluída ==="
