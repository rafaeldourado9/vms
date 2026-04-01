# VMS MVP — Guia de Deploy

> Checklist para produção. Siga na ordem.

---

## Pré-requisitos

- Servidor Linux (Ubuntu 22.04 LTS recomendado)
- Docker Engine 24+ + Docker Compose v2
- 8GB RAM mínimo (16GB para analytics com GPU)
- 500GB disco (gravações 7 dias × 200 câmeras ≈ ~2TB — ajuste `retention_days`)
- Porta 80/443 acessível (ou VPN interna)
- Domínio ou IP fixo para o servidor VMS

---

## 1. Clonar e configurar

```bash
git clone https://github.com/seu-org/vms-mvp.git /opt/vms
cd /opt/vms
cp .env.example .env
```

---

## 2. Editar `.env`

```bash
# OBRIGATÓRIO mudar:
SECRET_KEY=<gerar com: openssl rand -hex 32>
POSTGRES_PASSWORD=<senha forte>
RABBITMQ_PASSWORD=<senha forte>
ANALYTICS_API_KEY=<gerar com: openssl rand -hex 32>

# Opcional (padrões razoáveis para produção):
ALPR_DEDUP_TTL_SECONDS=60
MAX_CAMERAS=200
RECORDINGS_PATH=/mnt/recordings   # montar disco dedicado aqui
```

---

## 3. Disco de gravações

```bash
# Criar ponto de montagem
sudo mkdir -p /mnt/recordings
# Montar disco dedicado (recomendado)
sudo mount /dev/sdb1 /mnt/recordings
# Adicionar ao /etc/fstab para persistir reboot
echo "/dev/sdb1 /mnt/recordings ext4 defaults 0 2" | sudo tee -a /etc/fstab
```

---

## 4. TLS / HTTPS

```bash
# Opção A: Let's Encrypt (domínio público)
sudo apt install certbot
sudo certbot certonly --standalone -d vms.seudominio.com.br
# Colocar em infra/nginx/certs/

# Opção B: Certificado próprio (rede interna)
openssl req -x509 -nodes -days 3650 -newkey rsa:4096 \
  -keyout infra/nginx/certs/vms.key \
  -out infra/nginx/certs/vms.crt \
  -subj "/CN=vms.local"
```

---

## 5. Iniciar a stack

```bash
cd /opt/vms
docker compose pull
docker compose up -d
```

---

## 6. Criar tenant e usuário admin

```bash
# Após stack subir (aguardar ~30s):
docker compose exec api python -m vms.scripts.create_tenant \
  --name "Integrador Principal" \
  --slug "principal" \
  --admin-email admin@empresa.com \
  --admin-password "SenhaForte123"
```

---

## 7. Configurar agent no cliente

No servidor do cliente (onde estão as câmeras):

```bash
# .env do agent:
VMS_API_URL=https://vms.seudominio.com.br
VMS_API_KEY=vms_abc12345_xxxxxxxxxxxx   # gerado no VMS
AGENT_POLL_INTERVAL=30

# Subir agent:
docker compose -f docker-compose.agent.yml up -d
```

---

## 8. Verificar saúde

```bash
# Health check
curl https://vms.seudominio.com.br/health

# Deve retornar:
# { "status": "healthy", "services": { "database": "ok", "redis": "ok", "rabbitmq": "ok" } }

# Logs
docker compose logs -f api
docker compose logs -f analytics
```

---

## 9. Monitoramento básico

```bash
# Ver câmeras online
curl -H "Authorization: Bearer <token>" \
  https://vms.seudominio.com.br/api/v1/cameras?is_online=true

# Ver eventos recentes
curl -H "Authorization: Bearer <token>" \
  https://vms.seudominio.com.br/api/v1/events?page_size=10
```

---

## 10. Backup automatizado

```bash
# Configurar cron (backup diário 3h)
crontab -e
0 3 * * * /opt/vms/infra/scripts/backup_db.sh >> /var/log/vms-backup.log 2>&1
```

---

## 11. Atualização

```bash
cd /opt/vms
git pull
docker compose pull
docker compose up -d --build
# Rodar migrations automaticamente no startup da API
```

---

## Checklist de Produção

### Segurança
- [ ] `SECRET_KEY` não é o valor default
- [ ] Senhas de banco/rabbit trocadas
- [ ] TLS habilitado (HTTPS)
- [ ] `DEBUG=false`
- [ ] Firewall: só 80/443 exposto externamente
- [ ] Porta 5432 (Postgres) não acessível externamente
- [ ] Porta 5672 (RabbitMQ) não acessível externamente

### Infraestrutura
- [ ] Disco de gravações montado em `/mnt/recordings`
- [ ] `RECORDINGS_PATH` configurado corretamente
- [ ] Backup automático configurado
- [ ] `.env` com permissão 600: `chmod 600 .env`

