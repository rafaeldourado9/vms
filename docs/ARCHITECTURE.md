# VMS MVP — Arquitetura Completa

> Versao: 2.0 · Data: 2026-04-12
> Stack: FastAPI · SQLAlchemy 2 async · PostgreSQL 16 · Redis 7 · RabbitMQ 3 · MediaMTX · React 18

---

## 1. Visao Geral

VMS (Video Management System) white-label multi-tenant para integradores de seguranca brasileiros.
Self-hosted. Ate 200 cameras por instancia. Gravacao 24/7. Streaming ao vivo.
Analytics server-side com 8 plugins YOLOv8 para cameras sem IA embarcada.

### Diferenciais competitivos

| Eixo | Vantagem |
|------|----------|
| Cameras baratas -> inteligentes | YOLOv8 server-side transforma qualquer camera bullet |
| Self-hosted / dados do cliente | Zero dependencia de cloud — compliance LGPD nativo |
| Sem licenca por camera | Modelo por tenant/instancia — TCO 80% menor que Camerite/Monuvo |
| Multi-protocolo | RTSP pull, RTMP push, ONVIF — qualquer camera do mercado BR |

---

## 2. Diagrama de Servicos

```
Rede do Cliente                              Servidor VMS
+--------------------+                +----------------------------------+
|  Cameras RTSP      |                |                                  |
|  192.168.x.x       |                |  Nginx :80/:443                  |
+--------+-----------+                |   |-- /           -> Frontend    |
         | RTSP pull                  |   |-- /api/*      -> API :8000   |
         v                            |   |-- /webhooks/* -> API :8000   |
+--------------------+                |   |-- /hls/*      -> MediaMTX    |
|   Edge Agent       |  RTMP push     |   |-- /webrtc/*   -> MediaMTX    |
|   (ffmpeg -c copy) |--------------->|   +-- /recordings -> Nginx file  |
|   polls config 30s |                |                                  |
+--------------------+                |  FastAPI API :8000               |
                                      |   |-- /api/v1/auth/*             |
  Cameras Hikvision/Intelbras         |   |-- /api/v1/cameras/*          |
  (webhook push)                      |   |-- /api/v1/events/*           |
         |                            |   |-- /api/v1/recordings/*       |
         | HTTP POST                  |   |-- /api/v1/notifications/*    |
         +--------------------------->|   |-- /api/v1/analytics/*        |
                                      |   |-- /api/v1/plugins/*          |
                                      |   |-- /api/v1/sse               |
                                      |   +-- /streaming/* (MediaMTX)    |
                                      |                                  |
                                      |  MediaMTX                        |
                                      |   RTSP :8554 / RTMP :1935       |
                                      |   HLS  :8888 / WebRTC :8889     |
                                      |   API  :9997 / Metrics :9998    |
                                      |        | webhooks               |
                                      |        v                        |
                                      |  Webhooks internos              |
                                      |   on_ready -> camera.online     |
                                      |   on_not_ready -> camera.offline|
                                      |   segment_ready -> index grv    |
                                      |                                  |
                                      |  Analytics Service :8001        |
                                      |   8 plugins YOLOv8              |
                                      |   RTSP pull do MediaMTX         |
                                      |   POST /plugins/events          |
                                      |                                  |
                                      |  ARQ Worker (background)        |
                                      |   queue: notifications          |
                                      |   queue: recordings             |
                                      |   cron: cleanup 03:00           |
                                      |                                  |
                                      |  PostgreSQL :5432               |
                                      |  Redis :6379                    |
                                      |  RabbitMQ :5672                 |
                                      +----------------------------------+
```

---

## 3. Bounded Contexts

