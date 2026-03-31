# VMS MVP — Arquitetura

> Versão: 1.0 · Data: 2026-03-30
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
│  │ ApiKey   │  │          │  │                    │ │
│  └──────────┘  └──────────┘  └────────────────────┘ │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │Recordings│  │  Events  │  │   Notifications    │ │
│  │          │  │  (ALPR)  │  │                    │ │
│  │ Segment  │  │ VmsEvent │  │  Rule → Dispatch   │ │
│  │ Clip     │  │ Dedup    │  │  HMAC-signed       │ │
│  └──────────┘  └──────────┘  └────────────────────┘ │
└─────────────────────────────────────────────────────┘

┌────────────────────────────┐   ┌──────────────────────────┐
│    Analytics Service       │   │       Edge Agent         │
│                            │   │                          │
│  Plugin framework          │   │  Config poll (30s)       │
│  intrusion_detection       │   │  ffmpeg -c copy          │
│  people_count              │   │  RTSP→RTMP push          │
│  vehicle_count             │   │  Heartbeat               │
│  lpr (plate recognition)   │   │  Graceful shutdown       │
└────────────────────────────┘   └──────────────────────────┘
```

---

## 4. Modelo de Dados

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
├── agent_id (FK?, nullable)
├── name (str)
├── location (str?)
├── rtsp_url (str)
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
├── event_type (str)        ← "alpr.detected", "camera.online", ...
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
├── event_type_pattern (str)   ← fnmatch, e.g. "alpr.*"
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

---

## 5. Dois Fluxos ALPR

### Fluxo A — Câmera inteligente (push)
```
Câmera com ANPR → HTTP webhook → POST /webhooks/alpr/{manufacturer}
                                        ↓
                               Normalizer (Hikvision/Intelbras/Generic)
                                        ↓
                               AlprService.ingest()
                                        ↓
                               Redis dedup (SET NX, TTL 60s)
                                        ↓
                               VmsEvent.create() → publish "alpr.detected"
```

### Fluxo B — Câmera burra (analytics server-side)
```
Câmera RTSP → MediaMTX → analytics_service (frame capture, 1fps)
                                   ↓
                          LPR Plugin (YOLOv8 + fast-plate-ocr)
                                   ↓
                          POST /internal/analytics/ingest/
                                   ↓
                          AlprService.ingest() → VmsEvent.create()
```

---

## 6. Fluxo de Gravação 24/7

```
Câmera → [Agent ffmpeg] → MediaMTX → auto-record (60s segments)
                                         ↓ (on_segment_ready webhook)
                                  POST /webhooks/mediamtx/segment
                                         ↓
                                  ARQ task: index_segment()
                                         ↓
                                  RecordingSegment.create()
                                         ↓
                                  Retention check (delete old segments)
```

---

## 7. Stack de Tecnologia

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
Message Bus   | RabbitMQ (aio-pika)    | Topic exchange para event routing
Streaming     | MediaMTX               | RTSP/RTMP/HLS/WebRTC + auto-record
Proxy         | Nginx                  | TLS termination, segurança
Linting       | ruff + mypy            | Fast + type safety
Testes        | pytest-asyncio + BDD   | Async-first, BDD para features
```

---

## 8. Segurança

- JWT HS256, expiração 15min (access) / 7 dias (refresh)
- API Keys: prefix para lookup + bcrypt hash (plain key gerada só uma vez)
- Rate limiting via `slowapi` (100/min webhooks, 60/min API)
- HMAC-SHA256 em webhooks de saída (`X-VMS-Signature`)
- HSTS, X-Frame-Options, CSP, X-Content-Type no Nginx
- Tenant isolation obrigatório em todas as queries

---

## 9. Observabilidade

- Structured logging (structlog, JSON em prod)
- `/health` endpoint (DB + Redis + RabbitMQ status)
- Métricas básicas: câmeras online, eventos por hora
- ARQ dashboard (opcional em dev)

---

## 10. Escalabilidade (200 câmeras)

- 200 câmeras × 60s segments = 200 writes/min no banco (trivial)
- 200 streams RTSP simultâneos no MediaMTX (testado até 300+)
- Analytics: 1fps × 200 câmeras = 200 frames/s (4 workers YOLO, ~50fps/worker)
- Redis: ALPR dedup TTL keys — negligível
- PostgreSQL: índices em `(tenant_id, camera_id)`, `(tenant_id, occurred_at)`
- Horizontal: múltiplos workers ARQ, múltiplos uvicorn workers
