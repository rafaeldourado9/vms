# Arquitetura de Componentes

> Organização interna do código: bounded contexts, camadas, dependências e responsabilidades de cada módulo.

---

## 1. Mapa de Componentes por Camada

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                               │
│                                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ IAM      │ │ Cameras  │ │ Events   │ │Recordings│ │ Analytics    │  │
│  │ router   │ │ router   │ │ router   │ │ router   │ │ router       │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘  │
│       │            │            │            │               │          │
│  ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ ┌──────┴───────┐  │
│  │ IAM      │ │ Cameras  │ │ Events   │ │Recordings│ │ Notifications│  │
│  │ schemas  │ │ schemas  │ │ schemas  │ │ schemas  │ │ schemas      │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│                         APPLICATION LAYER                                │
│                                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ IAM      │ │ Camera   │ │ Event    │ │Recording │ │ Analytics    │  │
│  │ Service  │ │ Service  │ │ Service  │ │ Service  │ │ Service      │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘  │
│       │            │            │            │               │          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │              ARQ Tasks (background jobs)                         │   │
│  │  task_index_segment  │  task_dispatch_notification  │  reports   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│                          DOMAIN LAYER                                    │
│                                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ IAM      │ │ Camera   │ │VmsEvent  │ │Segment   │ │ Plugin       │  │
│  │ domain   │ │ domain   │ │ domain   │ │ domain   │ │ domain       │  │
│  │(Tenant,  │ │(Camera,  │ │(plate,   │ │(custody  │ │(installation,│  │
│  │ User,    │ │ Agent)   │ │ conf,    │ │ chain,   │ │ roi, event)  │  │
│  │ ApiKey)  │ │          │ │ payload) │ │ sha256)  │ │              │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│                       INFRASTRUCTURE LAYER                               │
│                                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │  IAM     │ │ Camera   │ │ Event    │ │Recording │ │ Notification │  │
│  │ Repo     │ │ Repo     │ │ Repo     │ │ Repo     │ │ Rule Repo    │  │
│  │(SQLAlch) │ │(SQLAlch) │ │(SQLAlch) │ │(SQLAlch) │ │ (SQLAlch)    │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │               Shared Infrastructure                              │   │
│  │  EventBus (Redis pubsub)  │  MediaMTXClient  │  OnvifClient      │   │
│  │  Settings (pydantic)      │  Encryption      │  JWT / ApiKey     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │               Messaging Infrastructure                           │   │
│  │  event_bus.py  │  event_handlers.py  │  dlq.py                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Bounded Contexts e Responsabilidades

### 2.1 IAM (Identity & Access Management)

```
api/src/vms/iam/
├── models.py        → TenantModel, UserModel, ApiKeyModel (SQLAlchemy)
├── domain.py        → Tenant, User, ApiKey (dataclasses puras)
├── repository.py    → TenantRepository, UserRepository, ApiKeyRepository
├── service.py       → IamService: criar tenant, user, auth, branding
├── schemas.py       → LoginRequest, TokenResponse, UserResponse, ...
└── router.py        → /auth/token, /auth/refresh, /users, /iam/branding
```

**Responsabilidades:**
- Autenticação (JWT): login, refresh, revogação
- Gerenciamento de tenants (multi-tenancy)
- Gerenciamento de usuários por tenant
- API keys para agents e integrações externas
- White-label branding por tenant

**Regras de negócio:**
- `role` enum: `admin | operator | viewer`
- `facial_recognition_enabled` default `False` — exige consent LGPD
- `onboarding_complete` controla exibição do wizard inicial

---

### 2.2 Cameras & Agents

```
api/src/vms/cameras/
├── models.py        → CameraModel, AgentModel
├── domain.py        → Camera, Agent
├── repository.py    → CameraRepository, AgentRepository
├── service.py       → CameraService (CRUD + MediaMTX + ONVIF)
├── mediamtx.py      → MediaMTXClient (HTTP adapter)
├── schemas.py       → CameraResponse, AgentResponse, StreamUrlsResponse
└── router.py        → /cameras, /agents, /agents/me/*
```

**Responsabilidades:**
- CRUD de câmeras com múltiplos protocolos (RTSP pull, RTMP push, ONVIF)
- Registro e gerenciamento de agents (edge devices)
- Configuração dinâmica de paths no MediaMTX
- Geração de URLs de streaming assinadas (JWT)
- Probe ONVIF: capabilities, perfis, PTZ
- WS-Discovery de câmeras na rede local

**Regras de negócio:**
- `rtmp_stream_key` é único globalmente (cross-tenant)
- `agent_id` é nullable — câmera pode ser gerenciada diretamente
- `onvif_password` e `isapi_password` são criptografados em repouso (Fernet)
- `delete_camera` é best-effort: ignora `MediaMTXError` e continua

---

### 2.3 Events