```
+-----------------------------------------------------+
|                     API Service                      |
|                                                      |
|  +----------+  +----------+  +--------------------+  |
|  |   IAM    |  | Cameras  |  |     Streaming      |  |
|  |          |  |          |  |  (MediaMTX hooks)   |  |
|  | Tenant   |  | Camera   |  |                    |  |
|  | User     |  | Agent    |  |  StreamSession     |  |
|  | ApiKey   |  | PTZ      |  |  ViewerToken       |  |
|  +----------+  +----------+  +--------------------+  |
|                                                      |
|  +----------+  +----------+  +--------------------+  |
|  |Recordings|  |  Events  |  |   Notifications    |  |
|  |          |  |  (ALPR)  |  |                    |  |
|  | Segment  |  | VmsEvent |  |  Rule -> Dispatch  |  |
|  | Clip     |  | Dedup    |  |  HMAC-signed       |  |
|  +----------+  +----------+  +--------------------+  |
|                                                      |
|  +----------+  +----------+  +--------------------+  |
|  |Analytics |  | Plugins  |  |       SSE          |  |
|  | ROIs     |  | Contract |  |  Redis pub/sub     |  |
|  | Events   |  | API Key  |  |  Realtime events   |  |
|  | Catalog  |  |          |  |                    |  |
|  +----------+  +----------+  +--------------------+  |
+-----------------------------------------------------+

+----------------------------+   +-----------------------+
|    Analytics Service       |   |      Edge Agent       |
|                            |   |                       |
|  Orchestrator              |   |  Config poll (30s)    |
|  8 plugins YOLOv8          |   |  ffmpeg -c copy       |
|  RTSP frame capture        |   |  RTSP pull -> RTMP    |
|  POST /plugins/events      |   |  Heartbeat            |
+----------------------------+   +-----------------------+
```

---

## 4. Protocolos de Camera

### 4.1 RTSP pull via Agent (padrao)

```
Camera IP (rede local)
  |  RTSP pull
  v
Edge Agent (ffmpeg -c copy)      <- roda na rede do cliente
  |  RTMP push
  v
MediaMTX :1935                   <- roda no VMS
  |
  |-- HLS  :8888   -> viewer browser
  |-- WebRTC :8889 -> viewer baixa latencia
  +-- Record /recordings/...
```

### 4.2 RTMP push direto (sem Agent)

```
Camera com RTMP nativo           <- Reolink, algumas Intelbras
  |  RTMP push (stream_key)
  v
MediaMTX :1935
  |  publish-auth hook
  v
API: POST /streaming/publish-auth
  |  valida stream_key
  +-- aceita ou rejeita
```

### 4.3 ONVIF (descoberta automatica)

```
Camera ONVIF (rede local)
  |  WS-Discovery / GetStreamUri
  v
API: POST /cameras/onvif-probe
  |  GetCapabilities -> GetStreamUri -> extrai rtsp_url
  +-- cria camera com stream_protocol=onvif
      (flui como RTSP pull via Agent)
```

### 4.4 Streaming para Viewers (saida)

```
Browser / App
  |  GET /cameras/{id}/stream-urls (JWT)
  v
API: gera ViewerToken (JWT 15min)
  |
  |-- HLS:    /hls/tenant-{id}/cam-{id}/index.m3u8?token=<jwt>
  +-- WebRTC: /webrtc/tenant-{id}/cam-{id}/whep?token=<jwt>

MediaMTX -> POST /streaming/read-auth -> valida ViewerToken
```

---

## 5. Modelo de Dados

### IAM

```
Tenant
  id (uuid PK)
  name, slug (unique), is_active
  facial_recognition_enabled (bool, default=False)
  facial_recognition_consent_at (datetime?)
  created_at

User
  id (uuid PK), tenant_id (FK)
  email, hashed_password, full_name
  role (admin | operator | viewer)
  is_active, created_at

ApiKey
  id (uuid PK), tenant_id (FK)
  owner_type (agent | integration | bot)
  owner_id (uuid), key_hash (bcrypt)
  prefix (12 chars, indexed), is_active
  last_used_at, created_at
```

### Cameras

```
Camera
  id (uuid PK), tenant_id (FK), agent_id (FK?)
  name, location, address
  latitude, longitude (float?)
  ia_enabled (bool)
  stream_protocol (rtsp_pull | rtmp_push | onvif)
  rtsp_url, rtmp_stream_key (unique)
  onvif_url, onvif_username, onvif_password
  manufacturer (generic | hikvision | intelbras)
  retention_days (default=7)
  stream_quality (low | medium | high | source)
  is_active, is_online, ptz_supported
  last_seen_at, created_at

Agent
  id (uuid PK), tenant_id (FK)
  name, status (pending | online | offline)
  last_heartbeat_at, version
  streams_running, streams_failed
  created_at
```

