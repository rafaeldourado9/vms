# VMS MVP — Arquitetura

> Versão: 1.1 · Data: 2026-03-31
> Stack: FastAPI · SQLAlchemy 2 async · PostgreSQL 16 · Redis 7 · RabbitMQ 3 · MediaMTX

---

## 1. Visão Geral

VMS (Video Management System) white-label multi-tenant para integradores de segurança.
Suporte a até 200 câmeras por instância. Gravação 24/7. Streaming ao vivo.
Analíticos server-side para câmeras sem IA embarcada.

### Diferenciais competitivos

| Eixo | Vantagem |
|------|----------|
| Câmeras baratas → inteligentes | YOLOv8 server-side transforma qualquer câmera bullet |
| Self-hosted / dados do cliente | Zero dependência de cloud externa — compliance LGPD nativo |
| Sem licença por câmera | Modelo por tenant/instância — TCO 80% menor que Camerite/Monuvo |
| Multi-protocolo | RTSP pull, RTMP push, ONVIF — qualquer câmera do mercado BR |

---

## 2. Arquitetura Hexagonal (Ports & Adapters)

```
┌─────────────────────────────────────────────────────────────┐
│  Driving Adapters (HTTP)          Domain          Driven Adapters        │
│                                                              │
│  ┌──────────────┐   command/query   ┌─────────────┐         │
│  │  FastAPI     │ ────────────────► │  Application │         │
│  │  Routers     │                   │  Services   │         │
│  └──────────────┘   ◄─── result ─── └──────┬──────┘         │
│                                            │ port call       │
│                                    ┌───────┴──────┐         │
│                                    │  Repository  │         │
│                                    │  (abstract)  │         │
│                                    └───────┬──────┘         │
│                                            │ implement       │
│                          ┌─────────────────┼──────────────┐ │
│                          │   SQLAlchemy    │  Redis       │ │
│                          │   asyncpg       │  aio-pika    │ │
│                          └─────────────────┴──────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Regras invioláveis

1. **Domain** não importa nada externo (SQLAlchemy, Redis, FastAPI)
2. **Ports** são interfaces (`Protocol` ou ABC) — sem implementação
3. **Application Services** orquestram domain + ports — sem HTTP, sem SQL direto
4. **Adapters** implementam ports e conhecem frameworks externos
5. Toda query filtra por `tenant_id` — sem exceção

---

## 3. Bounded Contexts

```
┌─────────────────────────────────────────────────────┐
│                      API Service                     │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │   IAM    │  │ Cameras  │  │     Streaming      │ │
│  │          │  │          │  │  (MediaMTX hooks)  │ │
│  │ Tenant   │  │ Camera   │  │                    │ │
│  │ User     │  │ Agent    │  │  StreamSession     │ │
│  │ ApiKey   │  │          │  │  ViewerToken       │ │
│  └──────────┘  └──────────┘  └────────────────────┘ │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │Recordings│  │  Events  │  │   Notifications    │ │
│  │          │  │  (ALPR)  │  │                    │ │
│  │ Segment  │  │ VmsEvent │  │  Rule → Dispatch   │ │
│  │ Clip     │  │ Dedup    │  │  HMAC-signed       │ │
│  └──────────┘  └──────────┘  └────────────────────┘ │
│                                                      │
│  ┌──────────┐  ┌──────────┐                         │
│  │Analytics │  │   SSE    │                         │
│  │  Config  │  │  Events  │                         │
│  │   ROIs   │  │ realtime │                         │
│  └──────────┘  └──────────┘                         │
└─────────────────────────────────────────────────────┘

┌────────────────────────────┐   ┌──────────────────────────┐
│    Analytics Service       │   │       Edge Agent         │
│                            │   │                          │
│  Plugin framework          │   │  Config poll (30s)       │
│  intrusion_detection       │   │  ffmpeg -c copy          │
│  people_count              │   │  RTSP pull → RTMP push   │
│  vehicle_count             │   │  Heartbeat               │
│  lpr (plate recognition)   │   │  Graceful shutdown       │
└────────────────────────────┘   └──────────────────────────┘
```

---

## 4. Protocolos de Câmera

O VMS suporta três modos de ingestão de vídeo. A escolha depende do hardware disponível.

### 4.1 RTSP pull via Agent (padrão)

```
Câmera IP (rede local)
  │  RTSP pull
  ▼
Edge Agent (ffmpeg -c copy)      ← roda na rede do cliente
  │  RTMP push
  ▼
