# VMS MVP — Sprints & Checklist

> Deadline: Quinta-feira 2026-04-02
> Início: Segunda-feira 2026-03-30
> Metodologia: Sprint = bloco de 4–6h · Commit ao final de cada sprint concluído

---

## Sprint 0 — Estrutura & Documentação ✅ [2026-03-31]

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
- [x] `infra/mediamtx/mediamtx.yml` — config completa: RTSP + RTMP + HLS + WebRTC + hooks (on_ready, on_not_ready, segment_ready, read_auth, publish_auth)
- [x] `infra/mediamtx/Dockerfile` — imagem MediaMTX com config embutida
- [x] `infra/postgres/init.sql` — extensões (uuid-ossp, pg_trgm) e índices iniciais
- [x] Atualizar `ARCHITECTURE.md` com protocolos: RTSP pull, RTMP push direto, ONVIF

---

## Sprint 1 — Foundation: Infra + IAM [2026-03-30] ✅

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
- [x] `migrations/versions/001_initial_schema.py` — migration inicial (todas as tabelas IAM + cameras)

### 1.3 Testes Sprint 1

- [x] `tests/unit/iam/test_domain.py` — 16 testes (entidades, hierarquia, enums)
- [x] `tests/unit/iam/test_service.py` — 19 testes (services com repos mockados)
- [x] `tests/integration/test_auth.py` — 10 testes (login, refresh, /me, erros)
- [x] `tests/bdd/features/auth.feature` + steps — 6 cenários BDD
- [x] 51 testes total Sprint 1 — todos passando

**Critério de aceite:** `make test` verde, `make lint` verde, migrate roda sem erro

---

## Sprint 2 — Cameras & Agents [2026-03-30] ✅

### 2.1 Cameras (Bounded Context)

- [x] `cameras/domain.py` — Camera, Agent, CameraConfig entities
- [x] `cameras/models.py` — ORM models
- [x] `cameras/repository.py` — Protocol + SQLAlchemy impl
- [x] `cameras/schemas.py` — DTOs
- [x] `cameras/service.py` — CRUD cameras, CRUD agents, heartbeat, config
- [x] `cameras/mediamtx.py` — MediaMTX API client (add/remove path)
- [x] `cameras/router.py` — CRUD /cameras, CRUD /agents, /agents/me/config, /agents/me/heartbeat

### 2.2 Protocolos de Câmera (adição necessária)

> Câmeras no mercado BR usam RTSP pull via agent, RTMP push direto **ou** ONVIF.
> O modelo atual só suporta RTSP pull. Precisa expandir.

- [x] Adicionar `stream_protocol` ao domínio Camera: `rtsp_pull` | `rtmp_push` | `onvif`
- [x] Adicionar campos ONVIF ao domínio Camera: `onvif_url`, `onvif_username`, `onvif_password`
- [x] Adicionar `rtmp_stream_key` ao domínio Camera (para câmeras RTMP push)
- [x] `cameras/onvif_client.py` — cliente ONVIF SOAP raw (httpx): GetDeviceInformation, GetProfiles, GetStreamUri, GetSnapshotUri, WS-Discovery
- [x] `cameras/snapshot.py` — captura de snapshot: via ONVIF GetSnapshotUri ou proxy interno
- [x] Endpoint `GET /api/v1/cameras/{id}/snapshot` → retorna URL de snapshot
- [x] Endpoint `GET /api/v1/cameras/{id}/stream-urls` → retorna URLs assinadas HLS, WebRTC, RTSP
- [x] Endpoint `POST /api/v1/cameras/discover` → WS-Discovery ONVIF na subnet (lista câmeras encontradas)
- [x] Endpoint `POST /api/v1/cameras/onvif-probe` → testa credenciais ONVIF para um IP específico
- [x] Migration `003_camera_protocols.py`: adicionar colunas `stream_protocol`, `onvif_*`, `rtmp_stream_key`; tornar `rtsp_url` nullable
- [x] Atualizar `cameras/service.py` — lógica: se `rtmp_push`, gera stream_key sem agent; se `onvif`, extrai rtsp_url via probe
- [x] `core/security.py` — `create_viewer_token` (JWT curta duração para viewer de stream)
- [x] `iam/service.py` — `AuthService.issue_viewer_token`

### 2.3 Testes Sprint 2

- [x] `tests/unit/cameras/test_domain.py` — 10 testes
- [x] `tests/unit/cameras/test_service.py` — 11 testes
- [x] `tests/integration/test_cameras.py` — 5 testes CRUD completo
- [x] `tests/integration/test_agents.py` — 5 testes config, heartbeat, API key
- [x] `tests/bdd/features/cameras.feature` + steps — 5 cenários BDD
- [x] `tests/bdd/features/agents.feature` + steps — 5 cenários BDD
- [x] `tests/unit/cameras/test_onvif_client.py` — mock ONVIF responses
- [x] `tests/unit/cameras/test_snapshot.py` — snapshot via ONVIF e ffmpeg

**Critério de aceite:** Camera RTMP push criada → MediaMTX path configurado sem agent; ONVIF camera → rtsp_url extraída automaticamente; snapshot endpoint retorna JPEG

---

## Sprint 2.5 — PTZ & ONVIF Avançado [2026-04-01] ✅

> PTZ (Pan-Tilt-Zoom) via ONVIF para câmeras que suportam.

- [x] `ptz/domain.py` — PtzCommand, PtzPreset, PtzCapabilities, PtzVector
- [x] `ptz/client.py` — PtzClient ONVIF SOAP raw (httpx): ContinuousMove, AbsoluteMove, Stop, GetPresets, GotoPreset, SetPreset, GetCapabilities
- [x] `ptz/service.py` — PtzService: move, absolute_move, stop, get_presets, goto_preset, save_preset, probe_capabilities
- [x] `ptz/schemas.py` — DTOs: PtzMoveRequest, PtzPresetsResponse, SavePresetRequest, PtzActionResponse
- [x] `ptz/router.py`:
  - `POST /api/v1/cameras/{id}/ptz/move` — move contínuo (pan/tilt/zoom + timeout)
  - `POST /api/v1/cameras/{id}/ptz/stop` — para movimento
  - `GET /api/v1/cameras/{id}/ptz/presets` — lista presets
  - `POST /api/v1/cameras/{id}/ptz/presets/{n}/goto` — goto preset
  - `POST /api/v1/cameras/{id}/ptz/presets/{n}/save` — salva posição atual como preset
- [x] `tests/unit/ptz/test_service.py` — 14 testes com mock ONVIF PTZ service
- [x] `cameras/domain.py` — `ptz_supported: bool = False` adicionado à Camera
- [x] `cameras/models.py` — coluna `ptz_supported` no ORM
- [x] `cameras/schemas.py` — `ptz_supported` em CameraResponse e UpdateCameraRequest
- [x] `migrations/versions/004_ptz_supported.py` — migration da coluna

**Critério de aceite:** Move command → câmera se move; goto preset funciona
**Testes:** 14 novos · 156 total — todos passando

---

## Sprint 3 — Streaming & Recordings [2026-03-30] ✅

### 3.1 Streaming (Bounded Context)

- [x] `streaming/domain.py` — StreamSession, ViewerToken
- [x] `streaming/models.py`
- [x] `streaming/service.py` — on_stream_ready, on_stream_stopped, verify_publish_token
- [x] `streaming/router.py` — POST /streaming/publish-auth (MediaMTX hook)
- [x] `migrations/versions/002_stream_sessions.py`

### 3.2 Viewer Auth & URLs de Streaming (adição necessária)

> O current `verify_publish_token` tem um TODO e aceita qualquer token não-vazio.
> Viewers (browser) precisam de URL autenticada para HLS/WebRTC.
> MediaMTX suporta `readUser`/`readPass` por path — integrar com VMS.

- [x] Implementar `verify_publish_token` real — valida stream key (RTMP push) ou API key de agent
- [x] `streaming/service.py` — `verify_viewer_token(token, path)` → bool (usado pelo MediaMTX read-auth hook)
- [x] `POST /streaming/read-auth` — hook MediaMTX para autenticar viewers HLS/WebRTC
- [x] `GET /api/v1/cameras/{id}/stream-urls` → retorna `{ hls_url, webrtc_url, rtsp_url, token, expires_at }` (já existia como stream-urls)
- [x] Atualizar `infra/mediamtx/mediamtx.yml` — `authHTTPAddress` despacha publish e read via campo `action`
- [x] Atualizar `infra/nginx/nginx.conf` — `/hls/` e `/webrtc/` passam token para MediaMTX (proxy_pass sem bloquear)