### Streaming & Recordings

```
StreamSession
  id, tenant_id, camera_id
  mediamtx_path, started_at, ended_at

RecordingSegment
  id, tenant_id, camera_id
  mediamtx_path, file_path
  started_at, ended_at
  duration_seconds, size_bytes

Clip
  id, tenant_id, camera_id, vms_event_id?
  starts_at, ends_at
  status (pending | processing | ready | failed)
  file_path, created_at
```

### Events

```
VmsEvent
  id, tenant_id, camera_id?
  event_type, plate?, confidence?
  payload (json), occurred_at
  Index: (tenant_id, occurred_at), (plate)
```

### Notifications

```
NotificationRule
  id, tenant_id, name
  event_type_pattern (fnmatch: "alpr.*")
  destination_url, webhook_secret
  is_active, created_at

NotificationLog
  id, tenant_id, rule_id, vms_event_id
  status (success | failed | timeout)
  response_code, response_body
  attempt, dispatched_at
```

### Analytics

```
AnalyticsROI
  id (uuid PK), tenant_id, camera_id, plugin_id
  name, polygon (json [[x,y]...] normalizado 0-1)
  config (json), is_active
  created_at, updated_at

PluginInstallation
  id, plugin_id, plugin_name, version
  edge_agent_id, tenant_id
  status (installed | running | stopped | error)
  settings (json), model_path, fps_target
  created_at, updated_at

AnalyticsEvent
  id, plugin_installation_id?, tenant_id
  camera_id, camera_name, plugin_id
  event_type, severity (critical | warning | info)
  confidence, payload (json), snapshot_path
  occurred_at, created_at
```

---

## 6. Fluxos Principais

### 6.1 ALPR — Camera inteligente (push)

```
Camera Hikvision ANPR
  | HTTP POST (XML/JSON)
  v
POST /webhooks/alpr/hikvision
  v
Normalizer (Hikvision | Intelbras | Generic)
  v
EventService.ingest_alpr()
  v
Redis dedup: SET alpr:dedup:{camera}:{plate} NX EX 60
  | (duplicata -> ignorar)
  v
VmsEvent.create() -> publish "alpr.detected" -> SSE + Notifications
```

### 6.2 ALPR — Analytics server-side (camera burra)

```
Camera RTSP -> MediaMTX
  | frame capture 1fps
  v
Analytics Service (plugin lpr)
  | YOLOv8 detect + fast-plate-ocr
  v
POST /api/v1/plugins/events
  v
VmsEvent + AnalyticsEvent criados -> SSE
```

### 6.3 Gravacao 24/7

```
Camera -> Agent -> MediaMTX
  | auto-record (60s fmp4 segments)
  | /recordings/{path}/{date}/{time}.mp4
  v (runOnRecordSegmentComplete hook)
POST /webhooks/mediamtx/segment_ready
  v
ARQ task: index_segment()
  v
RecordingSegment.create()
  v
Retention check -> delete > retention_days
```

### 6.4 Analytics Pipeline

```
Orchestrator.start()
  | GET /plugins/cameras -> lista cameras online
  | GET /plugins/rois -> lista ROIs por camera
  v
Per camera (asyncio task):
  FrameSource.open(rtsp://mediamtx:8554/{path})
  loop:
    frame = source.read() (1fps)
    for plugin in plugins:
      results = plugin.process_frame(frame, metadata, rois)
      for result in results:
        POST /plugins/events -> VmsEvent + AnalyticsEvent
```

---

## 7. Infraestrutura Docker

### Servicos