MediaMTX :1935                   ← roda no VMS (cloud ou on-prem)
  │
  ├── HLS  :8888   → viewer browser
  ├── WebRTC :8889 → viewer baixa latência
  └── Record /recordings/...
```

**Quando usar:** câmeras IP comuns (Hikvision, Intelbras, Dahua, genéricas) que não têm RTMP nativo. Requer um servidor com Docker na rede local do cliente.

**Configuração no VMS:**
- `stream_protocol = rtsp_pull`
- `rtsp_url = rtsp://user:pass@192.168.1.100:554/stream`
- `agent_id = <uuid do agent na rede local>`

---

### 4.2 RTMP push direto (sem Agent)

```
Câmera com RTMP nativo           ← Reolink, algumas Intelbras
  │  RTMP push  (stream_key no query param)
  ▼
MediaMTX :1935
  │  publish-auth hook
  ▼
VMS API: POST /streaming/publish-auth
  │  valida stream_key contra banco
  └── aceita ou rejeita
```

**Quando usar:** câmeras que suportam RTMP push nativamente (alguns modelos Reolink, Intelbras). Não requer Agent na rede local.

**Configuração no VMS:**
- `stream_protocol = rtmp_push`
- `rtmp_stream_key` gerado automaticamente na criação da câmera
- Operador configura na câmera: `rtmp://vms.host:1935/tenant-{id}/cam-{id}?key={stream_key}`

**Auth flow:**
```
MediaMTX → POST /streaming/publish-auth
  body: { action: "publish", path: "tenant-1/cam-42", query: "key=abc123" }
  ↓
VMS: SELECT camera WHERE rtmp_stream_key = "abc123" AND mediamtx_path MATCHES path
  ↓
200 OK (aceito) ou 401 (rejeitado)
```

---

### 4.3 ONVIF (descoberta automática)

```
Câmera ONVIF (rede local)        ← Hikvision, Intelbras, Dahua, Axis, Bosch
  │  ONVIF WS-Discovery / GetStreamUri
  ▼
VMS API: POST /cameras/onvif-probe
  │  GetCapabilities → GetStreamUri → extrai rtsp_url
  └── cria câmera com stream_protocol=onvif, rtsp_url preenchido

  ↓  (após criação, flui como RTSP pull via Agent)

Edge Agent → MediaMTX
```

**Quando usar:** câmeras compatíveis com ONVIF Profile S. Elimina necessidade de saber a URL RTSP manualmente. Suporta autodiscovery na subnet.

**Adicionalmente via ONVIF:**
- Snapshot: `GetSnapshotUri` → imagem JPEG sem precisar decodificar stream
- PTZ (pós-MVP): `PTZ.ContinuousMove`, `GotoPreset`

---

### 4.4 Streaming para Viewers (saída)

```
Browser / App
  │  GET /cameras/{id}/stream  (JWT)
  ▼
VMS API: gera ViewerToken (JWT 15min, camera_id + tenant_id)
  │
  ├── HLS URL:    http://vms/hls/tenant-1/cam-42/index.m3u8?token=<jwt>
  └── WebRTC URL: http://vms/webrtc/tenant-1/cam-42/whep?token=<jwt>

Browser → MediaMTX HLS/WebRTC
  │  read-auth hook com token
  ▼
VMS API: POST /streaming/read-auth
  │  verifica ViewerToken JWT
  └── 200 (permitido) ou 401 (negado)
```

**P2P / NAT traversal:**
- Viewers WebRTC usam ICE com STUN público (`stun.l.google.com:19302`)
- Para redes com NAT simétrico: configurar servidor TURN (coturn) via `.env`
- Agent → MediaMTX: RTMP push — saída de rede, sem problema de NAT

---

## 5. Modelo de Dados

### IAM

```
Tenant
├── id (uuid)
├── name (str)
├── slug (str, unique)
├── is_active (bool)
├── facial_recognition_enabled (bool, default=False)  ← LGPD
├── facial_recognition_consent_at (datetime?)
└── created_at (datetime)

User
├── id (uuid)
├── tenant_id (FK)
├── email (str, unique per tenant)
├── hashed_password (str)
├── full_name (str)
├── role (enum: admin, operator, viewer)
├── is_active (bool)
└── created_at (datetime)

ApiKey
├── id (uuid)
├── tenant_id (FK)
├── owner_type (enum: agent, analytics, webhook)
├── owner_id (uuid)         ← FK to Agent or service
├── key_hash (str)          ← bcrypt hash, never stored plain
├── prefix (str)            ← first 8 chars for lookup (e.g. "vms_1234")
├── is_active (bool)
└── last_used_at (datetime?)
```

