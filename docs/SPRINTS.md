# VMS MVP — Sprints & Checklist

> Deadline: Quinta-feira 2026-04-02
> Início: Segunda-feira 2026-03-30
> Metodologia: Sprint = bloco de 4–6h · Commit ao final de cada sprint concluído

---

## Sprint 0 — Estrutura & Documentação ✅ [2026-03-30]

- [x] Inicializar repositório git
- [x] Criar estrutura de pastas (bounded contexts)
- [x] `docs/ARCHITECTURE.md` — arquitetura hexagonal, modelos, fluxos
- [x] `docs/SPRINTS.md` — este arquivo
- [x] `docs/API.md` — contratos de API completos
- [x] `docs/PLUGINS.md` — guia de plugins analytics
- [x] `docs/DEPLOY.md` — checklist de produção
- [x] `docs/adr/` — Architecture Decision Records
- [x] `docker-compose.yml` — stack completa
- [x] `Makefile` — comandos dev
- [x] `.env.example` — todas as variáveis

---

## Sprint 1 — Foundation: Infra + IAM [2026-03-30]

### 1.1 Infraestrutura base

- [x] `api/pyproject.toml` — dependências, ruff, mypy
- [x] `api/Dockerfile` — imagem Python 3.12 slim
- [x] `api/src/vms/main.py` — FastAPI app factory, lifespan
- [x] `api/src/vms/core/config.py` — Pydantic Settings
- [x] `api/src/vms/core/database.py` — SQLAlchemy async engine + session
- [x] `api/src/vms/core/security.py` — JWT issue/verify, bcrypt helpers
- [x] `api/src/vms/core/exceptions.py` — exceções de domínio + handlers HTTP
- [x] `api/src/vms/core/pagination.py` — paginação cursor + offset
- [x] `api/src/vms/core/event_bus.py` — RabbitMQ publish (aio-pika)
- [x] `api/src/vms/core/deps.py` — FastAPI dependencies (get_db, get_current_user, etc.)
- [x] `api/migrations/env.py` + `alembic.ini`

### 1.2 IAM (Bounded Context)

- [x] `iam/domain.py` — entities: Tenant, User, ApiKey (dataclasses puros)
- [x] `iam/models.py` — SQLAlchemy ORM models
- [x] `iam/repository.py` — Protocol (port) + SQLAlchemyImpl
- [x] `iam/schemas.py` — Pydantic v2 DTOs (request/response)
- [x] `iam/service.py` — CreateTenant, CreateUser, Auth, IssueApiKey
- [x] `iam/router.py` — POST /auth/token, POST /auth/refresh, POST /tenants, POST /users
- [x] `migrations/versions/001_iam.py` — migration inicial (todas as tabelas)

### 1.3 Testes Sprint 1

- [x] `tests/unit/iam/test_domain.py` — 16 testes (entidades, hierarquia, enums)
- [x] `tests/unit/iam/test_service.py` — 19 testes (services com repos mockados)
- [x] `tests/integration/test_auth.py` — 10 testes (login, refresh, /me, erros)
- [x] `tests/bdd/features/auth.feature` + steps — 6 cenários BDD
- [x] 51 testes total Sprint 1 — todos passando

**Critério de aceite:** `make test` verde, `make lint` verde, migrate roda sem erro

---

## Sprint 2 — Cameras & Agents [2026-03-31]

### 2.1 Cameras (Bounded Context)

- [x] `cameras/domain.py` — Camera, Agent entities
- [x] `cameras/models.py` — ORM models
- [x] `cameras/repository.py` — Protocol + SQLAlchemy impl
- [x] `cameras/schemas.py` — DTOs
- [x] `cameras/service.py` — CRUD cameras, CRUD agents, heartbeat, config
- [x] `cameras/mediamtx.py` — MediaMTX API client (add/remove path)
- [x] `cameras/router.py` — CRUD /cameras, CRUD /agents, /agents/me/config, /agents/me/heartbeat
- [x] `migrations/versions/001_initial_schema.py` — todas as tabelas incluídas

