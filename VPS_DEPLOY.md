# 🌐 Deploy em VPS - Como o CluebaseVMS Funciona na Nuvem

## 📋 Visão Geral

O CluebaseVMS foi projetado para operar em **dois modos principais**:

1. **Modo Local (On-Premise)** - Instalação Windows com Docker Desktop
2. **Modo VPS/Cloud** - Deploy em servidor remoto (VPS) com acesso remoto de câmeras

---

## 🏗️ Arquitetura de Deploy

### Modo Local (Instalação Atual)

```
┌────────────────────────────────────────────────────┐
│              Windows (Máquina Local)                │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │         Docker Desktop (WSL2)                  │  │
│  │                                                │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐         │  │
│  │  │Backend  │ │ Frontend│ │   AI    │         │  │
│  │  │:3000    │ │  Nginx  │ │ :9001   │         │  │
│  │  └────┬────┘ └────┬────┘ └────┬────┘         │  │
│  │       │           │           │               │  │
│  │  ┌────┴───────────┴───────────┴────┐          │  │
│  │  │        Nginx Proxy (:80)        │          │  │
│  │  └─────────────────────────────────┘          │  │
│  │                                               │  │
│  │  ┌──────────┐  ┌──────────┐ ┌──────────┐    │  │
│  │  │  MySQL   │  │  RTSP    │ │ WebRTC   │    │  │
│  │  │  :3307   │  │  :8565   │ │ :4002    │    │  │
│  │  └──────────┘  └──────────┘ └──────────┘    │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  Câmeras IP ──RTSP──▶ RTSP Server ──▶ WebRTC       │
│  (LAN)                  :8565         Navegador     │
└────────────────────────────────────────────────────┘
```

### Modo VPS/Cloud

```
┌─────────────────────────────────────────────────────────────┐
│                    VPS (Servidor Remoto)                     │
│                                                              │
│  IP Público: 203.0.113.50                                    │
│  Domínio: vms.cliente.com.br                                 │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Docker Compose                             │  │
│  │                                                         │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐             │  │
│  │  │ Backend  │  │ Frontend │  │   AI     │             │  │
│  │  │ :3000    │  │  Nginx   │  │  :9001   │             │  │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘             │  │
│  │       │              │             │                    │  │
│  │  ┌────┴──────────────┴─────────────┴────┐               │  │
│  │  │        Nginx Proxy (:80/:443)        │               │  │
│  │  │        (SSL com Let's Encrypt)       │               │  │
│  │  └──────────────────────────────────────┘               │  │
│  │                                                          │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │  │
│  │  │  MySQL   │  │  RTSP    │  │  WebRTC  │              │  │
│  │  │  :3306   │  │  :8565   │  │ :4002    │              │  │
│  │  └──────────┘  └──────────┘  └──────────┘              │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
          Internet (HTTPS/WSS)
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
   │Camera 1 │   │Camera 2 │   │Camera N │
   │ RTSP    │   │ RTSP    │   │ RTSP    │
   │(ONVIF)  │   │(ONVIF)  │   │(ONVIF)  │
   └─────────┘   └─────────┘   └─────────┘
   (Site A)      (Site B)      (Site C)

   ┌──────────────────────────────────────┐
   │         Operador (Remoto)             │
   │   https://vms.cliente.com.br          │
   │   (Navegador com WebRTC)              │
   └──────────────────────────────────────┘
```

---

## 🔧 Configuração para VPS

### 1. Variáveis de Ambiente (.env)

O arquivo `.env` é **o coração da configuração**. Para uma VPS, ele se torna:

```bash
# ===== CONFIGURAÇÃO DE REDE =====
# IP/DNS da VPS (público)
APP_HOST=vms.cliente.com.br
MACHINE_HOST=vms.cliente.com.br
LOCAL_HOST=0.0.0.0  # Bind em todas as interfaces

# Gateway da rede da VPS
SUBNET_ADDRESS=192.168.1.1

# ===== PORTAS EXTERNAS =====
# Porta pública do Nginx
NGINX_PORT=80
APP_PORT=80

# Porta interna do backend
LOCAL_PORT=3000

# MySQL exposto (cuidado!)
EXTERNAL_MYSQL_PORT=3307

# RTSP e WebRTC
RTSP_SERVER_PORT=8565
LIVESTREAM_SERVER_PORT=4001
WS_SERVER_PORT=4444

# ===== BANCO DE DADOS =====
MYSQL_USER=root
MYSQL_DB=vcloud
MYSQL_PASSWORD=<senha_forte>
SECRET_WORD=<secret_forte>

# ===== SSL/TLS =====
APP_PROTOCOL=https  # Mudar para HTTPS em produção

# ===== TIMEZONE =====
TZ=America/Sao_Paulo
NODE_ENV=production
OS_PLATFORM=linux

# ===== TUNNEL SERVER (ACESSO REMOTO) =====
TUNNEL_SERVER_HOST=link.vcloud.ai
TUNNEL_SERVER_PORT=10000
TUNNEL_SERVER_PROTOCOL=https

# ===== SERVIÇOS IA =====
AI_PORT=9001
ROADAR_PORT=8095

# ===== TOGGLES DE IA =====
DISABLE_ONLINE_LICENSE_OPT=0
DISABLE_YOLO_OPT=0
DISABLE_LLAVA_OPT=0
DISABLE_VCA_OPT=0
DISABLE_LUNA_OPT=1
DISABLE_BLD_OPT=1
DISABLE_SGR_OPT=1
DISABLE_INF_OPT=1
DISABLE_ROADAR_OPT=1
DISABLE_NTECH_OPT=0
```