```
api/src/vms/events/
├── models.py            → VmsEventModel
├── domain.py            → VmsEvent, AlprDetection
├── repository.py        → EventRepository
├── service.py           → EventService (ingest + dedup + publish)
├── normalizers/
│   ├── hikvision.py     → HikvisionNormalizer
│   ├── intelbras.py     → IntelbrasNormalizer (JPEG binário Dahua ITC)
│   └── generic.py       → GenericNormalizer
└── router.py            → /webhooks/alpr, /events
```

**Responsabilidades:**
- Normalização de payloads ALPR de múltiplos fabricantes
- Deduplicação com Redis (dupla janela: exata 24h + deslizante 60s)
- Filtro de confiança mínima (0.80 padrão)
- Persistência de eventos e publicação no event bus

**Regra crítica do Intelbras ITSCAM:**
- Payload é JPEG binário com metadados Dahua ITC embutidos no header
- A placa e o serial são extraídos do binário, não de JSON

---

### 2.4 Recordings

```
api/src/vms/recordings/
├── models.py        → RecordingSegmentModel, ClipModel
├── domain.py        → RecordingSegment, Clip
├── repository.py    → RecordingSegmentRepository, ClipRepository
├── service.py       → RecordingService (index, VOD, custody chain)
├── tasks.py         → task_index_segment, task_cleanup_old_segments
├── schemas.py       → SegmentResponse, ClipResponse, TimelineHourResponse
└── router.py        → /recordings, /cameras/{id}/timeline, /recordings/clips
```

**Responsabilidades:**
- Indexação de segmentos MP4 do MediaMTX
- Geração de clips (ffmpeg stitch de segmentos)
- VOD via HLS remux (sem reencoding)
- Cadeia de custódia imutável (JSONB append-only)
- Verificação de integridade SHA-256
- Exportação forense com assinatura HMAC-SHA256
- Cleanup baseado em `retention_days` (LGPD)

**Timeline:**
- `GET /cameras/{id}/timeline?date=YYYY-MM-DD` retorna cobertura por hora (0–100%)
- Usado pela UI para mostrar onde há gravações disponíveis

---

### 2.5 Streaming

```
api/src/vms/streaming/
├── models.py        → StreamSessionModel
├── service.py       → StreamingService (track sessions)
└── schemas.py       → StreamSessionResponse
```

**Responsabilidades:**
- Rastreamento de sessões de streaming ativas
- Token verification para MediaMTX (endpoint interno)
- Métricas de bandwidth/uso por câmera

---

### 2.6 Analytics

```
api/src/vms/analytics/
├── models.py        → PluginInstallation, AnalyticsEvent, AnalyticsROI
├── service.py       → AnalyticsService (install, events, stats, rois)
└── router.py        → /analytics/catalog, /install, /events, /rois, /stats
```

```
analytics_service/           ← Serviço independente (contêiner separado)
├── core/
│   ├── plugin_base.py       → AnalyticsPlugin ABC
│   ├── orchestrator.py      → Orchestrator (frame capture + plugin dispatch)
│   └── shared_inference.py  → SharedInferenceEngine (YOLOv8 compartilhado)
└── plugins/
    ├── intrusion/plugin.py
    ├── people_count/plugin.py
    ├── vehicle_count/plugin.py
    ├── lpr/plugin.py
    ├── fire_smoke/plugin.py
    ├── ppe_detection/plugin.py
    ├── biker_detection/plugin.py
    ├── horse_cart/plugin.py
    └── face_recognition/plugin.py  ← stub (LGPD blocker)
```

**Inversão de dependência:**
- `analytics_service` nunca importa código do VMS Django/FastAPI
- Comunicação exclusiva via HTTP:
  - `GET /api/v1/analytics/rois` — busca zonas configuradas
  - `POST /api/v1/analytics/events` — envia resultados de detecção

---

### 2.7 Notifications

```
api/src/vms/notifications/
├── models.py        → NotificationRuleModel, NotificationLogModel
├── service.py       → NotificationService (rules + dispatch)
├── tasks.py         → task_dispatch_notification (ARQ)
└── router.py        → /notifications/rules, /notifications/logs
```

**Responsabilidades:**
- Regras de webhook configuráveis por tenant
- Pattern matching glob em event_type (`alpr.*`, `recording.*`)
- Assinatura HMAC-SHA256 em cada webhook saída
- Retry automático (até 3 tentativas) com backoff
- Log de cada tentativa com status HTTP e body

---

### 2.8 Audit

```
api/src/vms/audit/
├── models.py        → AuditLogModel (imutável, particionado por mês)
├── service.py       → AuditService (log_action, list_by_*)
└── repository.py    → AuditRepository
```

**Responsabilidades:**
- Log imutável de todas as ações do usuário
- Particionamento RANGE por `occurred_at` (mensal)
- Índices compostos: (tenant_id, occurred_at), (user_id), (action), (resource_type, resource_id)
- Usado para compliance, LGPD e forensics

---

### 2.9 Billing & Licensing

```
api/src/vms/billing/
├── models.py        → LicenseKeyModel, AnalyticsPricingModel, LicenseModel
└── router.py        → /billing/*
```