### Cameras

```
Camera
├── id (uuid)
├── tenant_id (FK)
├── agent_id (FK?, nullable)         ← null para rtmp_push
├── name (str)
├── location (str?)
├── stream_protocol (enum: rtsp_pull, rtmp_push, onvif)
├── rtsp_url (str?)                  ← preenchido para rtsp_pull e onvif
├── rtmp_stream_key (str?)           ← preenchido para rtmp_push (hash stored)
├── onvif_url (str?)                 ← http://192.168.1.100:80/onvif/device_service
├── onvif_username (str?)
├── onvif_password (str?)            ← encrypted at rest
├── manufacturer (enum: hikvision, intelbras, dahua, generic)
├── retention_days (int, default=7)
├── is_active (bool)
├── is_online (bool, default=False)
├── last_seen_at (datetime?)
└── created_at (datetime)

Agent
├── id (uuid)
├── tenant_id (FK)
├── name (str)
├── status (enum: pending, online, offline)
├── last_heartbeat_at (datetime?)
├── version (str?)
├── streams_running (int, default=0)
├── streams_failed (int, default=0)
└── created_at (datetime)
```

### Streaming & Recordings

```
StreamSession
├── id (uuid)
├── tenant_id (FK)
├── camera_id (FK)
├── mediamtx_path (str)     ← "tenant-{id}/cam-{id}"
├── started_at (datetime)
└── ended_at (datetime?)

RecordingSegment
├── id (uuid)
├── tenant_id (FK)
├── camera_id (FK)
├── mediamtx_path (str)
├── file_path (str)
├── started_at (datetime)
├── ended_at (datetime)
├── duration_seconds (float)
└── size_bytes (int)

Clip
├── id (uuid)
├── tenant_id (FK)
├── camera_id (FK)
├── vms_event_id (FK?, nullable)
├── file_path (str?)
├── status (enum: pending, processing, ready, failed)
├── starts_at (datetime)
├── ends_at (datetime)
└── created_at (datetime)
```

### Events

```
VmsEvent
├── id (uuid)
├── tenant_id (FK)
├── camera_id (FK?)
├── event_type (str)        ← "alpr.detected", "camera.online", "analytics.intrusion.detected"...
├── plate (str?)            ← ALPR specific
├── confidence (float?)
├── payload (json)
└── occurred_at (datetime)
```

### Notifications

```
NotificationRule
├── id (uuid)
├── tenant_id (FK)
├── name (str)
├── event_type_pattern (str)   ← fnmatch, e.g. "alpr.*", "analytics.intrusion.*"
├── destination_url (str)
├── webhook_secret (str)       ← HMAC-SHA256 signing key
├── is_active (bool)
└── created_at (datetime)

NotificationLog
├── id (uuid)
├── tenant_id (FK)
├── rule_id (FK)
├── vms_event_id (FK)
├── status (enum: success, failed)
├── response_code (int?)
├── response_body (str?)
├── attempt (int, default=1)
└── dispatched_at (datetime)
```

### Analytics Config

```
RegionOfInterest (ROI)
├── id (uuid)
├── tenant_id (FK)
├── camera_id (FK)
├── name (str)
├── ia_type (str)              ← "intrusion", "human_traffic", "vehicle_traffic", "lpr"
├── polygon_points (json)      ← [[x, y], ...] normalizado 0.0–1.0
├── config (json)              ← configuração específica do plugin
├── is_active (bool)
└── created_at (datetime)
```

---

## 6. Três Fluxos ALPR

### Fluxo A — Câmera inteligente (push de evento)
```
Câmera com módulo ANPR (Hikvision ANPR, Intelbras ITSCAM)
  │  HTTP webhook com payload do fabricante
  ▼
POST /webhooks/alpr/{manufacturer}
  │
  ▼
Normalizer (Hikvision / Intelbras / Generic)
  │
  ▼
EventService.ingest_alpr()
  │
  ▼
Redis dedup: SET alpr:dedup:{camera}:{plate} NX EX 60
  │ (se duplicata → ignorar)
  ▼
VmsEvent.create() → publish "alpr.detected" → SSE + Notifications
```

### Fluxo B — Analytics server-side (câmera burra)
```
Câmera RTSP (qualquer) → MediaMTX
  │  frame capture 1fps
  ▼
Analytics Service (plugin lpr)
  │  YOLOv8 detect + fast-plate-ocr
  ▼
POST /internal/analytics/ingest/
  │
  ▼
EventService.ingest_alpr() → (mesmo fluxo acima a partir de dedup)
```