### 2.2 Testes Sprint 2

- [x] `tests/unit/cameras/test_domain.py` — 10 testes
- [x] `tests/unit/cameras/test_service.py` — 11 testes
- [x] `tests/integration/test_cameras.py` — 5 testes CRUD completo
- [x] `tests/integration/test_agents.py` — 5 testes config, heartbeat, API key
- [x] `tests/bdd/features/cameras.feature` + steps — 5 cenários BDD
- [x] `tests/bdd/features/agents.feature` + steps — 5 cenários BDD

**Critério de aceite:** Agent consegue fazer GET config e POST heartbeat; câmera aparece no MediaMTX

---

## Sprint 3 — Streaming & Recordings [2026-03-31]

### 3.1 Streaming (Bounded Context)

- [x] `streaming/domain.py` — StreamSession
- [x] `streaming/models.py`
- [x] `streaming/service.py` — on_stream_ready, on_stream_stopped, verify_publish_token
- [x] `streaming/router.py` — POST /streaming/publish-auth (webhooks MediaMTX em events/router)
- [x] `migrations/versions/002_stream_sessions.py`

### 3.2 Recordings (Bounded Context)

- [x] `recordings/domain.py` — RecordingSegment, Clip
- [x] `recordings/models.py`
- [x] `recordings/repository.py`
- [x] `recordings/service.py` — index_segment, create_clip, cleanup_expired
- [x] `recordings/schemas.py`
- [x] `recordings/router.py` — GET /recordings, POST /recordings/clips
- [x] `recordings/tasks.py` — ARQ tasks: index_segment, cleanup_segments
- [x] `migrations/versions/001_initial_schema.py` — tabelas incluídas

### 3.3 Testes Sprint 3

- [x] `tests/unit/streaming/test_service.py` — 4 testes webhooks MediaMTX
- [x] `tests/unit/streaming/test_streaming_service.py` — 10 testes StreamingService
- [x] `tests/unit/recordings/test_service.py` — 7 testes RecordingService
- [x] `tests/integration/test_mediamtx_hooks.py` — 6 testes publish-auth + webhooks
- [x] `tests/integration/test_recordings.py` — 5 testes segments + clips
- [x] `tests/bdd/features/recording.feature` + steps — 3 cenários BDD

**Critério de aceite:** MediaMTX segment_ready → RecordingSegment criado; cleanup deleta segmentos expirados

---

## Sprint 4 — Events & ALPR [2026-04-01]

### 4.1 Events (Bounded Context)

- [x] `events/domain.py` — VmsEvent, AlprDetection
- [x] `events/models.py`
- [x] `events/repository.py`
- [x] `events/service.py` — ingest_alpr (com dedup Redis), create_event, list_events
- [x] `events/schemas.py`
- [x] `events/router.py` — POST /webhooks/alpr, POST /webhooks/alpr/{manufacturer}, GET /events
- [x] `events/normalizers/base.py` — Protocol NormalizerPort
- [x] `events/normalizers/hikvision.py` — Hikvision ANPR payload
- [x] `events/normalizers/intelbras.py` — Intelbras ITSCAM payload
- [x] `events/normalizers/generic.py` — fallback genérico
- [x] `migrations/versions/005_events.py`

### 4.2 Testes Sprint 4

- [x] `tests/unit/events/test_normalizers.py` — 21 testes (3 fabricantes + registry + fallback + inválido)
- [x] `tests/unit/events/test_dedup.py` — 7 testes (Redis dedup lógica)
- [x] `tests/unit/events/test_service.py` — 4 testes (list/get)
- [x] `tests/integration/test_alpr_webhook.py` — 7 testes (webhook, dedup, vendor, events API)
- [x] `tests/bdd/features/alpr.feature` + steps — 3 cenários BDD (Fluxo A)

**Critério de aceite:** POST /webhooks/alpr/hikvision → VmsEvent criado; segundo POST mesmo plate < 60s → ignorado

---