### 2. Script `newIP.ps1` (Adaptar para VPS Linux)

Em uma VPS Linux, o equivalente ao `newIP.ps1` seria:

```bash
#!/bin/bash
# newIP.sh - Versão Linux

# Detectar IP público da VPS
LOCAL_IP=$(curl -s ifconfig.me || hostname -I | awk '{print $1}')
GATEWAY=$(ip route | grep default | awk '{print $3}')

# Atualizar .env
sed -i "s/APP_HOST=.*/APP_HOST=$LOCAL_IP/" .env
sed -i "s/MACHINE_HOST=.*/MACHINE_HOST=$LOCAL_IP/" .env
sed -i "s/LOCAL_HOST=.*/LOCAL_HOST=$LOCAL_IP/" .env
sed -i "s/SUBNET_ADDRESS=.*/SUBNET_ADDRESS=$GATEWAY/" .env

echo "IP atualizado: $LOCAL_IP"
```

### 3. Docker Compose para VPS

O `docker-compose-ai.yml` **já está pronto para VPS**. As únicas mudanças necessárias:

#### Network Mode
```yaml
# Em VPS, usar bridge em vez de host network
services:
  appback:
    # network_mode: host   # ← Descomentar para Linux bare-metal
    ports:
      - "3000:3000"        # ← Usar port mapping em Docker
    networks:
      - vms-network

  ai:
    ports:
      - "9001:9001"
    networks:
      - vms-network

networks:
  vms-network:
    driver: bridge
```

#### SSL/TLS (Nginx)
```nginx
# nginx.conf (produção)
server {
    listen 443 ssl;
    listen [::]:443 ssl;

    ssl_certificate /etc/letsencrypt/live/vms.cliente.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vms.cliente.com.br/privkey.pem;

    server_name vms.cliente.com.br;

    # ... resto da configuração
}

# Redirect HTTP → HTTPS
server {
    listen 80;
    server_name vms.cliente.com.br;
    return 301 https://$server_name$request_uri;
}
```

---

## 🚪 Acesso Remoto de Câmeras

### Como as Câmeras se Conectam à VPS

#### Cenário 1: Câmeras com IP Público na VPS

```
Câmera (RTSP) ──────Internet──────▶ VPS RTSP Server (:8565)
192.168.1.100                      203.0.113.50:8565
```

**Configuração na Câmera:**
- Stream para: `rtsp://203.0.113.50:8565/camera1`
- Ou a VPS faz pull via ONVIF/RTSP da câmera

#### Cenário 2: VPS Faz Pull das Câmeras

```
VPS Backend ──────Internet──────▶ Câmera (RTSP/ONVIF)
203.0.113.50                     192.168.1.100:554
       (pull RTSP)
```

**Configuração no CluebaseVMS:**
```javascript
// CameraInfo.url
{
  url: 'rtsp://192.168.1.100:554/stream1',  // URL interna da câmera
  // A VPS precisa ter acesso à rede da câmera!
}
```

#### Cenário 3: Tunnel Server (Acesso Remoto)

Para câmeras atrás de NAT/firewall sem IP público:

```
┌───────────────┐                    ┌────────────────┐
│   Site Cliente │                    │      VPS       │
│                │                    │                │
│  ┌──────────┐  │   ┌────────────┐   │ ┌──────────┐   │
│  │ Câmera   │──│──▶│  Tunnel   │───│──▶│  VMS     │   │
│  │ (NAT)    │  │   │  Client   │   │   │ Backend  │   │
│  └──────────┘  │   └────────────┘   │ └──────────┘   │
│                │                    │                │
└───────────────┘                    └────────────────┘
            │                              │
            └────────── Tunnel ────────────┘
              (link.vcloud.ai:10000)
```