### 3.3 RTMP Direct Push (câmeras sem agent)

> Câmeras IP de entrada (Intelbras, Reolink) suportam RTMP push nativo.
> Não precisam de agent. VMS autentica via publish-auth hook.

- [x] Atualizar `streaming/service.py` — `verify_publish_token` aceita stream key de câmeras RTMP push
- [x] `GET /api/v1/cameras/{id}/rtmp-config` → retorna `{ rtmp_url, stream_key }` para configurar câmera
- [x] `cameras/service.py` — gera `rtmp_stream_key` aleatório ao criar câmera RTMP push (já existia)
- [x] `tests/integration/test_rtmp_push.py` — simular publish-auth com stream key

### 3.4 Recordings (Bounded Context)

- [x] `recordings/domain.py` — RecordingSegment, Clip
- [x] `recordings/models.py`
- [x] `recordings/repository.py`
- [x] `recordings/service.py` — index_segment, create_clip, cleanup_expired
- [x] `recordings/schemas.py`
- [x] `recordings/router.py` — GET /recordings, POST /recordings/clips
- [x] `recordings/tasks.py` — ARQ tasks: index_segment, cleanup_segments
- [x] `GET /api/v1/recordings/{id}/download` → redirect para URL assinada do arquivo
- [x] `GET /api/v1/cameras/{id}/timeline` → segmentos agrupados por hora para UI de playback
- [x] `GET /api/v1/recordings/clips/{id}` → status do clip (polling para UI saber quando ficou pronto)

### 3.5 Testes Sprint 3

- [x] `tests/unit/streaming/test_service.py` — 4 testes webhooks MediaMTX
- [x] `tests/unit/streaming/test_streaming_service.py` — 10 testes StreamingService
- [x] `tests/unit/recordings/test_service.py` — 7 testes RecordingService
- [x] `tests/integration/test_mediamtx_hooks.py` — 6 testes publish-auth + webhooks
- [x] `tests/integration/test_recordings.py` — 5 testes segments + clips
- [x] `tests/bdd/features/recording.feature` + steps — 3 cenários BDD
- [x] `tests/unit/streaming/test_viewer_token.py` — geração + verificação de tokens de viewer
- [x] `tests/integration/test_read_auth.py` — hook read-auth MediaMTX
- [x] `tests/integration/test_rtmp_push_auth.py` — publish-auth com stream key

**Critério de aceite:** `GET /cameras/{id}/stream` → URL HLS com token válido; viewer sem token → 401 no read-auth; RTMP push com stream key correto → aceito; câmera sem token → rejeitado

---

## Sprint 3.5 — VOD Timeline & Retention Management [pendente]

### 3.5.1 VOD Playback via MediaMTX

> MediaMTX já tem API de recording/playback built-in.
> VMS precisa apenas proxiar com autenticação.

- [ ] `GET /api/v1/cameras/{id}/vod` — proxy para MediaMTX recording API
  - Query params: `from=ISO8601&to=ISO8601`
  - VMS valida ViewerToken, chama MediaMTX GET /recording/get, retorna HLS URL autenticada
  - Nginx serve /recordings/ com auth_request JWT (já configurado no Sprint 8)
- [ ] `GET /api/v1/cameras/{id}/timeline` — heat map de horas com gravação
  - Retorna `{ "2026-04-01": { "14": 60, "15": 58, "16": 60, ... } }` (minutos gravados por hora)
  - Query do RecordingSegment no DB agrupado por hora

### 3.5.2 Retenção Pendente

> Ao fazer upgrade de retenção (ex: 5→15 dias), o novo prazo
> só entra em vigor ao fim do ciclo atual para não onerar storage de surpresa.

- [ ] Adicionar `retention_days_pending: int | None` à Camera (domain + model + schema)
- [ ] Adicionar `retention_pending_from: datetime | None` à Camera
- [ ] Migration `005_retention_pending.py` (renumerar se necessário)
- [ ] `cameras/service.py` — lógica de upgrade/downgrade:
  - Upgrade: seta pending, `retention_pending_from = now() + retention_days_atuais dias`
  - Downgrade: aplica imediatamente, limpa pending
- [ ] ARQ task `apply_pending_retention()` — roda diariamente, aplica pendentes vencidos

### 3.5.3 Testes

- [ ] `tests/unit/cameras/test_retention_pending.py` — lógica upgrade/downgrade
- [ ] `tests/integration/test_vod.py` — endpoint VOD com mock MediaMTX
- [ ] `tests/unit/recordings/test_apply_pending_retention.py` — ARQ task

**Critério de aceite:** Frontend consegue scrubbing de 1h de gravação sem buffering; upgrade 5→15 dias não expande storage imediatamente

---

## Sprint 4 — Events & ALPR [2026-04-01] ✅

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

## Sprint 5 — Notifications & Event Bus [2026-04-01] ✅

### 5.1 Notifications (Bounded Context)

- [x] `notifications/domain.py` — NotificationRule, NotificationLog
- [x] `notifications/models.py`
- [x] `notifications/repository.py`
- [x] `notifications/service.py` — evaluate_rules, dispatch_webhook (HMAC-SHA256)
- [x] `notifications/schemas.py`
- [x] `notifications/router.py` — CRUD /notifications/rules, GET /notifications/logs
- [x] `notifications/dispatcher.py` — httpx async dispatch + retry (3×, exponential backoff)
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
- [x] Adicionar ao health: `mediamtx: "ok"|"degraded"` — checar `/v3/config/global/get` da API MediaMTX
- [x] Adicionar ao health: `cameras_online: int` e `cameras_total: int`

### 5.5 Testes Sprint 5

- [x] `tests/unit/notifications/test_service.py` — 9 testes (CRUD + evaluate_and_dispatch)
- [x] `tests/unit/notifications/test_dispatcher.py` — 5 testes (HMAC, success, failure, error)
- [x] `tests/integration/test_notifications.py` — 6 testes CRUD regras
- [x] `tests/bdd/features/notifications.feature` + steps — 3 cenários BDD
- [x] `tests/integration/test_e2e_alpr_to_notification.py` — E2E: ALPR → Event → Notification

**Critério de aceite:** ALPR event → regra match → webhook disparado com X-VMS-Signature correto

---

## Sprint 6 — Edge Agent [2026-04-01] ✅

### 6.1 Edge Agent (serviço separado)

- [x] `edge_agent/pyproject.toml`
- [x] `edge_agent/Dockerfile`
- [x] `edge_agent/src/agent/config.py` — env vars
- [x] `edge_agent/src/agent/cloud_client.py` — HTTP client (poll config, heartbeat)
- [x] `edge_agent/src/agent/stream_manager.py` — ffmpeg subprocess management (RTSP pull → RTMP push)
- [x] `edge_agent/src/agent/health_checker.py` — process monitor + restart
- [x] `edge_agent/src/agent/main.py` — event loop principal

### 6.2 P2P & Conectividade NAT (adição necessária)

> Problema real: cliente tem câmeras em rede privada 192.168.x.x.
> O VMS está na cloud ou data center do integrador.
> Agent faz RTMP push para o VMS — isso já resolve o problema de saída de vídeo.
> O que falta: config push do VMS para o agent (atual = polling 30s → lento).
> E: acesso RTSP direto ao agent quando VMS precisa puxar stream (analytics server-side).

- [x] `edge_agent/src/agent/cloud_client.py` — WebSocket persistente para receber config push imediato
  - Conecta em `wss://vms.host/api/v1/agents/me/ws` com API key
  - Recebe mensagens: `config_updated`, `camera_added`, `camera_removed`, `restart_stream`
  - Fallback para polling se WebSocket cair
- [x] `api/src/vms/cameras/router.py` — `GET /api/v1/agents/me/ws` WebSocket endpoint
  - Autentica via API key no handshake
  - Publica no Redis channel `agent:{agent_id}:config` quando config muda
  - Redis pub/sub → WebSocket push
- [x] `cameras/service.py` — ao criar/atualizar/deletar câmera, publicar evento no channel do agent
- [x] Documentar abordagem P2P/NAT em `docs/DEPLOY.md`:
  - Agent faz RTMP push para o VMS (fluxo de saída — sem problema de NAT)
  - Analytics acessa via MediaMTX (stream já está no VMS)
  - STUN/TURN para WebRTC: documentar configuração do MediaMTX com servidor STUN público e opção TURN próprio