### Fluxo C — Câmera RTMP push com LPR nativo (futuro)
```
Câmera com RTMP + ANPR nativo
  │  RTMP push (stream) + HTTP webhook (evento ALPR)
  ▼
MediaMTX (stream) + POST /webhooks/alpr (evento)  ← paralelos
```

---

## 7. Fluxo de Gravação 24/7

```
Câmera → [Agent ffmpeg -c copy] → MediaMTX
                                     │  auto-record (60s fmp4 segments)
                                     │  /recordings/{path}/{date}/{time}.mp4
                                     │
                                     ▼ (runOnRecordSegmentComplete hook)
                           POST /webhooks/mediamtx/segment_ready
                                     │
                                     ▼
                           ARQ task: index_segment()
                                     │
                                     ▼
                           RecordingSegment.create()
                                     │
                                     ▼
                           Retention check → delete segments > retention_days
```

---

## 8. Stack de Tecnologia

```
Serviço       | Tech                    | Razão
──────────────┼─────────────────────────┼───────────────────────────────────
API           | FastAPI + Uvicorn       | Async, tipagem nativa, OpenAPI auto
ORM           | SQLAlchemy 2.0 async    | Async-native, sem Django overhead
Migrations    | Alembic                 | Padrão com SQLAlchemy
Auth JWT      | python-jose             | Padrão de mercado
Auth API Key  | Custom (bcrypt hash)    | Simples para machine-to-machine
Background    | ARQ                     | Async-native, Redis-backed, simples
Cache/PubSub  | Redis 7                 | ALPR dedup + SSE + task queue
Message Bus   | RabbitMQ (aio-pika)     | Topic exchange para event routing
Streaming     | MediaMTX                | RTSP/RTMP/HLS/WebRTC + auto-record
Proxy         | Nginx                   | TLS termination, segurança
Analytics     | FastAPI + YOLOv8        | Serviço independente, plugins
Agent         | Python + ffmpeg         | Roda na rede do cliente
Linting       | ruff + mypy             | Fast + type safety
Testes        | pytest-asyncio + BDD    | Async-first, BDD para features
Frontend      | React 18 + Vite + TW    | SPA dark-mode, HLS.js, Recharts
```

---

## 9. Segurança

- JWT HS256, expiração 15min (access) / 7 dias (refresh)
- API Keys: prefix para lookup + bcrypt hash (plain key gerada só uma vez)
- ViewerToken: JWT 15min com claims `camera_id` + `tenant_id` — validado pelo MediaMTX read-auth hook
- RTMP stream key: token aleatório por câmera, validado no publish-auth hook
- Rate limiting via `slowapi` (100/min webhooks, 60/min API)
- HMAC-SHA256 em webhooks de saída (`X-VMS-Signature`)
- HSTS, X-Frame-Options, CSP, X-Content-Type no Nginx
- Tenant isolation obrigatório em todas as queries
- ONVIF credentials: armazenadas encrypted at rest (campo `onvif_password`)

---

## 10. Observabilidade

- Structured logging (structlog, JSON em prod)
- `/health` endpoint (DB + Redis + RabbitMQ + MediaMTX status)
- Métricas básicas: câmeras online, eventos por hora
- ARQ dashboard (opcional em dev)

---

## 11. Escalabilidade (200 câmeras)

- 200 câmeras × 60s segments = 200 writes/min no banco (trivial)
- 200 streams RTSP simultâneos no MediaMTX (testado até 300+)
- Analytics: 1fps × 200 câmeras = 200 frames/s (4 workers YOLO, ~50fps/worker)
- Redis: ALPR dedup TTL keys — negligível
- PostgreSQL: índices em `(tenant_id, camera_id)`, `(tenant_id, occurred_at)`
- Horizontal: múltiplos workers ARQ, múltiplos uvicorn workers

---

## 12. Path Convention (MediaMTX)

Todos os streams seguem o padrão:

```
tenant-{tenant_id}/cam-{camera_id}
```

Exemplos:
- `tenant-550e8400/cam-f47ac10b`  → stream live
- Arquivo: `/recordings/tenant-550e8400/cam-f47ac10b/2026/03/31/14-30-00.mp4`

O `cameras/service.py` e `streaming/service.py` extraem `tenant_id` e `camera_id` do path via regex `tenant-(?P<tenant_id>[^/]+)/cam-(?P<camera_id>.+)` — sem endpoint extra no banco.
