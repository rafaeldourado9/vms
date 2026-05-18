# System Design

> Visão completa do sistema: topologia de serviços, fluxo de dados, protocolos de comunicação e decisões de infraestrutura.

---

## 1. Topologia de Serviços

```
                           INTERNET / REDE DO CLIENTE
                                     │
                     ┌───────────────▼───────────────┐
                     │           Nginx :80/443        │
                     │  (TLS termination, HSTS, CSP)  │
                     └───┬───────────────────────┬───┘
                         │                       │
              /api/*      │                       │  /static/* (frontend)
              /webhooks/* │                       │
              /sse/*      │                       │
                         ▼                       ▼
               ┌──────────────────┐    ┌──────────────────┐
               │  FastAPI :8000   │    │  React SPA       │
               │  (async uvicorn) │    │  (nginx serve)   │
               └──────┬───────────┘    └──────────────────┘
                      │
          ┌───────────┼──────────────────────────┐
          │           │                          │
          ▼           ▼                          ▼
   ┌─────────┐  ┌──────────┐          ┌──────────────────┐
   │Postgres │  │  Redis   │          │    RabbitMQ      │
   │  :5432  │  │  :6379   │          │  Exchange:       │
   │(primary │  │(pubsub + │          │  vms_events      │
   │  store) │  │  ARQ Q)  │          │  (topic)         │
   └─────────┘  └──────────┘          └──────────────────┘
                      │                          │
                      ▼                          ▼
               ┌──────────────┐      ┌───────────────────┐
               │  ARQ Worker  │      │  Celery Workers   │
               │  (recordings │      │  (notifications,  │
               │   reports,   │      │   analytics tasks)│
               │   cleanup)   │      └───────────────────┘
               └──────────────┘

STREAMING PATH:
  Câmera RTSP ──────────────────────────────────▶ MediaMTX :8554
  VMS Agent (ffmpeg -c copy) ──RTMP──────────────▶ MediaMTX :1935
                                                         │
                                             ┌───────────┴────────────┐
                                             │                        │
                                        HLS :8888              WebRTC :8889
                                        (browser VOD)          (browser live)
                                             │
                                    webhooks (segment_ready,
                                             on_ready,
                                             on_not_ready)
                                             │
                                             ▼
                                    FastAPI /webhooks/mediamtx/*

ANALYTICS PATH:
  Câmera RTSP ──▶ analytics_service ──▶ YOLOv8 Plugin
                       │ frames           │ AnalyticsResult
                       │                  ▼
                       │         POST /api/v1/analytics/events
                       │                  │
                       │                  ▼
                       │         analytics_events table
                       │                  │
                       └─────── GET /api/v1/analytics/rois
                                (busca zonas configuradas)

CLIENTE EXTERNO (VMS Agent):
  ┌────────────────────────────────┐
  │  VMS Agent                     │
  │  - Poll GET /agents/me/config  │
  │  - POST /agents/me/heartbeat   │
  │  - WS  /agents/me/ws          │
  │  - ffmpeg -c copy RTSP→RTMP    │
  └────────────────────────────────┘
```

---

## 2. Fluxos de Dados Críticos

### 2.1 Fluxo A — ALPR Event-based (câmeras inteligentes)

```
Câmera Hikvision/Intelbras
        │ POST evento ALPR (ISAPI/HTTP)
        ▼
FastAPI /webhooks/alpr/{manufacturer}
        │
        ├── Normalizer (fabricante-específico)
        │       Hikvision: XML ISAPI → AlprDetection
        │       Intelbras: JPEG binário Dahua ITC → AlprDetection
        │       Generic:   JSON → AlprDetection
        │
        ├── Confidence filter (min: 0.80)
        │
        ├── Redis DEDUP check
        │       Key: alpr:dedup:{camera_id}:{plate}  TTL=60s
        │       Key: alpr:dedup:exact:{cam}:{plate}:{ts_bucket}  TTL=86400s
        │       └── Se duplicado → retorna 200 sem persistir
        │
        ├── INSERT vms_events
        │
        ├── Publish domain event "alpr.detected" (Redis pubsub)
        │       └── SSE bridge → frontend recebe em tempo real
        │
        └── Enqueue ARQ task "dispatch_notification"
                └── Match notification_rules (glob pattern)
                └── POST webhook com HMAC-SHA256 header
                └── INSERT notification_logs
```

### 2.2 Fluxo B — Analytics server-side (câmeras burras)

```
Câmera bullet RTSP
        │ pull direto pelo analytics_service
        ▼
analytics_service (Python, contêiner separado)
        │
        ├── GET /api/v1/analytics/rois     (busca zonas por câmera)
        ├── Frame capture @ 1 FPS
        │
        ├── SharedInferenceEngine (YOLOv8n)
        │       Roda 1 vez por frame → detecta todos os objetos
        │
        ├── Plugins paralelos:
        │       intrusion  → filtra por ROI polygon → evento se violação
        │       people_count → conta pessoas no frame
        │       vehicle_count → conta veículos
        │       lpr → detecta placa → PaddleOCR → texto
        │       fire_smoke → modelo dedicado
        │       ppe_detection → modelo dedicado
        │
        └── POST /api/v1/analytics/events (API key auth)
                └── INSERT analytics_events
                └── Publish "analytics.{plugin}.detected"
```

### 2.3 Fluxo de Gravação

```
MediaMTX (gravação automática, segmentos de 60s)
        │ POST /webhooks/mediamtx/segment_ready
        ▼
FastAPI webhook handler
        │
        └── Enqueue ARQ task "index_segment"
                │
                ├── Compute SHA-256 do arquivo .mp4
                ├── INSERT recording_segments
                │       {file_path, started_at, ended_at, duration, size, sha256}
                └── Append custody_chain[0]: {action:"indexed", ts, actor:"system"}
```