**Configuração do Tunnel:**
```javascript
// .env
TUNNEL_SERVER_HOST=link.vcloud.ai
TUNNEL_SERVER_PORT=10000
TUNNEL_SERVER_PROTOCOL=https

// GeneralSettings.tunnelConf (JSON)
{
  "enabled": true,
  "token": "abc123...",
  "cameras": ["camera-uuid-1", "camera-uuid-2"]
}
```

---

## 🔐 Sistema de Licenciamento

O CluebaseVMS possui **dois modos de licenciamento**:

### 1. Licenciamento Online (Padrão)

```javascript
// config.js
licenseApi: {
  protocol: 'http',
  host: 'licsrv.vcloud.ai',  // ← Servidor de licenças
  port: '80',
}
```

**Fluxo:**
```
VMS Backend ──HTTP POST──▶ licsrv.vcloud.ai
                              │
                              ├── Valida licença
                              ├── Retorna número de câmeras
                              └── Retorna features ativas
```

**Variável .env:**
```bash
DISABLE_ONLINE_LICENSE_OPT=0  # 0 = Habilitado
```

### 2. Licenciamento Offline (Local)

Quando `DISABLE_ONLINE_LICENSE_OPT=1`, o sistema opera sem validação online.

**Arquivos de licença local:**
```
/static/licenses/
├── license.json
└── license.key
```

---

## ☁️ Modo Cloud (isCloudMode)

O sistema possui um **modo cloud** explícito:

```javascript
// Migracao 20240308123201
GeneralSettings.isCloudMode: boolean  // true = modo cloud
```

### Diferenças entre Modos

| Feature | Modo Local | Modo Cloud |
|---------|-----------|------------|
| **Storage** | Local (`/static/archive`) | Cloud (Huawei, Google, Amazon) |
| **Câmeras** | LAN (RTSP direto) | Remotas (via Tunnel/Internet) |
| **Acesso** | Navegador local | HTTPS público |
| **Licenciamento** | Online/Offline | Online obrigatório |
| **STUN/TURN** | Opcional | Recomendado |
| **Multi-tenant** | Opcional | Ativado |

### Cloud Storage Vendors

```javascript
exports.CLOUD_STORAGE_VENDORS = {
  HUAWEI: 'Huawei',
  GOOGLE: 'Google',
  AMAZON: 'Amazon',
};
```

**Configuração:**
```javascript
// Storage model
{
  type: 'cloud',  // local | cloud
  vendor: 'Amazon',  // Huawei | Google | Amazon
  bucketName: 'vms-archive',
  region: 'sa-east-1',
  accessKey: 'AKIA...',
  secretKey: 'xxx...',
  isCloudStorage: true
}
```

---

## 🔒 Segurança para VPS

### 1. SSL/TLS (OBRIGATÓRIO)

```bash
# Instalar Certbot
apt install certbot python3-certbot-nginx

# Gerar certificado
certbot --nginx -d vms.cliente.com.br

# Auto-renew (crontab)
0 0 * * * certbot renew --quiet
```

### 2. Firewall (UFW)

```bash
# Permitir apenas portas necessárias
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP (Let's Encrypt)
ufw allow 443/tcp   # HTTPS
ufw allow 8565/tcp  # RTSP (se câmeras publicam)
ufw enable
```

### 3. MySQL Seguro

```yaml
# docker-compose.yml
mysql:
  ports:
    - "127.0.0.1:3307:3306"  # ← SOMENTE localhost!
  # NUNCA expor MySQL público
```

### 4. Senhas Fortes

```bash
# Gerar senha MySQL
openssl rand -base64 32

# Gerar SECRET_WORD
openssl rand -hex 32
```

### 5. Rate Limiting (Nginx)

```nginx
http {
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    server {
        location /api {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://app_back:3000;
        }
    }
}
```

---

## 📦 Deploy Passo a Passo em VPS

### 1. Preparar Servidor

```bash
# Ubuntu 22.04/24.04
apt update && apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com | sh

# Instalar Docker Compose
apt install docker-compose-plugin -y

# Iniciar Docker
systemctl enable docker
systemctl start docker
```

### 2. Upload dos Arquivos

```bash
# Criar diretório
mkdir -p /opt/cluebase-vms
cd /opt/cluebase-vms

# Upload via SCP/SFTP
scp -r CluebaseVMS-windows/* root@vps:/opt/cluebase-vms/

# Estrutura esperada
/opt/cluebase-vms/
├── all_images.tar          # Imagens Docker
├── docker-confs/
│   └── docker-compose-ai.yml
├── .env                    # ← Configurar!
├── nginx.conf
├── rtsp-simple-server.yml
├── branding/
├── certs/
└── mysql-conf/
```