**Responsabilidades:**
- Ativação e validação de licenças por tenant
- Modelo de pricing por plugin (tier light/pro, preço por câmera/dia)
- Fingerprinting de hardware para self-hosted

---

### 2.10 Reports

```
api/src/vms/reports/
├── models.py           → ReportModel
├── service.py          → ReportService (generate, list)
├── tasks.py            → task_generate_report, task_auto_monthly_report
├── templates/
│   └── base.html       → Template HTML para PDF
└── router.py           → /reports
```

**Responsabilidades:**
- Geração de relatórios PDF on-demand e agendados
- Relatório automático mensal (cron: dia 1, 6h UTC)
- Tipos: ALPR, compliance, incident, monthly_summary
- SHA-256 do PDF gerado para auditoria

---

### 2.11 LGPD / Compliance

```
api/src/vms/lgpd/
├── models.py        → RetentionPolicyModel, ConsentRecordModel
└── service.py       → LgpdService (policies, consent)
```

**Responsabilidades:**
- Políticas de retenção por tipo de dado e por tenant
- Registros de consentimento (grant/revoke) com hash do texto de consent
- Controla `facial_recognition_enabled` no tenant (opt-in explícito)
- Base para o cleanup diário de dados expirados

---

## 3. Shared Kernel

```
api/src/vms/shared/
├── __init__.py      → Exportações compartilhadas
├── kernel.py        → Tipos base: TenantId, UserId, CameraId (type aliases)
└── exceptions.py    → Exceções do domínio:
                         NotFoundError, PermissionError,
                         UnsupportedManufacturerError,
                         MediaMTXError, DuplicateError
```

---

## 4. Infrastructure Shared

```
api/src/vms/infrastructure/
├── config/
│   └── settings.py          → Settings (pydantic-settings, env vars)
├── messaging/
│   ├── event_bus.py         → EventBus (Redis pubsub publish/subscribe)
│   ├── event_handlers.py    → Handlers: alpr.detected, camera.online, clip.ready
│   └── dlq.py               → Dead Letter Queue (Redis sorted set)
└── db/
    └── session.py           → AsyncSession factory, get_db dependency
```

---

## 5. Diagrama de Dependências entre Módulos

```
router.py
    │
    ▼
service.py  ──────────────────────────────────────────┐
    │                                                 │
    ├── repository.py (Port Protocol)                 │
    │       └── models.py (SQLAlchemy ORM)            │
    │               └── PostgreSQL                    │
    │                                                 │
    ├── infrastructure/messaging/event_bus.py         │
    │       └── Redis pubsub                          │
    │                                                 │
    ├── cameras/mediamtx.py (MediaMTXClient)          │
    │       └── MediaMTX HTTP API                     │
    │                                                 │
    ├── shared/exceptions.py                          │
    └── infrastructure/config/settings.py             │
                                                      │
tasks.py (ARQ) ────────────────────────────────────────┘
    │
    ├── service.py (same domain)
    └── infrastructure/db/session.py
```

**Regra:** módulos só podem importar para dentro (domain ← infra ← application ← presentation). Nunca cruzar bounded contexts diretamente — usar event bus ou service calls.

---

## 6. Componente: VMS Agent (Edge)

```
edge_agent/
├── main.py              → CLI entry point, graceful shutdown
├── config_poller.py     → GET /agents/me/config a cada 30s
├── stream_manager.py    → Gerencia processos ffmpeg por câmera
├── heartbeat.py         → POST /agents/me/heartbeat a cada 30s
└── ws_client.py         → WebSocket /agents/me/ws (config push imediato)

ffmpeg invocado com:
  ffmpeg -rtsp_transport tcp -i {rtsp_url} -c copy -f flv {rtmp_url}
  # -c copy: OBRIGATÓRIO. Sem reencoding. CPU explodiria com reencoding.
```

---

## 7. Componente: Analytics Service (Independente)

```
analytics_service/
├── main.py              → FastAPI app + Orchestrator startup
├── core/
│   ├── plugin_base.py   → ABC AnalyticsPlugin
│   ├── orchestrator.py  → Frame capture loop, plugin dispatch
│   └── shared_inference.py → SharedInferenceEngine (YOLOv8 singleton)
├── plugins/
│   └── {nome}/plugin.py → Implementação de cada plugin
└── models/
    └── *.pt             → Pesos YOLOv8 (montados via volume)
```

**Fluxo interno do Orchestrator:**
```
1. GET /api/v1/analytics/rois  → cache ROIs por câmera
2. Para cada câmera ativa:
   a. Abre stream RTSP (via RTSP token obtido da API)
   b. Captura frame @ fps_target (default: 1 FPS)
   c. SharedInferenceEngine.run(frame) → detections[]
   d. Para cada plugin instalado nessa câmera:
      - plugin.process_shared_frame(detections, frame, metadata, rois)
      - Filtra por ROI polygon (normalizado 0.0–1.0)
      - Retorna [AnalyticsResult] ou []
   e. POST /api/v1/analytics/events para cada resultado
3. Métricas: FPS real, latência por plugin, uso de GPU
```
