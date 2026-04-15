#!/bin/sh
set -e

# Injeta variáveis de ambiente no template do nginx
# Variáveis substituídas: $DOMAIN
envsubst '${DOMAIN}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# Se os certificados não existirem, usar configuração HTTP-only para desenvolvimento
if [ ! -f /etc/nginx/certs/fullchain.pem ] || [ ! -f /etc/nginx/certs/privkey.pem ]; then
    echo "[nginx] Certificados TLS não encontrados em /etc/nginx/certs/ — usando HTTP-only (modo desenvolvimento)"
    cat > /etc/nginx/nginx.conf << 'EOF'
worker_processes auto;
pid /run/nginx.pid;

events { worker_connections 1024; }

http {
    include      /etc/nginx/mime.types;
    default_type application/octet-stream;

    sendfile on;
    keepalive_timeout 65;
    server_tokens off;

    # Resolvedor DNS interno do Docker — permite re-resolução de nomes em runtime
    resolver 127.0.0.11 valid=10s ipv6=off;

    limit_req_zone $binary_remote_addr zone=api_general:10m rate=60r/m;
    limit_req_zone $binary_remote_addr zone=webhook:10m     rate=30r/m;
    limit_req_zone $binary_remote_addr zone=auth:10m        rate=5r/m;
    limit_req_zone $binary_remote_addr zone=public_webhook:10m rate=120r/m;

    log_format json escape=json
        '{"time":"$time_iso8601","remote_addr":"$remote_addr","method":"$request_method","uri":"$request_uri","status":$status,"request_time":$request_time}';
    access_log /var/log/nginx/access.log json;
    error_log  /var/log/nginx/error.log warn;

    # Upstreams
    upstream vms_api {
        server api:8000;
        keepalive 32;
    }
    upstream vms_frontend {
        server frontend:80;
        keepalive 16;
    }
    upstream mediamtx_hls    { server mediamtx:8888; }
    upstream mediamtx_webrtc { server mediamtx:8889; }

    server {
        listen 80;
        server_name _;
        client_max_body_size 10m;

        add_header X-Content-Type-Options  "nosniff"       always;
        add_header X-Frame-Options         "DENY"          always;
        add_header Referrer-Policy         "strict-origin-when-cross-origin" always;

        location / {
            proxy_pass http://vms_frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
        }
        location /api/v1/auth/ {
            limit_req zone=auth burst=3 nodelay;
            proxy_pass http://vms_api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
        }
        location /api/ {
            limit_req zone=api_general burst=20 nodelay;
            proxy_pass http://vms_api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
        }
        location /webhooks/ {
            limit_req zone=webhook burst=10 nodelay;
            proxy_pass http://vms_api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
        }
        location /api/v1/sse {
            proxy_pass http://vms_api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_buffering off;
            proxy_cache off;
            chunked_transfer_encoding off;
            proxy_read_timeout 86400s;
        }
        location = /api/v1/health {
            proxy_pass http://vms_api;
            access_log off;
        }
        location /docs       { proxy_pass http://vms_api; }
        location /redoc      { proxy_pass http://vms_api; }
        location /openapi.json { proxy_pass http://vms_api; }
        location /hls/ {
            proxy_pass http://mediamtx_hls/;
            proxy_set_header Host $host;
            proxy_http_version 1.1;
            proxy_buffering off;
            proxy_cache off;
        }
        location /webrtc/ {
            proxy_pass http://mediamtx_webrtc/;
            proxy_set_header Host $host;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_buffering off;
            proxy_cache off;
        }
        location /recordings/ {
            alias /recordings/;
            autoindex off;
            add_header Accept-Ranges bytes always;
            add_header Access-Control-Allow-Origin "*" always;
            add_header Access-Control-Allow-Headers "Range" always;
            add_header Cache-Control "private, no-cache";
        }
        location /internal/ { deny all; return 403; }

        location = /hik_pro_connect {
            limit_req zone=public_webhook burst=20 nodelay;
            proxy_pass http://vms_api/webhooks/hik_pro_connect;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_read_timeout 10s;
        }

        location = /intelbras_events {
            limit_req zone=public_webhook burst=20 nodelay;
            proxy_pass http://vms_api/webhooks/intelbras_events;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_read_timeout 10s;
        }

        location = /camera_events {
            limit_req zone=public_webhook burst=20 nodelay;
            proxy_pass http://vms_api/webhooks/camera_events;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_read_timeout 10s;
        }

        # Intelbras LPR — path hardcoded no firmware (não configurável)
        # camera_id passado via header X-Camera-Id para identificação
        location = /NotificationInfo/TollgateInfo {
            limit_req zone=public_webhook burst=20 nodelay;
            client_max_body_size 20m;
            proxy_pass http://vms_api/webhooks/intelbras_events$is_args$args;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Camera-Serial $http_x_camera_serial;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_read_timeout 10s;
        }
    }
}
EOF
fi

# Aguardar API estar disponível antes de iniciar o Nginx
echo "[nginx] Aguardando API ficar disponível..."
MAX_RETRIES=30
RETRY_INTERVAL=3
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if getent hosts api > /dev/null 2>&1; then
        HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://api:8000/api/v1/health 2>/dev/null || echo "000")
        if [ "$HTTP_STATUS" = "200" ]; then
            echo "[nginx] API está saudável (HTTP $HTTP_STATUS) — iniciando Nginx"
            break
        fi
        echo "[nginx] API respondeu HTTP $HTTP_STATUS — aguardando ($((RETRY_COUNT + 1))/$MAX_RETRIES)"
    else
        echo "[nginx] DNS da API ainda não resolvido — aguardando ($((RETRY_COUNT + 1))/$MAX_RETRIES)"
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep $RETRY_INTERVAL
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "[nginx] Timeout aguardando API ($((MAX_RETRIES * RETRY_INTERVAL))s) — iniciando Nginx mesmo assim"
fi

exec nginx -g 'daemon off;'