### 3. Configurar .env

```bash
cp .env .env.backup

# Editar com dados da VPS
nano .env

# Mínimo necessário:
APP_HOST=<IP_DA_VPS_ou_DOMINIO>
MACHINE_HOST=<IP_DA_VPS_ou_DOMINIO>
MYSQL_PASSWORD=<senha_forte>
SECRET_WORD=<secret_forte>
TZ=America/Sao_Paulo
```

### 4. Carregar Imagens Docker

```bash
# Load das imagens offline
docker load -i all_images.tar

# Verificar imagens carregadas
docker images
# Deve mostrar:
# vcloudaiorg/vcloudai-vms-back-end-public
# vcloudaiorg/vcloudai-vms-front-end-public
# vcloudaiorg/vcloudai-vms-ai
# vcloudaiorg/vcloudai-vms-motion
# vcloudaiorg/vcloudai-vms-stream
# mysql:8.0.32
# aler9/rtsp-simple-server
# nginx:latest
```

### 5. Preparar Docker Compose

```bash
# Copiar compose de AI
cp docker-confs/docker-compose-ai.yml docker-compose.yml

# Se necessário, ajustar network mode
nano docker-compose.yml
```

### 6. Iniciar Sistema

```bash
# Subir todos os containers
docker compose up -d

# Verificar status
docker compose ps

# Ver logs
docker compose logs -f backend
docker compose logs -f ai
docker compose logs -f nginx
```

### 7. Verificar Instalação

```bash
# Backend API
curl http://localhost:3000/api/health

# Frontend
curl http://localhost:80

# RTSP Server
curl http://localhost:8565/v1/paths/list

# AI Service
curl http://localhost:9001/api/health
```

### 8. Configurar Nginx como Proxy Reverso (Opcional)

Se quiser Nginx externo na frente do Docker:

```nginx
server {
    listen 443 ssl;
    server_name vms.cliente.com.br;

    ssl_certificate /etc/letsencrypt/live/vms.cliente.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vms.cliente.com.br/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket para Socket.io
    location /api/socket.io {
        proxy_pass http://127.0.0.1:80;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }
}
```

---

## 🔧 Manutenção em Produção

### Backup do Banco de Dados

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/backups/vms"
mkdir -p $BACKUP_DIR

docker exec database mysqldump -u root -p"$MYSQL_PASSWORD" vcloud > \
  $BACKUP_DIR/vcloud_$DATE.sql

# Comprimir
gzip $BACKUP_DIR/vcloud_$DATE.sql

# Manter apenas últimos 7 dias
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup completo: $BACKUP_DIR/vcloud_$DATE.sql.gz"
```

**Crontab:**
```
0 2 * * * /opt/scripts/backup.sh
```

### Update do Sistema

```bash
# Parar containers
docker compose down

# Pull novas imagens (se atualizadas)
docker compose pull

# Carregar imagens offline (se novo tarball)
docker load -i all_images.tar

# Recriar containers
docker compose up -d

# Verificar logs
docker compose logs -f
```

### Monitoramento

```bash
# Uso de recursos
docker stats

# Logs em tempo real
docker compose logs -f backend

# Health check
docker inspect --format='{{.State.Health.Status}}' database

# Reiniciar serviço específico
docker compose restart ai
```

---

## 🌍 Configuração de STUN/TURN para WebRTC

### Por que STUN/TURN é necessário?

Quando o operador acessa a VPS de **fora da rede local**, o WebRTC precisa de servidores STUN/TURN para atravessar NAT/firewall.

### Configuração Atual

```json
// webrtc-config.json
{
  "server": {
    "http_port": ":4002",
    "ice_servers": [
      "stun:stun.l.google.com:19302",
      "stun:stun1.l.google.com:19302"
    ]
  }
}
```

### Configuração Recomendada para Produção

```json
{
  "server": {
    "http_port": ":4002",
    "ice_servers": [
      "stun:stun.l.google.com:19302",
      "stun:stun1.l.google.com:19302",
      "stun:stun2.l.google.com:19302",
      "stun:stun3.l.google.com:19302",
      "stun:stun4.l.google.com:19302",
      "turn:turn.vms.cliente.com.br:3478",
      {
        "urls": ["turn:turn.vms.cliente.com.br:3478"],
        "username": "vms_user",
        "credential": "senha_turn_forte"
      }
    ],
    "webrtc_port_min": 50000,
    "webrtc_port_max": 50100
  }
}
```

### Instalar Servidor TURN (Coturn)

```bash
apt install coturn -y