- [x] `infra/mediamtx/mediamtx.yml` — adicionar seção `webrtc.iceServers` com STUN público + opção TURN

### 6.3 STUN/TURN para Playback WebRTC

> Viewers fora da rede local precisam de ICE para estabelecer WebRTC.
> MediaMTX suporta ICE servers configuráveis.

- [x] `infra/mediamtx/mediamtx.yml` — configurar ICE servers: STUN público (stun.l.google.com) + TURN opcional
- [x] `.env.example` — variáveis: `TURN_URL`, `TURN_USERNAME`, `TURN_CREDENTIAL`
- [x] `docker-compose.yml` — passar variáveis TURN para o serviço mediamtx
- [x] Documentar em `docs/DEPLOY.md`: quando TURN é necessário (NAT simétrico) e como configurar coturn

### 6.4 Testes Sprint 6

- [x] `edge_agent/tests/test_stream_manager.py` — start/stop/restart streams
- [x] `edge_agent/tests/test_cloud_client.py` — config poll, heartbeat
- [x] `tests/bdd/features/edge_agent.feature` + steps
- [x] `edge_agent/tests/test_websocket_client.py` — receber config push via WebSocket
- [x] `api/tests/integration/test_agent_ws.py` — WebSocket endpoint com API key auth

**Critério de aceite:** Config change no VMS → agent recebe em < 1s via WebSocket; stream reinicia automaticamente

---

## Sprint 7 — Analytics Service [2026-04-01] ✅

### 7.1 Framework de Plugins

- [x] `analytics/src/analytics/core/plugin_base.py` — AnalyticsPlugin ABC
- [x] `analytics/src/analytics/core/yolo_base.py` — YOLOPlugin base
- [x] `analytics/src/analytics/core/orchestrator.py` — frame capture + plugin routing
- [x] `analytics/src/analytics/core/frame_source.py` — OpenCV RTSP reader (1fps) — usado SOMENTE para intrusion real-time
- [ ] `analytics/src/analytics/core/segment_processor.py` — lê .mp4 do disco, extrai frames via ffmpeg, envia para plugins
- [ ] ARQ task `analytics_segment(segment_id)` — disparada após index_segment()
- [ ] `analytics/src/analytics/core/orchestrator.py` — modo dual: pós-gravação (padrão) vs real-time (somente intrusion)
- [x] `analytics/src/analytics/core/vms_client.py` — HTTP client para VMS API
- [x] `analytics/src/analytics/core/config.py` — settings
- [x] `analytics/src/analytics/main.py` — FastAPI app + lifespan

### 7.2 Plugins Core

- [x] `analytics/src/analytics/plugins/intrusion/plugin.py` — YOLOv8n + polígono
- [x] `analytics/src/analytics/plugins/people_count/plugin.py` — YOLOv8n count
- [x] `analytics/src/analytics/plugins/vehicle_count/plugin.py` — YOLOv8n classes car/truck/moto
- [x] `analytics/src/analytics/plugins/lpr/plugin.py` — YOLOv8 detect + fast-plate-ocr

### 7.3 API interna (analytics ↔ VMS)

- [x] `POST /internal/analytics/ingest/` — recebe resultado do plugin
- [x] `GET /internal/cameras/{id}/rois/` — ROIs ativas por câmera
- [x] `GET /health` — status dos plugins carregados

### 7.4 ROI Management no VMS API

- [x] `analytics_config/domain.py` — RegionOfInterest
- [x] `analytics_config/models.py`
- [x] `analytics_config/service.py` — CRUD ROIs
- [x] `analytics_config/router.py` — GET/POST/PATCH/DELETE /analytics/rois
- [x] `GET /api/v1/analytics/rois/{id}/events` — eventos gerados por esta ROI (filtrado por data)
- [x] `GET /api/v1/analytics/summary` — contagens agregadas por câmera/período (para dashboard)

### 7.5 Testes Sprint 7

- [x] `analytics/tests/unit/test_intrusion_plugin.py`
- [x] `analytics/tests/unit/test_people_count_plugin.py`
- [x] `analytics/tests/unit/test_lpr_plugin.py`
- [x] `analytics/tests/integration/test_analytics_api.py`
- [x] `tests/bdd/features/analytics.feature` + steps

**Critério de aceite:** Frame sintético com pessoas → people_count emite evento; LPR detecta placa; ROI events listam histórico

---

## Sprint 8 — Segurança, Observabilidade & Polish [2026-04-02] ✅

- [x] Rate limiting `slowapi` em webhooks + auth endpoints
- [x] Security headers no Nginx (HSTS, CSP, X-Frame-Options)
- [x] Structured logging com `structlog` (JSON em prod)
- [x] Métricas endpoint `/metrics` (contadores básicos)
- [x] Backup script `infra/scripts/backup_db.sh`
- [x] `make test-cov` → coverage > 80% em todos os contextos
- [x] Documentação OpenAPI gerada automaticamente verificada
- [x] `docker compose up` completo funciona sem erros
- [x] Smoke test E2E: câmera criada → agent heartbeat → stream → recording segment
- [x] Nginx: `/hls/` e `/webrtc/` exigem token (sem token → 401 antes de chegar no MediaMTX)
  - Implementado via `auth_request /streaming-auth-check` → `GET /streaming/auth-check?token=&path=`
- [x] Nginx: `/recordings/` serve arquivos apenas com JWT válido
  - Implementado via `auth_request /recordings-auth-check`
- [x] Rate limit diferenciado: webhooks câmera (500/min), API auth (5/min), API geral (120/min), SSE (30 conexões simultâneas)
- [x] ARQ dead letter queue — tasks que falham 3× → DLQ + alerta via NotificationRule tipo `system.task_failed`
- [x] `docker-compose.yml` — adicionar `restart: unless-stopped` em todos os serviços críticos
- [x] Smoke test completo RTMP push: câmera RTMP → stream live → recording → download

**Critério de aceite final:**
- `make test` → todos os testes passam
- `make lint` → zero erros
- `docker compose up` → todos os serviços healthy
- Coverage > 80% global
- HLS stream inacessível sem token
- Recording inacessível sem JWT válido

---

## Pós-MVP — Funcionalidades Futuras

> Não bloqueia o MVP. Implementar após 2026-04-02.

### Face Recognition (LGPD-bloqueado)
- [ ] `analytics/src/analytics/plugins/face_recognition/plugin.py` — InsightFace embeddings
- [ ] `FaceProfile` model — name, embedding, tenant FK, lgpd_consent
- [ ] `facial_recognition_enabled` por Tenant (default: False, exige termo aceito)
- [ ] `DELETE /api/v1/faces/{id}/` — direito ao esquecimento LGPD
- [ ] Logs de acesso separados para dados biométricos

### Weapon Detection (dataset necessário)
- [ ] Fine-tuning YOLOv8 com dataset licenciado (Open Images ou proprietário)
- [ ] `analytics/src/analytics/plugins/weapon_detection/plugin.py`
- [ ] UI: disclaimer explícito "beta — alto risco de falso positivo"

### Frontend
- [ ] Dashboard câmeras (grid live view HLS/WebRTC)
- [ ] Timeline de gravações com playback
- [ ] Timeline de gravações com scrubbing via HLS.js (VOD MediaMTX)
- [ ] Mapa de câmeras
- [ ] Eventos e alertas em tempo real (SSE consumer)
- [ ] Gestão de ROIs com editor de polígono
- [ ] Relatórios analytics (people/vehicle count por hora/dia)
- [ ] PTZ control (se câmera suportar)

### Multitenancy avançado
- [ ] Limites por tenant: max_cameras, max_retention_days, analytics_enabled
- [ ] Billing hooks (eventos de quota excedida)
- [ ] Tenant admin UI

### P2P Avançado
- [ ] coturn deployment no docker-compose (TURN server próprio)
- [ ] Agent tunnel reverso para acesso RTSP direto sem exposição de porta

---

## Progresso Geral