### 2.4 Fluxo de Autenticação

```
Browser
  │ POST /auth/token {email, password}
  ▼
FastAPI → bcrypt verify → gera JWT access (15min) + refresh (7d)
  │
  ├── Access token: Bearer em Authorization header
  └── Refresh token: POST /auth/refresh → novo par de tokens

VMS Agent
  │ Authorization: Agent <api_key>
  ▼
FastAPI → hash lookup em api_keys → resolve tenant + owner
```

---

## 3. Comunicação entre Serviços

| Canal | Protocolo | Uso | Garantia |
|-------|-----------|-----|----------|
| API → PostgreSQL | asyncpg (TCP) | Persistência primária | ACID |
| API → Redis (pubsub) | aioredis | Domain events, SSE bridge | Fire-and-forget |
| API → Redis (ARQ) | aioredis | Task queue | At-least-once |
| API → RabbitMQ | aio-pika (AMQP) | Event bus topic exchange | Durable |
| API → MediaMTX | HTTP (REST) | Gerenciar paths de stream | Sync |
| analytics_service → API | HTTP (REST) | Ingest eventos, fetch ROIs | Sync |
| MediaMTX → API | HTTP webhooks | Notificar eventos de stream | Sync |
| Worker → PostgreSQL | asyncpg | Ler/gravar tarefas | ACID |
| Nginx → API | HTTP (proxy_pass) | TLS termination | Sync |
| VMS Agent → API | HTTP polling + WS | Config pull, heartbeat | Polling 30s |
| VMS Agent → MediaMTX | RTMP (ffmpeg) | Push stream | Streaming |
| Câmera → MediaMTX | RTSP pull | Ingestão de vídeo | Streaming |

---

## 4. Infraestrutura Docker Compose

| Serviço | Imagem base | Portas expostas | Healthcheck | Depende de |
|---------|-------------|-----------------|-------------|------------|
| `postgres` | postgres:16 | 5432 | `pg_isready` | — |
| `redis` | redis:7-alpine | 6379 | `redis-cli ping` | — |
| `rabbitmq` | rabbitmq:3-management | 5672, 15672 | `rabbitmq-diagnostics` | — |
| `mediamtx` | bluenviron/mediamtx | 8554, 1935, 8888, 8889, 9997, 9998 | `curl /v3/config/global/get` | — |
| `api` | ./api (production) | 8000 | `curl /health` | postgres, redis, rabbitmq, mediamtx |
| `worker` | ./api | — | redis ping | postgres, redis, rabbitmq |
| `analytics` | ./analytics (cpu/gpu) | 8001 | `curl /health` | api |
| `frontend` | ./frontend (nginx) | 3000 | — | — |
| `nginx` | nginx:alpine | 80, 443 | `curl /health` | api, frontend |
| `edge-agent` | ./edge_agent | — | — | api, mediamtx *(profile: agent)* |
| `cloudflared` | cloudflare/cloudflared | — | — | api *(profile: dev)* |
| `backup` | postgres:16-alpine | — | — | postgres *(profile: backup)* |

### Volumes

| Volume | Montado em | Propósito |
|--------|-----------|-----------|
| `pgdata` | /var/lib/postgresql/data | Dados PostgreSQL |
| `recordings` | /recordings | Segmentos de vídeo MP4 |
| `vod_streams` | /tmp/vod | Paths HLS temporários |
| `backups` | /backups | Dumps PostgreSQL comprimidos |
| `tunnel_data` | /etc/cloudflared | Config Cloudflare tunnel |

---

## 5. Segurança de Rede

```
Internet
    │
    ▼ :80 → redirect :443
  Nginx (TLS termination)
    │ Headers:
    │   Strict-Transport-Security: max-age=31536000; includeSubDomains
    │   X-Frame-Options: DENY
    │   X-Content-Type-Options: nosniff
    │   Content-Security-Policy: default-src 'self' ...
    │   Referrer-Policy: no-referrer
    │
    ├── /api/*      → proxy_pass api:8000
    ├── /webhooks/* → proxy_pass api:8000 (rate limit: 100/min/IP via slowapi)
    └── /sse/*      → proxy_pass api:8000 (SSE streaming)

Rede interna Docker (bridge "vms"):
  - Serviços comunicam por nome de serviço
  - PostgreSQL, Redis, RabbitMQ NÃO expostos ao host em produção
  - MediaMTX API (:9997) acessível apenas internamente
```

---

## 6. Escalabilidade

| Componente | Estratégia atual | Como escalar |
|-----------|-----------------|--------------|
| API (FastAPI) | 1 instância, async | Múltiplas instâncias + load balancer (Nginx upstream) |
| Worker (ARQ) | 1 instância, max_jobs=50 | Múltiplas instâncias (ARQ é stateless) |
| Analytics | 1 instância por tipo (cpu/gpu) | 1 instância por GPU + queue por câmera |
| PostgreSQL | 1 primário | Read replicas para queries de relatórios |
| Redis | 1 instância | Redis Cluster para HA |
| MediaMTX | 1 instância | Múltiplas instâncias por região (stateful) |

---

## 7. Observabilidade

| Sinal | Implementação | Endpoint |
|-------|--------------|---------|
| **Health** | FastAPI route, sem auth | `GET /health` → `{status, services:{db,redis,rabbitmq}}` |
| **Logs** | JSON estruturado (python-json-logger) em produção | stdout → coleta por Docker logging driver |
| **Métricas MediaMTX** | MediaMTX Prometheus exporter | `:9998/metrics` |
| **Métricas Analytics** | FPS + processing time por plugin | Interno no analytics_service |
| **Backup** | pg_dump comprimido com timestamp | `infra/scripts/backup_db.sh` → `/backups/` |