### Funcional
- [ ] `curl /health` retorna 200 com todos serviços ok
- [ ] Tenant e admin criados
- [ ] Agent configurado e online
- [ ] Câmera de teste aparece online
- [ ] Gravação de teste aparece em /api/v1/recordings
- [ ] Timeline retorna heat map correto
- [ ] VOD playback funciona (HLS.js scrubbing)
- [ ] Webhook de notificação testado
- [ ] PTZ funciona (se câmera ONVIF com suporte)

---

## Estimativas de Capacidade (por instância)

### Armazenamento (por câmera, por dia)

| Codec  | Bitrate   | Armazenamento/câmera/dia |
|--------|-----------|--------------------------|
| H.264  | ~500 kbps | ~5.4 GB                  |
| H.265  | ~250 kbps | ~2.7 GB  ← recomendado   |
| H.265  | ~150 kbps | ~1.6 GB  (qualidade mín) |

> O VMS usa `-c copy` — bitrate depende do encoder da câmera.
> Configure H.265 nas câmeras para maximizar retenção pelo mesmo custo de disco.

### Armazenamento total

| Câmeras | Retenção | H.264  | H.265  |
|---------|----------|--------|--------|
| 50      | 7 dias   | 1.9 TB | 950 GB |
| 100     | 7 dias   | 3.8 TB | 1.9 TB |
| 200     | 7 dias   | 7.5 TB | 3.8 TB |
| 200     | 15 dias  | 16 TB  | 8 TB   |

### Recursos computacionais

| Câmeras | RAM API | RAM Analytics | CPU Analytics | GPU       |
|---------|---------|---------------|---------------|-----------|
| 10      | 512MB   | 1GB           | 1 core        | opcional  |
| 50      | 1GB     | 2GB           | 2 cores       | opcional  |
| 100     | 2GB     | 4GB           | 4 cores       | opcional  |
| 200     | 4GB     | 6GB           | 4 cores       | opcional* |

*GPU recomendada apenas se > 50 câmeras com ROI intrusion em modo real-time.*
*Analytics pós-gravação (padrão): CPU é suficiente.*

---

## Problemas Comuns

### MediaMTX não aceita stream do agent
- Verificar se agent consegue resolver hostname do MediaMTX
- Checar firewall porta 1935 (RTMP)
- Logs: `docker compose logs mediamtx`

### Analytics não processa câmeras
- Modo pós-gravação: verificar se ARQ worker está rodando (`docker compose logs worker`)
- Verificar se `segment_ready` webhook está configurado no mediamtx.yml
- Verificar `ANALYTICS_API_KEY` igual nos dois serviços
- Checar ROIs configuradas: `GET /api/v1/analytics/rois`
- Modo real-time (intrusion): verificar ROIs com `ia_type=intrusion` e `is_active=true`
- Logs: `docker compose logs analytics`

### VOD / Timeline não funciona
- Verificar se MediaMTX tem recording habilitado no mediamtx.yml
- Verificar se `/mnt/recordings` está acessível pelo MediaMTX e pelo Nginx
- Verificar se segments aparecem em `GET /api/v1/recordings?camera_id=<id>`
- Nginx: checar se /recordings/ tem auth_request configurado

### Gravações não aparecem
- Verificar permissão em `/mnt/recordings`
- Checar webhook `segment_ready` no MediaMTX config
- Logs: `docker compose logs worker`

---

## Conectividade NAT / P2P

### Arquitetura de fluxo de vídeo

O VMS resolve o problema de NAT de forma assimétrica:

| Fluxo | Direção | Problema NAT | Solução |
|-------|---------|-------------|---------|
| Vídeo (RTMP) | Agent → VMS | Agent inicia conexão de saída | Sem problema — saída sempre funciona |
| Config push (WS) | Agent → VMS | Agent inicia WebSocket de saída | Sem problema — saída sempre funciona |
| HLS/WebRTC viewer | Browser → VMS | Browser acessa VMS diretamente | Sem problema — VMS tem IP público |

**O Agent nunca precisa de porta aberta.** Ele sempre inicia as conexões.

### WebRTC e ICE (STUN/TURN)

Para viewers WebRTC, o browser precisa estabelecer ICE com o MediaMTX.

**STUN (padrão):**
Configurado automaticamente com `stun:stun.l.google.com:19302`.
Funciona em 90% dos casos (NAT cone, NAT full cone, NAT restrito).

**TURN (NAT simétrico):**
Necessário quando o viewer está atrás de NAT simétrico (empresas, alguns provedores móveis).

Para habilitar TURN, configure em `.env`:
```bash
TURN_URL=turn:turn.suaempresa.com:3478
TURN_USERNAME=usuario-turn
TURN_CREDENTIAL=senha-turn
```

**Instalar coturn (servidor TURN próprio):**
```bash
# Ubuntu/Debian
apt install coturn

# Editar /etc/turnserver.conf
realm=suaempresa.com
server-name=turn.suaempresa.com
listening-port=3478
lt-cred-mech
user=usuario:senha
external-ip=SEU_IP_PUBLICO

# Iniciar
systemctl enable --now coturn
```

> **Quando TURN é necessário:** se viewers em redes corporativas ou 4G não conseguem
> visualizar WebRTC mas HLS funciona, é NAT simétrico → configure TURN.