```
Sprint 0  ██████████░░  ✅ Estrutura + Docs (infra configs pendentes)
Sprint 1  ████████████  ✅ IAM + Foundation (51 testes)
Sprint 2  ████████░░░░  ✅ Cameras + Agents | ░ ONVIF + multi-protocol
Sprint 2.5 ████████████  ✅ PTZ & ONVIF Avançado (14 testes)
Sprint 3  ████████░░░░  ✅ Streaming + Recordings | ░ viewer auth + RTMP push + download
Sprint 3.5 ░░░░░░░░░░░░  ☐ VOD Timeline + Retention Pending
Sprint 4  ████████████  ✅ Events + ALPR (42 testes + 3 BDD)
Sprint 5  ████████████  ✅ Notifications + Event Bus + SSE + Health
Sprint 6  ████████░░░░  ✅ Edge Agent | ░ WebSocket push + STUN/TURN docs
Sprint 7  ████████░░░░  ✅ Analytics (4 plugins) | ░ ROI events + summary
Sprint 8  ████████░░░░  ✅ Security + Polish | ░ auth em /hls/ e /recordings/
Sprint 9  ░░░░░░░░░░░░  ☐ Frontend (pós-backend 100%)
```

---

## Sprint 9 — Frontend [pós-backend 100%]

> Stack idêntica ao legado. Design replicado 1:1 — mesmas variáveis CSS, mesmas classes utilitárias,
> mesmos padrões de componente. O legado em `legado/frontend/` é a referência visual de produção.

---

### 9.0 Setup & Design System

#### Estrutura de projeto

```
mvp/frontend/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── index.css              ← design tokens (CSS vars idênticas ao legado)
    ├── components/
    │   ├── ui/                ← Modal, Badge, Spinner, Tooltip, Confirm
    │   ├── camera/            ← VideoPlayer, CameraCard, DetectionOverlay
    │   ├── layout/            ← Layout, Sidebar, Header
    │   └── wizard/            ← AddCameraWizard, OnboardingWizard, AgentWizard
    ├── pages/                 ← uma pasta por tela
    ├── hooks/                 ← useSSE, usePermission, useTheme, useConfirm
    ├── services/              ← api.ts (axios) + serviços por domínio
    ├── store/                 ← authStore, themeStore (Zustand + persist)
    └── types/                 ← index.ts (contratos TS espelhando a API)
```

#### Tech stack (idêntica ao legado)

```
React 18 + TypeScript 5        — framework
Vite 5                         — build tool
Tailwind CSS 3                 — styling
Zustand 4 + persist            — state management
react-router-dom 6             — routing
axios                          — HTTP client
HLS.js                         — streaming HLS
Recharts                       — gráficos
react-hook-form + Zod          — forms com validação
lucide-react                   — ícones
clsx                           — className condicional
date-fns (pt-BR)               — formatação de datas
react-hot-toast                — notificações toast
```

#### Checklist setup

- [x] `frontend/package.json` — dependências acima
- [x] `frontend/vite.config.ts` — alias `@/` → `src/`, proxy `/api` e `/webhooks` para `localhost:8000`
- [x] `frontend/tailwind.config.ts` — cores customizadas referenciando CSS vars:
  ```js
  colors: {
    bg: 'var(--bg)', surface: 'var(--surface)', elevated: 'var(--elevated)',
    border: 'var(--border)', accent: 'var(--accent)',
    t1: 'var(--text-1)', t2: 'var(--text-2)', t3: 'var(--text-3)',
    success: 'var(--success)', warning: 'var(--warning)', danger: 'var(--danger)',
  }
  ```
- [x] `frontend/src/index.css` — CSS vars, `.btn`, `.btn-primary`, `.btn-ghost`, `.btn-danger`, `.card`, `.input`, `.label`, `.badge`, scrollbar, `animate-fade-in`, `animate-slide-in`
- [x] `frontend/Dockerfile` — multi-stage: build Vite → nginx:alpine serving `/dist`

---

### 9.1 Core Components

#### UI Primitives (replicar do legado exatamente)

- [x] `components/ui/Modal.tsx` — props: `open`, `onClose`, `title`, `size` (sm/md/lg/xl/full), `footer`; Escape key; click fora fecha; animação slide-in
- [x] `components/ui/Badge.tsx` — props: `variant` (default/success/warning/danger/info), `dot`, `className`
- [x] `components/ui/Spinner.tsx` — `<Spinner />` inline + `<PageSpinner />` full-height centered
- [x] `components/ui/Tooltip.tsx` — hover tooltip simples (usar `title` nativo como fallback)
- [x] `components/ui/Confirm.tsx` — modal de confirmação: "Tem certeza?" com btn-danger; hook `useConfirm()`

#### Camera Components

- [x] `components/camera/VideoPlayer.tsx` — HLS.js + controles hover (play/pause, mute, fullscreen); overlay prop para canvas de detecção; camera name overlay top-left; estados: loading (spinner), error ("Sem sinal"), no-source; `lowLatencyMode: true`, `maxBufferLength: 10`
- [x] `components/camera/DetectionOverlay.tsx` — canvas sobreposto ao vídeo; recebe `detections: { bbox, label, confidence }[]`; re-escala bbox normalizada para pixels
- [x] `components/camera/CameraCard.tsx` — thumbnail (snapshot ou placeholder escuro); status dot (verde/vermelho); badge Online/Offline; badge "IA" se analytics ativos; protocolo (RTSP/RTMP/ONVIF); hover: botões Visualizar + Configurar

#### Layout

- [x] `components/layout/Sidebar.tsx` — logo (dinâmico via themeStore); nav items com ícones Lucide; active state accent bg; colapsa para ícones em telas pequenas; logout no bottom
- [x] `components/layout/Header.tsx` — título da página atual; sino de notificações com contador badge; avatar + nome + role do usuário logado
- [x] `components/layout/Layout.tsx` — flex h-full: `<Sidebar>` + flex-col: `<Header>` + `<main>` overflow-auto px-6 py-5

#### Hooks base

- [x] `hooks/useSSE.ts` — conecta `GET /sse/events` com JWT; reconecta em caso de drop; retorna `{ lastEvent, connected }`
- [x] `hooks/usePermission.ts` — `isAdmin()`, `isOperator()`, `isViewer()` baseado no role do authStore
- [x] `hooks/useTheme.ts` — aplica `--accent` e título da aba via themeStore; busca theme em `GET /api/v1/tenants/me/theme`
- [x] `hooks/useConfirm.ts` — retorna `confirm(message): Promise<boolean>` renderizando `<Confirm />`

#### Services / API Client

- [x] `services/api.ts` — instância axios com `baseURL`, interceptor de auth (adiciona Bearer), interceptor de refresh (401 → refresh → retry)
- [x] `services/auth.ts` — `login()`, `refresh()`, `me()`
- [x] `services/cameras.ts` — `list()`, `get()`, `create()`, `update()`, `delete()`, `streamUrls()`, `snapshot()`, `rtmpConfig()`, `discover()`, `onvifProbe()`
- [x] `services/agents.ts` — `list()`, `create()`, `delete()`, `regenerateKey()`
- [x] `services/recordings.ts` — `listSegments()`, `timeline()`, `createClip()`, `getClip()`, `listClips()`, `downloadUrl()`
- [x] `services/events.ts` — `list()`, `get()` (com filtros: camera, tipo, placa, data)
- [x] `services/notifications.ts` — `listRules()`, `createRule()`, `updateRule()`, `deleteRule()`, `listLogs()`
- [x] `services/analytics.ts` — `listROIs()`, `createROI()`, `updateROI()`, `deleteROI()`, `roiEvents()`, `summary()`
- [x] `services/dashboard.ts` — `stats()`, `detectionsByHour()`
- [x] `services/iam.ts` — `listUsers()`, `createUser()`, `updateUser()`, `deactivateUser()` (coberto por `services/users.ts`)

---

### 9.2 Onboarding Wizard (primeira vez)

> Exibido automaticamente quando tenant não tem câmeras nem agents configurados.
> Guia o integrador do zero até o primeiro stream funcionando.

**Arquivo:** `components/wizard/OnboardingWizard.tsx`
**Trigger:** `App.tsx` verifica `GET /health` + `GET /api/v1/cameras?page_size=1` — se cameras.total === 0 e agent === 0, mostra wizard em fullscreen.

#### Passo 0 — Bem-vindo (tela de boas-vindas)