| Servico | Imagem | Portas | Finalidade |
|---------|--------|--------|------------|
| postgres | infra/postgres (PG 16) | 5432 | Banco relacional |
| redis | redis:7-alpine | 6379 | Cache, dedup, ARQ queue, SSE pub/sub |
| rabbitmq | rabbitmq:3-management | 5672, 15672 | Event bus topic exchange |
| mediamtx | infra/mediamtx | 8554, 1935, 8888, 8889 | Streaming RTSP/RTMP/HLS/WebRTC |
| api | api/ (FastAPI) | 8000 | REST API + webhooks |
| worker | api/ (ARQ) | - | Background tasks |
| analytics | analytics/ (FastAPI) | 8001 | 8 plugins YOLOv8 |
| frontend | frontend/ (React) | 80 | SPA |
| nginx | infra/nginx | 80, 443 | Reverse proxy + TLS |
| cloudflared | (profile: dev) | - | Tunnel Cloudflare dev |
| backup | (profile: backup) | - | pg_dump agendado |

### Rede e Volumes

```
Network: vms (bridge)

Volumes:
  pgdata       -> PostgreSQL data
  recordings   -> Video segments (MediaMTX + Nginx)
  backups      -> Database dumps
  tunnel_data  -> Cloudflare tunnel metadata
```

### Nginx Routing

| Location | Backend | Rate Limit | Notas |
|----------|---------|-----------|-------|
| / | frontend:80 | - | SPA |
| /api/v1/auth/ | api:8000 | 5/min | Login agressivo |
| /api/ | api:8000 | 60/min | API geral |
| /webhooks/ | api:8000 | 30/min | Webhooks cameras |
| /api/v1/sse | api:8000 | - | SSE sem buffering |
| /hls/ | mediamtx:8888 | - | HLS streaming |
| /webrtc/ | mediamtx:8889 | - | WebRTC + WS upgrade |
| /recordings/ | alias /recordings/ | - | Nginx serve direto |
| /hik_pro_connect | api:8000 | 120/min | Hikvision webhook |
| /intelbras_events | api:8000 | 120/min | Intelbras webhook |
| /camera_events | api:8000 | 120/min | Generico webhook |
| /health | api:8000 | - | Health check |

---

## 8. Seguranca

| Mecanismo | Implementacao |
|-----------|---------------|
| Auth usuarios | JWT HS256, access 15min, refresh 7d |
| Auth agents/plugins | API Key (bcrypt hash, prefix lookup) |
| Auth viewers | ViewerToken JWT 15min (camera_id + tenant_id) |
| Auth RTMP push | stream_key validado no publish-auth hook |
| Rate limiting | slowapi (app) + nginx (infra) |
| Webhooks saida | HMAC-SHA256 (X-VMS-Signature) |
| Headers HTTP | HSTS, X-Frame-Options, CSP, X-Content-Type |
| Tenant isolation | Filtro tenant_id obrigatorio em todas as queries |
| Passwords | bcrypt |
| ONVIF credentials | Armazenadas no banco |

---

## 9. Observabilidade

- Health check: `GET /health` (DB, Redis, RabbitMQ, MediaMTX, cameras online)
- Structured logging: structlog JSON em producao
- Metricas: `GET /metrics` (tenants, users, cameras, events, streams)
- MediaMTX metrics: `:9998` (Prometheus)
- ARQ: Redis-backed job tracking + DLQ

---

## 10. Path Convention (MediaMTX)

```
Pattern: tenant-{tenant_id}/cam-{camera_id}
Exemplo: tenant-550e8400/cam-f47ac10b

Stream:   rtsp://mediamtx:8554/tenant-550e8400/cam-f47ac10b
HLS:      /hls/tenant-550e8400/cam-f47ac10b/index.m3u8
WebRTC:   /webrtc/tenant-550e8400/cam-f47ac10b/whep
Gravacao: /recordings/tenant-550e8400/cam-f47ac10b/2026/04/12/14-30-00.mp4
```

Parse via regex: `tenant-(?P<tenant_id>[^/]+)/cam-(?P<camera_id>.+)`

---

## 11. Escalabilidade (200 cameras)

- 200 cameras x 60s segments = 200 writes/min (trivial para PostgreSQL)
- 200 streams RTSP simultaneos no MediaMTX (testado ate 300+)
- Analytics: 1fps x 200 = 200 frames/s (4 workers YOLO, ~50fps/worker)
- Redis: ALPR dedup TTL keys + SSE pub/sub — negligivel
- PostgreSQL: indices em (tenant_id, camera_id), (tenant_id, occurred_at)
- Horizontal: multiplos workers ARQ, multiplos uvicorn workers