# /etc/coturn/turnserver.conf
listening-port=3478
external-ip=203.0.113.50
min-port=50000
max-port=50100
user=vms_user:senha_turn_forte
realm=vms.cliente.com.br
lt-cred-mech
```

---

## 📊 Arquitetura Completa VPS (Produção)

```
                          Internet
                              │
                    ┌─────────┴─────────┐
                    │   Cloudflare CDN  │
                    │   (DDoS Protect)  │
                    └─────────┬─────────┘
                              │
                    ┌─────────┴─────────┐
                    │      VPS (Ubuntu)  │
                    │   IP: 203.0.113.50 │
                    │                     │
                    │  ┌───────────────┐  │
                    │  │  Nginx Proxy  │  │
                    │  │  :443 (SSL)   │  │
                    │  └───────┬───────┘  │
                    │          │          │
                    │  ┌───────┴───────┐  │
                    │  │ Docker Compose│  │
                    │  │                │  │
                    │  │ ┌──────────┐  │  │
                    │  │ │ Backend  │  │  │
                    │  │ │ Node.js  │  │  │
                    │  │ │ :3000    │  │  │
                    │  │ └────┬─────┘  │  │
                    │  │      │        │  │
                    │  │ ┌────┴────┐   │  │
                    │  │ │ MySQL   │   │  │
                    │  │ │ :3306   │   │  │
                    │  │ └─────────┘   │  │
                    │  │                │  │
                    │  │ ┌──────────┐  │  │
                    │  │ │ Frontend │  │  │
                    │  │ │ React    │  │  │
                    │  │ └──────────┘  │  │
                    │  │                │  │
                    │  │ ┌──────────┐  │  │
                    │  │ │   AI     │  │  │
                    │  │ │ :9001    │  │  │
                    │  │ └──────────┘  │  │
                    │  │                │  │
                    │  │ ┌──────────┐  │  │
                    │  │ │  WebRTC  │  │  │
                    │  │ │  :4002   │  │  │
                    │  │ └──────────┘  │  │
                    │  │                │  │
                    │  │ ┌──────────┐  │  │
                    │  │ │  Coturn  │  │  │
                    │  │ │  :3478   │  │  │
                    │  │ └──────────┘  │  │
                    │  └────────────────┘  │
                    └──────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │   Câmeras (RTSP)  │
                    │                   │
                    │  Site A: 5 câmeras│
                    │  Site B: 3 câmeras│
                    │  Site C: 8 câmeras│
                    └───────────────────┘
```

---

## ⚠️ Checklist de Produção

### Pré-Deploy
- [ ] VPS com Ubuntu 22.04+ e Docker instalado
- [ ] Domínio configurado (vms.cliente.com.br)
- [ ] SSL/TLS certificado (Let's Encrypt)
- [ ] Firewall configurado (UFW)
- [ ] Senhas fortes geradas
- [ ] Backup strategy definida
- [ ] Monitoramento configurado

### Deploy
- [ ] Imagens Docker carregadas
- [ ] `.env` configurado corretamente
- [ ] `docker-compose.yml` ajustado
- [ ] Containers subindo sem erros
- [ ] Health checks passando

### Pós-Deploy
- [ ] Acesso HTTPS funcionando
- [ ] WebSocket (Socket.io) funcionando
- [ ] Câmeras conectadas
- [ ] WebRTC testado (com e sem TURN)
- [ ] Licenciamento validado
- [ ] Backup automático ativo
- [ ] Logs centralizados
- [ ] Alertas configurados

---

## 🚨 Troubleshooting VPS

### Problema: Containers não sobem
```bash
# Ver logs
docker compose logs

# Verificar portas em uso
netstat -tulpn | grep :80

# Verificar espaço em disco
df -h
```

### Problema: WebRTC não conecta
```bash
# Verificar STUN/TURN
docker compose logs webrtc

# Testar conectividade
curl http://localhost:4002/stream/codec/test

# Verificar portas UDP
iptables -L -n | grep 50000
```

### Problema: Câmeras não aparecem
```bash
# Verificar RTSP Server
curl http://localhost:8565/v1/paths/list

# Testar RTSP URL
ffprobe rtsp://camera-ip:554/stream1

# Verificar logs do backend
docker compose logs backend | grep RTSP
```

### Problema: IA não processa
```bash
# Verificar serviço AI
docker compose logs ai

# Verificar GPU (se aplicável)
nvidia-smi

# Verificar modelos
ls -la /opt/cluebase-vms/static/customAIModels/
```

---

*Documento gerado em 11 de Abril de 2026*