```
┌─────────────────────────────────────────────────────────────┐
│                     [Logo da empresa]                        │
│                                                              │
│         Bem-vindo ao VMS                                     │
│   Vamos configurar seu sistema em poucos minutos.            │
│                                                              │
│   ○ Configurar instância                                     │
│   ○ Instalar o Agent na rede das câmeras                     │
│   ○ Adicionar sua primeira câmera                            │
│   ○ Verificar o stream ao vivo                               │
│                                                              │
│                        [Começar →]                           │
└─────────────────────────────────────────────────────────────┘
```

#### Passo 1 — Configurar instância

- Nome do sistema (ex: "VMS — Empresa XYZ")
- Cor primária (color picker → atualiza `--accent` em tempo real)
- Logo upload (opcional) → preview inline
- `PATCH /api/v1/tenants/me` com os dados

#### Passo 2 — Instalar o Agent

```
┌─────────────────────────────────────────────────────────────┐
│  Passo 2 de 5 — Agent                                        │
│                                                              │
│  O Agent roda na rede onde estão as câmeras e envia os       │
│  streams para cá.                                            │
│                                                              │
│  1. Copie sua API Key:                                       │
│     [vms_abc12345_xxxxxxxxxxxxx]  [📋 Copiar]               │
│                                                              │
│  2. Execute no servidor local:                               │
│     docker run ... VMS_API_KEY=<key> VMS_API_URL=<url>      │
│     [📋 Copiar comando]                                      │
│                                                              │
│  3. Aguardando agent conectar...  [◉ Verificando...]        │
│     (polling GET /api/v1/agents?status=online a cada 3s)     │
│                                                              │
│  [Pular — tenho câmeras RTMP/ONVIF diretas →]               │
└─────────────────────────────────────────────────────────────┘
```

- Cria Agent automaticamente via `POST /api/v1/agents` ao entrar no passo
- Mostra API key (UMA vez) com botão copiar
- Gera comando docker completo com as variáveis preenchidas
- Poll a cada 3s para detectar agent online — quando detectar, avança automaticamente com animação ✅

#### Passo 3 — Adicionar primeira câmera

- Abre inline o `AddCameraWizard` (sem modal separado — embutido no fluxo)
- Protocolo pré-selecionado baseado no contexto:
  - Se agent foi detectado no passo 2 → sugere RTSP via Agent
  - Se passo 2 foi pulado → sugere RTMP ou ONVIF

#### Passo 4 — Verificar stream ao vivo

```
┌─────────────────────────────────────────────────────────────┐
│  Passo 4 de 5 — Stream ao vivo                               │
│                                                              │
│  ┌─────────────────────────────────┐                        │
│  │                                 │                        │
│  │      [VideoPlayer HLS]          │                        │
│  │      "Câmera 01"                │                        │
│  │                                 │                        │
│  └─────────────────────────────────┘                        │
│                                                              │
│  Status: ● Online — stream recebido                         │
│  Protocolo: RTSP · Resolução: 1920×1080 · 25fps             │
│                                                              │
│  [← Adicionar outra câmera]    [Concluir configuração →]    │
└─────────────────────────────────────────────────────────────┘
```

#### Passo 5 — Concluído

- Confete animado (CSS puro)
- Resumo: X câmeras, Y agents, Z analíticos configurados
- Links rápidos: Dashboard, Mosaico, Gravações
- Botão "Ir para o Dashboard"
- `localStorage.setItem('onboarding_complete', '1')` para não mostrar novamente

**Checklist:**
- [x] `components/wizard/OnboardingWizard.tsx` — wizard 5 passos
- [x] `App.tsx` — lógica de trigger do onboarding
- [x] `hooks/useOnboarding.ts` — estado + progresso + skip logic

---

### 9.3 AddCamera Wizard (expandido)

> Versão expandida do legado para suportar todos os protocolos do novo VMS.
> **Arquivo:** `components/wizard/AddCameraWizard.tsx`

**5 passos (ou 6 para RTMP):**

```
[Protocolo] → [Conexão] → [Configuração] → [Analíticos] → [Revisão] → ✅
```

#### Passo 0 — Escolha o protocolo