## Sprint 5 — Notifications & Event Bus [2026-04-01]

### 5.1 Notifications (Bounded Context)

- [x] `notifications/domain.py` — NotificationRule, NotificationLog
- [x] `notifications/models.py`
- [x] `notifications/repository.py`
- [x] `notifications/service.py` — evaluate_rules, dispatch_webhook (HMAC-SHA256)
- [x] `notifications/schemas.py`
- [x] `notifications/router.py` — CRUD /notifications/rules, GET /notifications/logs
- [x] `notifications/dispatcher.py` — httpx async dispatch + retry
- [x] `notifications/tasks.py` — ARQ task: dispatch_webhook
- [x] `migrations/versions/006_notifications.py`

### 5.2 Event Bus Integration

- [x] `core/event_bus.py` — publish_event completo (aio-pika)
- [x] Consumers em ARQ workers para cada evento (via evaluate_and_dispatch)
- [x] Integrar publish em services (camera.online, alpr.detected, etc.)

### 5.3 SSE (Server-Sent Events)

- [x] `sse/router.py` — GET /api/v1/sse → Redis pub/sub (filtrado por tenant JWT)
- [x] `sse/router.py:publish_sse_event()` — helper para publicar no Redis

### 5.4 Health check

- [x] `health/router.py` — GET /health (DB + Redis + RabbitMQ)

### 5.5 Testes Sprint 5

- [x] `tests/unit/notifications/test_service.py` — 9 testes (CRUD + evaluate_and_dispatch)
- [x] `tests/unit/notifications/test_dispatcher.py` — 5 testes (HMAC, success, failure, error)
- [x] `tests/integration/test_notifications.py` — 6 testes CRUD regras
- [x] `tests/bdd/features/notifications.feature` + steps — 3 cenários BDD
- [x] `tests/integration/test_e2e_alpr_to_notification.py` — E2E: ALPR → Event → Notification

**Critério de aceite:** ALPR event → regra match → webhook disparado com X-VMS-Signature correto

---

## Sprint 6 — Edge Agent [2026-04-01]

### 6.1 Edge Agent (serviço separado)

- [ ] `edge_agent/pyproject.toml`
- [ ] `edge_agent/Dockerfile`
- [ ] `edge_agent/src/agent/config.py` — env vars
- [ ] `edge_agent/src/agent/cloud_client.py` — HTTP client (poll config, heartbeat)
- [ ] `edge_agent/src/agent/stream_manager.py` — ffmpeg subprocess management
- [ ] `edge_agent/src/agent/health_checker.py` — process monitor + restart
- [ ] `edge_agent/src/agent/main.py` — event loop principal
- [ ] Agent Dockerfile separado

### 6.2 Testes Sprint 6

- [ ] `edge_agent/tests/test_stream_manager.py` — start/stop/restart streams
- [ ] `edge_agent/tests/test_cloud_client.py` — config poll, heartbeat
- [ ] `tests/bdd/features/edge_agent.feature` + steps

**Critério de aceite:** Agent sobe, faz heartbeat, inicia ffmpeg para cada câmera ativa

---

## Sprint 7 — Analytics Service [2026-04-02]

### 7.1 Framework de Plugins

- [ ] `analytics/src/analytics/core/plugin_base.py` — AnalyticsPlugin ABC
- [ ] `analytics/src/analytics/core/yolo_base.py` — YOLOPlugin base
- [ ] `analytics/src/analytics/core/orchestrator.py` — frame capture + plugin routing
- [ ] `analytics/src/analytics/core/frame_source.py` — OpenCV RTSP reader (1fps)
- [ ] `analytics/src/analytics/core/vms_client.py` — HTTP client para VMS API
- [ ] `analytics/src/analytics/core/config.py` — settings
- [ ] `analytics/src/analytics/main.py` — FastAPI app + lifespan

### 7.2 Plugins Core