Cards em grid 3×2 com ícone grande, nome e descrição:

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   📡 RTSP    │  │   📤 RTMP    │  │   🔍 ONVIF   │
│  Via Agent   │  │ Push direto  │  │ Auto-discover│
│  IP Cameras  │  │ Câmera envia │  │  Detecção    │
│  DVR / NVR   │  │ pra cá       │  │  automática  │
└──────────────┘  └──────────────┘  └──────────────┘
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   🌐 IP Cam  │  │   🤝 P2P     │  │   ➕ Manual  │
│ IP + porta   │  │  Via Agent   │  │  URL direta  │
│ auto ONVIF   │  │  (NAT)       │  │  (avançado)  │
└──────────────┘  └──────────────┘  └──────────────┘
```

- **RTSP via Agent** — câmera na rede local, Agent faz pull e push para o VMS
- **RTMP push** — câmera envia diretamente para o VMS (sem Agent)
- **ONVIF** — descoberta automática: IP + credenciais → GetStreamUri
- **IP Camera** — assistente simplificado: IP + porta + user/pass → tenta ONVIF, fallback RTSP
- **P2P (via Agent)** — igual RTSP mas com instrução específica para NAT traversal
- **Manual (URL direta)** — RTSP/RTMP/HLS URL bruta para usuários avançados

#### Passo 1 — Conexão (varia por protocolo)

**RTSP via Agent:**
```
Agent:    [select — lista agents online]
IP:       [192.168.1.100       ]
Porta:    [554   ]
Usuário:  [admin  ]  Senha: [••••••]
Caminho:  [/stream  ] (opcional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
URL gerada: rtsp://admin:••••@192.168.1.100:554/stream   [Testar conexão ▶]
```

**RTMP push:**
```
ℹ A câmera vai ENVIAR o stream para o VMS.
  Após criar, você receberá as credenciais para configurar na câmera.

Nenhum campo necessário aqui — as credenciais serão geradas automaticamente.
```

**ONVIF:**
```
IP da câmera: [192.168.1.100]
Porta ONVIF:  [80     ]  (padrão: 80)
Usuário:      [admin  ]  Senha: [••••••]
                              [🔍 Descobrir stream]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Streams encontrados:
  ◉ Main Stream  rtsp://192.168.1.100:554/h265/ch1
  ○ Sub Stream   rtsp://192.168.1.100:554/h264/ch1/sub
  ○ Terceiro     rtsp://192.168.1.100:554/h264/ch2
```

**IP Camera (assistente):**
```
IP ou hostname: [192.168.1.100]
Usuário:        [admin ]  Senha: [•••••]
                              [🔍 Detectar câmera]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Detectado: Hikvision DS-2CD2143G2-I
Protocolo: ONVIF ✅
Streams:  Main (2688×1520) | Sub (640×360)
```

**P2P via Agent (NAT):**
```
Agent:    [select — lista agents online + status NAT]
           ● Agent SP-01  (NAT: Aberto ✅)
           ● Agent RJ-02  (NAT: Restrito ⚠)

IP (rede local do agent): [192.168.1.100]
Porta:    [554   ]
Usuário:  [admin ]  Senha: [••••••]

ℹ O Agent está na mesma rede das câmeras.
  Ele fará RTSP pull localmente e enviará via RTMP para o VMS.
```

**Manual:**
```
Protocolo:  [select: RTSP / RTMP / HLS]
URL:        [rtsp://...              ]
```

#### Passo 2 — Testar conexão (apenas RTSP/ONVIF/IP)

```
┌───────────────────────────────────────────────┐
│  Testando conexão...                           │
│                                                │
│  ✅ Câmera acessível (ping 12ms)              │
│  ✅ RTSP respondeu (porta 554)                │
│  ✅ Credenciais OK (auth aceito)              │
│  ✅ Stream decodificável (H.264, 1080p, 25fps)│
│                                                │
│  [preview de 1 frame da câmera]               │
└───────────────────────────────────────────────┘
```

- Chama `POST /api/v1/cameras/onvif-probe` ou testa via URL
- Se falhar, mostra diagnóstico: "Câmera inacessível — verifique IP/porta" / "Credenciais inválidas" / "Stream não decodificável"
- "Pular teste" disponível para continuar mesmo com erro

#### Passo 3 — Configuração geral

```
Nome *:       [Entrada Principal              ]
Localização:  [Portaria Norte — Bloco A       ]
Latitude:     [-23.5505   ]  Longitude: [-46.6333]
                             [📍 Usar localização atual]
Retenção:     [7 dias] [15 dias] [30 dias] [personalizado: __ dias]
Agent:        [select — apenas para RTSP/P2P]
```

#### Passo 4 — Analíticos

- Toggle "Habilitar IA" com explicação do custo de CPU
- Grid de analíticos disponíveis (replicar exato do legado):

```
┌──────────────────────┐  ┌──────────────────────┐
│ 🚗 Reconhec. Placa   │  │ 🚙 Tráfego Veículos  │
│ Detecta e lê placas  │  │ Conta e classifica   │
│ [toggle OFF]         │  │ [toggle OFF]         │
└──────────────────────┘  └──────────────────────┘
┌──────────────────────┐  ┌──────────────────────┐
│ 🚶 Tráfego Humano   │  │ 🚨 Intrusão          │
│ Conta pessoas        │  │ Zona proibida        │
│ [toggle OFF]         │  │ [toggle OFF]         │
└──────────────────────┘  └──────────────────────┘
...
```

- Analíticos selecionados criam ROIs automaticamente com config padrão (editáveis depois)

#### Passo 5 — Revisão

```
┌────────────────────────────────────────────────┐
│  Revisar antes de criar                         │
│                                                 │
│  Nome:        Entrada Principal                 │
│  Protocolo:   RTSP via Agent (SP-01)           │
│  Stream:      rtsp://admin@192.168.1.100/stream │
│  Localização: Portaria Norte                    │
│  Retenção:    7 dias                            │
│  Analíticos:  LPR, Intrusão                     │
│                                                 │
│  [← Voltar]              [✅ Criar Câmera]     │
└────────────────────────────────────────────────┘
```

#### Passo 6 — Credenciais RTMP (apenas RTMP push)

```
┌────────────────────────────────────────────────┐
│  ✅ Câmera criada!                              │
│                                                 │
│  Configure na câmera:                           │
│                                                 │
│  RTMP URL:   rtmp://vms.empresa.com/live        │
│              [📋 Copiar]                        │
│                                                 │
│  Stream Key: cam-abc123-xyz789                  │
│              [📋 Copiar]  [👁 Mostrar]          │
│                                                 │
│  ⚠ A Stream Key não será exibida novamente.    │
│                                                 │
│  [Aguardar stream...] ← polling status         │
│  ○ Aguardando câmera conectar...               │
└────────────────────────────────────────────────┘
```

**Checklist:**
- [x] `components/wizard/AddCameraWizard.tsx` — wizard 5-6 passos, todos os protocolos
- [x] `hooks/useConnectionTest.ts` — lógica de teste RTSP/ONVIF com estados loading/ok/error
- [x] Tipos TypeScript para todos os form states por protocolo

---

### 9.4 Telas — Especificações

#### Roteamento

```
/login                     → LoginPage (sem layout)
/                          → redirect → /dashboard
/dashboard                 → DashboardPage
/cameras                   → CamerasPage
/cameras/:id               → CameraDetailPage
/cameras/:id/roi           → ROIEditorPage
/mosaic                    → MosaicPage
/recordings                → RecordingsPage
/events                    → EventsPage
/analytics                 → AnalyticsPage
/agents                    → AgentsPage          ← novo (não existe no legado)
/notifications             → NotificationsPage   ← novo
/users                     → UsersPage           ← admin only
/settings                  → SettingsPage        ← admin only
```

---

#### Tela: LoginPage

**Arquivo:** `pages/LoginPage.tsx`
**Layout:** Split 50/50 — esquerda: branding, direita: formulário. Sem Sidebar/Header.

```
Left (hidden mobile):           Right:
┌──────────────────────┐   ┌──────────────────────┐
│                      │   │                      │
│   [Logo]             │   │   Entrar             │
│                      │   │                      │
│   VMS                │   │   Email              │
│   Sistema de         │   │   [____________]     │
│   Monitoramento      │   │                      │
│                      │   │   Senha              │
│   "Câmeras           │   │   [____________]     │
│    inteligentes       │   │   [ ] Lembrar-me    │
│    para sua          │   │                      │
│    segurança"        │   │   [  Entrar  ]       │
│                      │   │                      │
│   --accent gradient  │   │   v1.0.0             │
└──────────────────────┘   └──────────────────────┘
```

- `themeStore` aplica cor primária e logo do tenant
- Erro de login: shake animation + mensagem inline
- Rate limit 401: "Muitas tentativas. Aguarde X segundos."
- Redirect para `/dashboard` após login bem-sucedido

**Checklist:**
- [x] `pages/LoginPage.tsx`
- [x] `store/authStore.ts` — Zustand + persist em localStorage
- [x] `store/themeStore.ts` — accent var + logo + título
- [x] Interceptor axios refresh token (401 → refresh → retry → se falhar, logout)

---

#### Tela: DashboardPage

**Arquivo:** `pages/DashboardPage.tsx`
**Referência direta:** `legado/frontend/src/pages/DashboardPage.tsx`

**Seções:**

1. **Stat cards** (5 cards em grid responsive 2→3→5):
   - Total de Câmeras · Online · Offline · Detecções Hoje · Gravações
   - Cada card: ícone com bg colorido + label pequeno + número grande
   - SSE: contador "Online" atualiza em tempo real

2. **Detecções por hora** (AreaChart 24h):
   - Gradiente accent com fill opacity 30%→0%
   - Tooltip styled com surface bg
   - `GET /api/v1/dashboard/detections-by-hour`

3. **Eventos hoje por tipo** (mini bar-list lateral):
   - Lista de event_types com bar relativa + count
   - Ordenado por volume decrescente

4. **Câmeras — status em tempo real** (card-table):
   - Dot status (verde/vermelho) · Nome · Endereço · Badge Online/Offline · Protocolo
   - SSE: `camera.online` / `camera.offline` atualiza dot sem reload
   - "Ver todas →" link para `/cameras`

5. **Alertas recentes** (últimas 5 notificações):
   - Ícone por tipo · mensagem · data relativa (date-fns formatDistanceToNow)
   - Link "Ver todos →" para `/events`

**Checklist:**
- [x] `pages/DashboardPage.tsx`
- [x] SSE integration — `useSSE()` hook atualiza counters em tempo real
- [x] `services/dashboard.ts`

---

#### Tela: CamerasPage

**Arquivo:** `pages/CamerasPage.tsx`
**Referência direta:** `legado/frontend/src/pages/CamerasPage.tsx`

**Toolbar:**
- Search input com ícone (busca por nome e localização)
- Filter tabs: Todas · Online · Offline (pill segmented control)
- View toggle: Grid (4 cols) ↔ List (tabela)
- `+ Nova Câmera` → abre `AddCameraWizard`

**Grid view** — `CameraCard`:
```
┌─────────────────────────┐
│ [snapshot 16:9]         │
│  ● Online               │
├─────────────────────────┤
│ Entrada Principal       │ ← nome
│ Portaria Norte          │ ← localização
│ RTSP   [IA]  7d         │ ← protocolo, badge IA, retenção
│ [👁 Ver]  [⚙ Config]   │ ← hover actions
└─────────────────────────┘
```

**List view** — tabela:
- Colunas: Status · Nome · Localização · Protocolo · IA · Agent · Retenção · Ações
- Row click → `/cameras/:id`
- Ações: Config (ícone) · Delete (admin only)

**Checklist:**
- [x] `pages/CamerasPage.tsx`
- [x] `components/camera/CameraCard.tsx`
- [x] SSE: camera.online/offline atualiza status dot sem reload

---

#### Tela: CameraDetailPage

**Arquivo:** `pages/CameraDetailPage.tsx`
**Referência direta:** `legado/frontend/src/pages/CameraDetailPage.tsx`

**Header:** ← back · Nome + badge status · badge IA

**Tabs:** Ao Vivo · Informações · ROIs · Eventos · Clips

**Tab: Ao Vivo**
```
┌──────────────────────────────┐  ┌──────────────────┐
│                              │  │  Status           │
│   [VideoPlayer 16:9]         │  │  ─────────────── │
│   [DetectionOverlay canvas]  │  │  Protocolo RTSP  │
│                              │  │  Retenção  7d    │
│                              │  │  IA        Ativa │
│                              │  │  Resolução 1080p │
│                              │  │  FPS       25    │
│   HLS  ·  WebRTC  ·  RTSP   │  │  ─────────────── │
│   [protocol switcher]        │  │  [📸 Snapshot]   │
└──────────────────────────────┘  │  [🗺 Editor ROI] │
                                   └──────────────────┘
```
- Protocol switcher: HLS (padrão) / WebRTC (baixa latência) / RTSP direto
- `GET /api/v1/cameras/{id}/stream` → retorna URLs com token
- Snapshot: `GET /api/v1/cameras/{id}/snapshot` → abre em tab nova

**Tab: Informações**
- Formulário editável: nome, localização, lat/lng, retenção, protocolo
- Toggle IA habilitada
- Campos ONVIF se `stream_protocol === 'onvif'`: onvif_url
- Campos RTMP se `stream_protocol === 'rtmp_push'`: mostrar stream_key + botão revogar/regenerar
- `[Editar]` / `[Salvar]` / `[Cancelar]` (admin only editar)

**Tab: ROIs**
- Cards com nome, tipo, nº pontos, toggle ativo/inativo
- `[+ Nova ROI]` → abre ROIEditorPage embutida ou link para `/cameras/:id/roi`

**Tab: Eventos**
- Tabela com filtro de data e tipo
- Colunas: Tipo · Placa (se ALPR) · Confiança · Câmera · Data/Hora
- Click na linha → modal com detalhes + thumbnail

**Tab: Clips**
- Grid de clips com thumbnail (VideoPlayer em miniatura)
- Badge status: Processando (amber) · Pronto (verde) · Erro (vermelho)
- Download button quando `ready`

**Checklist:**
- [x] `pages/CameraDetailPage.tsx`
- [x] Protocol switcher (HLS↔WebRTC)
- [x] Snapshot modal

---

#### Tela: ROIEditorPage

**Arquivo:** `pages/ROIEditorPage.tsx`
**Referência:** `legado/frontend/src/pages/ROIEditorPage.tsx`

**Layout:** fullscreen canvas à esquerda, painel de ROIs à direita.

```
┌──────────────────────────────────────┐  ┌────────────────────┐
│                                      │  │  ROIs              │
│  [VideoPlayer como background]       │  │                    │
│  [Canvas SVG sobreposto]             │  │  ┌──────────────┐  │
│                                      │  │  │ Intrusão #1  │  │
│  Click: adiciona ponto               │  │  │ 4 pontos ✅  │  │
│  Drag ponto: reposiciona             │  │  │ [Editar][Del]│  │
│  Double-click: fecha polígono        │  │  └──────────────┘  │
│  Right-click ponto: remove           │  │                    │
│                                      │  │  [+ Nova ROI]      │
│  [Tipo ROI:  select    ]             │  │                    │
│  [Nome ROI: _________ ]             │  │  Tipo:             │
│  [Cor:      ■ ]                     │  │  ◉ Intrusão        │
│                                      │  │  ○ Contagem        │
│  [Limpar] [Cancelar] [Salvar ROI]   │  │  ○ LPR             │
└──────────────────────────────────────┘  └────────────────────┘
```

- Polígonos em cores distintas por tipo (accent para intrusão, verde para contagem, amber para LPR)
- ROI selecionada fica com pontos arrastáveis
- Coordenadas normalizadas 0.0–1.0 (independentes da resolução)
- Config específica por tipo aparece no painel direito

**Checklist:**
- [x] `pages/ROIEditorPage.tsx`
- [x] Canvas com SVG overlay (polígonos interativos)
- [x] `hooks/useROIEditor.ts` — lógica de desenho/edição de polígono (inline na página)

---

#### Tela: MosaicPage

**Arquivo:** `pages/MosaicPage.tsx`
**Referência direta:** `legado/frontend/src/pages/MosaicPage.tsx`

**Toolbar:**
- Layout picker: `1×1` `2×2` `3×3` `4×4` `1+3` `2+4` (pill segmented)
- Botão Tela Cheia (fullscreen API)
- Botão "Salvar layout" → persiste no localStorage

**Grid de slots:**
- Slot vazio: fundo escuro + ícone + select de câmera
- Slot com câmera: `VideoPlayer` fullwidth + overlay com nome
- Hover: botão ✕ para limpar slot
- Drag-and-drop entre slots (v2)

**Checklist:**
- [x] `pages/MosaicPage.tsx`
- [x] Persist layout no localStorage
- [x] Fullscreen API

---

#### Tela: RecordingsPage

**Arquivo:** `pages/RecordingsPage.tsx`
**Referência direta:** `legado/frontend/src/pages/RecordingsPage.tsx`

**Layout:** seletor câmera + navegador data / player + timeline + lista segmentos / modal clip

```
[Câmera: select] [← 30/03] [Calendário] [31/03 →]
─────────────────────────────────────────────────────
┌────────────────────────┐  ┌────────────────────────┐
│                        │  │  Timeline 30/03/2026   │
│  [VideoPlayer 16:9]    │  │  42 segmentos gravados │
│  Entrada Principal     │  │                        │
│                        │  │  00:00──────────23:59  │
│                        │  │  ███░░░░░██████░░░███  │ ← acc
│                        │  │  [═══════]              │ ← clip range amber
│                        │  │                        │
│  [✂ Criar Clip]        │  │  Lista de segmentos:   │
└────────────────────────┘  │  ● 00:00–01:00  60min  │
                             │  ● 01:00–02:00  60min  │
                             │  ...                   │
                             └────────────────────────┘
```

- Timeline clicável: click define centro do clip range; drag handles para ajustar
- Segmentos em azul accent, área de clip selecionada em amber
- Download de segmento individual: click no segmento → botão download
- `GET /api/v1/cameras/{id}/timeline?date=2026-03-30` → segments agrupados por hora

**Checklist:**
- [x] `pages/RecordingsPage.tsx`
- [x] `components/recordings/TimelineBar.tsx` — barra 24h com drag handles para clip range
- [x] Download de segmento individual

---

#### Tela: EventsPage

**Arquivo:** `pages/EventsPage.tsx`
**Base:** `legado/frontend/src/pages/DetectionsPage.tsx`

**Toolbar:**
- Busca por placa (ALPR)
- Filtro câmera (select)
- Filtro tipo de evento (multi-select)
- Date range: De — Até
- `[↓ Exportar CSV]`

**Tabela:**
- Colunas: Tipo · Placa · Confiança · Câmera · ROI · Data/Hora · Ações
- Row click → modal lateral com detalhes:
  - Tipo de evento + badge
  - Thumbnail do frame (se disponível)
  - JSON do payload expandível
  - Link "Ver na timeline" → `/recordings` na data/hora do evento
  - Link "Criar clip" (abre modal clip pré-preenchido)

**Paginação:** cursor-based, botões Anterior/Próximo + "Página X de Y"

**Checklist:**
- [x] `pages/EventsPage.tsx`
- [x] Modal de detalhe com thumbnail e payload
- [x] Export CSV (blob download via axios)

---

#### Tela: AnalyticsPage

**Arquivo:** `pages/AnalyticsPage.tsx`
**Base:** `legado/frontend/src/pages/AnalyticsPage.tsx`

**Tabs:** Visão Geral · Tráfego · Eventos · Mapa de Calor

**Tab: Visão Geral**
- KPI cards: Total detecções semana · Câmeras com IA · ROIs ativas · Alertas críticos
- BarChart: top 5 câmeras por volume de eventos (últimos 7 dias)
- LineChart: tendência por tipo (intrusion vs people vs vehicle)
- Date range picker global (afeta todos os charts)

**Tab: Tráfego**
- Seletor câmera + ROI + período
- AreaChart: pessoas/veículos por hora do dia (médias)
- BarChart: comparativo dia a dia
- `GET /api/v1/analytics/summary?camera_id=X&period=7d`

**Tab: Eventos**
- Tabela de eventos analytics (filtrada por plugin/ROI)
- Same component que EventsPage mas filtrado

**Tab: Mapa de Calor** *(v2 — pós-MVP)*
- Canvas sobre snapshot da câmera
- Células coloridas por densidade de detecções

**Checklist:**
- [x] `pages/AnalyticsPage.tsx`
- [x] Date range picker reutilizável `components/ui/DateRangePicker.tsx`
- [x] `services/analytics.ts` — summary + ROI events

---

#### Tela: AgentsPage

**Arquivo:** `pages/AgentsPage.tsx`
**Sem referência no legado — nova tela.**

**Layout:** toolbar + cards de agents

```
[+ Novo Agent]  [Busca]
────────────────────────────────────────────────────
┌─────────────────────────┐  ┌─────────────────────┐
│ ● Agent SP-01           │  │ ● Agent RJ-02        │
│ Online · v1.2.0         │  │ Offline há 2h        │
│ 5 câmeras · 0 falhas    │  │ 3 câmeras            │
│ Heartbeat: agora        │  │ Heartbeat: 14:22     │
│ [Ver câmeras] [Revogar] │  │ [Ver câmeras][Revog] │
└─────────────────────────┘  └─────────────────────┘
```

**Modal Novo Agent:**
- Nome do agent → `POST /api/v1/agents`
- Resultado: mostra API Key (UMA vez) + comando docker para copiar
- `Copy to clipboard` para API Key e para o comando completo

**Modal Detalhes (clique no card):**
- Informações: versão, uptime, streams rodando/falhando
- Lista de câmeras atribuídas a este agent
- Histórico de heartbeats (últimas 24h — sparkline)
- Botão "Revogar" com confirmação

**Checklist:**
- [x] `pages/AgentsPage.tsx`
- [x] Modal de criação com exibição única da API key
- [x] Comando docker auto-gerado com variáveis

---

#### Tela: NotificationsPage

**Arquivo:** `pages/NotificationsPage.tsx`
**Sem referência direta no legado.**

**Tabs:** Regras · Logs

**Tab: Regras**
- Lista de `NotificationRule` com toggle ativo/inativo
- `+ Nova Regra` → modal:
  ```
  Nome:         [_________________]
  Padrão evento:[alpr.*          ] ← fnmatch, helper: select comum
  URL destino:  [https://...      ]
  Segredo HMAC: [_________________] [🔄 Gerar]
  [Salvar]
  ```
- Padrões pré-definidos no select: `alpr.*` · `analytics.intrusion.*` · `camera.offline` · `*`

**Tab: Logs**
- Tabela: Regra · Evento · Status (✅/❌) · HTTP Code · Data
- Filtro: regra, status, date range
- Click → modal com request/response body (para debug)
- Retry manual em falhas

**Checklist:**
- [x] `pages/NotificationsPage.tsx`
- [x] Gerador de segredo HMAC (crypto.randomBytes via `/api` ou frontend random)

---

#### Tela: UsersPage

**Arquivo:** `pages/UsersPage.tsx`
**Base:** `legado/frontend/src/pages/UsersPage.tsx`

- Tabela: Avatar · Nome · Email · Role badge · Ativo · Último acesso · Ações
- `+ Novo Usuário` → modal com react-hook-form + Zod: email, nome, senha, role (admin/operator/viewer)
- Role badges: Admin (accent) · Operador (warning) · Visualizador (default)
- Desativar usuário (toggle + confirmação)
- Reset de senha (gera nova senha temporária)

**Checklist:**
- [x] `pages/UsersPage.tsx`

---

#### Tela: SettingsPage

**Arquivo:** `pages/SettingsPage.tsx`
**Base:** `legado/frontend/src/pages/SettingsPage.tsx`

**Tabs:** Instância · Segurança · Integrações · Sistema

**Tab: Instância**
- Nome do sistema, cor primária (live preview), logo upload, favicon
- `PATCH /api/v1/tenants/me`

**Tab: Segurança**
- Alterar senha do usuário logado
- Sessões ativas (listagem de refresh tokens) com revogação

**Tab: Integrações**
- Webhooks de saída (atalho para NotificationsPage)
- Chave ALPR para câmeras Hikvision/Intelbras (instruções de configuração)
- URL de webhook de entrada: `https://vms.host/webhooks/alpr/hikvision`

**Tab: Sistema**
- Health check visual (DB · Redis · RabbitMQ · MediaMTX)
- Storage: uso de disco · retenção média configurada
- Versão do VMS + backend + uptime

**Checklist:**
- [x] `pages/SettingsPage.tsx`
- [x] Color picker com live preview de `--accent`
- [x] Logo upload com preview + crop (ou simples URL)

---

### 9.5 Estado Global e SSE Real-time

- [x] `store/authStore.ts` — user, tokens, setAuth(), logout(), persist localStorage
- [x] `store/themeStore.ts` — theme, primaryColor(), side effects em CSS var + favicon + title
- [x] `store/cameraStore.ts` — cache de status cameras (online/offline) atualizado via SSE
- [x] `hooks/useSSE.ts` — implementação:
  ```ts
  // Conecta /sse/events com JWT
  // EventSource nativo (ou polyfill se necessário)
  // Tipos de eventos que atualizam estado:
  //   camera.online  → cameraStore.setOnline(camera_id)
  //   camera.offline → cameraStore.setOffline(camera_id)
  //   alpr.detected  → toast de alerta se regra de notificação local
  //   analytics.*    → atualiza counters no dashboard
  // Reconexão automática com backoff exponencial
  ```

---

### 9.6 Testes Frontend

- [x] Vitest config + React Testing Library setup
- [x] `tests/unit/components/VideoPlayer.test.tsx` — render, HLS init, states
- [x] `tests/unit/components/AddCameraWizard.test.tsx` — navegação de passos, validação
- [x] `tests/unit/components/OnboardingWizard.test.tsx` — trigger, progresso, skip
- [x] `tests/unit/hooks/useSSE.test.ts` — connect, event handling, reconnect
- [x] `tests/unit/services/api.test.ts` — interceptors, refresh
- [ ] `tests/e2e/` (Playwright — pós-MVP):
  - Login + redirect
  - Criar câmera via wizard
  - Visualizar stream

---

### 9.7 Build & Integração Docker

- [x] `frontend/Dockerfile` — multi-stage: `node:20-alpine` build → `nginx:1.25-alpine` serve
- [x] `infra/nginx/nginx.conf` — adicionar `location /` serving frontend, SPA fallback `try_files $uri /index.html`
- [x] `docker-compose.yml` — adicionar serviço `frontend` (build + nginx) ou servir o dist via nginx existente
- [x] Vite proxy em dev: `/api` → `localhost:8000`, sem CORS issues
- [x] `make dev-fe` — `vite dev` com hot reload
- [x] `make build-fe` — `vite build` + verifica bundle size

---

### 9.8 Critérios de Aceite Frontend

**Visual:**
- [x] Dark mode correto (CSS vars idênticas ao legado)
- [x] Responsive: funciona em 1280px (desktop operador) e 768px (tablet)
- [x] Sem flash of unstyled content (CSS vars no `:root`)
- [x] Scroll suave, animações fade-in em page transitions

**Funcional:**
- [x] Login → JWT armazenado → refresh automático → logout limpa store
- [x] Onboarding aparece uma única vez em accounts novas
- [x] AddCamera wizard: todos os 6 protocolos, validação por passo, revisão antes de criar
- [x] VideoPlayer: HLS com token, fallback WebRTC, "Sem sinal" em erro
- [x] Mosaic: 6 layouts, persist localStorage, fullscreen
- [x] Timeline recordings: clicável, create clip com time range
- [x] SSE: camera.online/offline atualiza dot sem refresh
- [x] ALPR event chega via SSE → toast com placa detectada

---

## Progresso Geral

```
Sprint 0  ████████████  ✅ Estrutura + Docs
Sprint 1  ████████████  ✅ IAM + Foundation (51 testes)
Sprint 2  ████████████  ✅ Cameras + Agents + ONVIF + multi-protocol
Sprint 3  ████████████  ✅ Streaming + Recordings + viewer auth + RTMP push
Sprint 4  ████████████  ✅ Events + ALPR (42 testes + 3 BDD)
Sprint 5  ████████████  ✅ Notifications + Event Bus + SSE + Health
Sprint 6  ████████████  ✅ Edge Agent + WebSocket push + STUN/TURN docs
Sprint 7  ████████████  ✅ Analytics (4 plugins) + ROI events + summary
Sprint 8  ████████████  ✅ Security + Polish + nginx auth + ARQ DLQ
Sprint 9  ████████░░░░  ✅ Frontend (telas + componentes + testes unitários)
```

---

## Convenções

### Commits
```
tipo(contexto): descrição em português

feat(cameras): adicionar suporte a câmeras RTMP push e ONVIF
feat(streaming): implementar viewer token para HLS e WebRTC
feat(agent): adicionar config push via WebSocket
fix(streaming): corrigir verify_publish_token (era TODO)
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