- [ ] `analytics/src/analytics/plugins/intrusion/plugin.py` — YOLOv8n + polígono
- [ ] `analytics/src/analytics/plugins/people_count/plugin.py` — YOLOv8n count
- [ ] `analytics/src/analytics/plugins/vehicle_count/plugin.py` — YOLOv8n classes car/truck/moto
- [ ] `analytics/src/analytics/plugins/lpr/plugin.py` — YOLOv8 detect + fast-plate-ocr

### 7.3 API interna (analytics_service)

- [ ] `POST /internal/analytics/ingest/` — recebe resultado do plugin
- [ ] `GET /internal/cameras/{id}/rois/` — ROIs ativas por câmera
- [ ] `GET /health` — status dos plugins carregados

### 7.4 ROI Management no VMS API

- [ ] `analytics_config/domain.py` — RegionOfInterest
- [ ] `analytics_config/models.py`
- [ ] `analytics_config/service.py` — CRUD ROIs
- [ ] `analytics_config/router.py` — GET/POST/PATCH/DELETE /analytics/rois

### 7.5 Testes Sprint 7

- [ ] `analytics/tests/unit/test_intrusion_plugin.py`
- [ ] `analytics/tests/unit/test_people_count_plugin.py`
- [ ] `analytics/tests/unit/test_lpr_plugin.py`
- [ ] `analytics/tests/integration/test_analytics_api.py`
- [ ] `tests/bdd/features/analytics.feature` + steps

**Critério de aceite:** Frame sintético com pessoas → people_count emite evento; LPR detecta placa em imagem de teste

---

## Sprint 8 — Segurança, Observabilidade & Polish [2026-04-02]

- [ ] Rate limiting `slowapi` em webhooks + auth endpoints
- [ ] Security headers no Nginx (HSTS, CSP, X-Frame-Options)
- [ ] Structured logging com `structlog` (JSON em prod)
- [ ] Métricas endpoint `/metrics` (contadores básicos)
- [ ] Backup script `infra/scripts/backup_db.sh`
- [ ] `make test-cov` → coverage > 80% em todos os contextos
- [ ] Documentação OpenAPI gerada automaticamente verificada
- [ ] `docker compose up` completo funciona sem erros
- [ ] Smoke test E2E: câmera criada → agent heartbeat → stream → recording segment

**Critério de aceite final:**
- `make test` → todos os testes passam
- `make lint` → zero erros
- `docker compose up` → todos os serviços healthy
- Coverage > 80% global

---

## Progresso Geral

```
Sprint 0  ████████████  ✅ Estrutura + Docs
Sprint 1  ████████████  ✅ IAM + Foundation (51 testes)
Sprint 2  ████████████  ✅ Cameras + Agents (41 testes + 10 BDD)
Sprint 3  ████████████  ✅ Streaming + Recordings (35 testes + 3 BDD)
Sprint 4  ████████████  ✅ Events + ALPR (42 testes + 3 BDD)
Sprint 5  ████████████  ✅ Notifications + Event Bus + SSE + Health (24 testes + 3 BDD + E2E)
Sprint 6  ░░░░░░░░░░░░  🔲 Edge Agent
Sprint 7  ░░░░░░░░░░░░  🔲 Analytics Service
Sprint 8  ░░░░░░░░░░░░  🔲 Security + Polish
```

---

## Convenções

### Commits
```
tipo(contexto): descrição em português

feat(iam): adicionar autenticação JWT com refresh token
fix(alpr): corrigir dedup quando TTL expira antes do segundo evento
test(cameras): cobrir edge case câmera sem agent
docs(api): documentar endpoint de config do agent
```

### Testes

```bash
make test          # todos os testes (exceto e2e)
make test-unit     # apenas unit
make test-bdd      # apenas BDD
make test-cov      # com coverage report
make test-e2e      # requer docker compose up
```

### Qualidade de Código

- Funções < 20 linhas
- Complexidade ciclomática < 5 por função
- Type hints em tudo
- Docstrings em funções públicas (pt-br)
- Zero `print()` (usar `structlog`)
- Zero credenciais hardcoded
- Filtro `tenant_id` obrigatório em queries
