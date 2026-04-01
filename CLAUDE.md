# VMS — Contexto para o Claude Code

> Leia este arquivo antes de qualquer tarefa. Contém visão, arquitetura real,
> decisões tomadas e regras de trabalho.

---

## 1. Visão do Produto

**VMS** (Video Management System) white-label multi-tenant para integradores de segurança
no Brasil. Roda self-hosted (cloud do integrador ou on-prem no cliente).

### Posicionamento

| Eixo | Proposta |
|------|----------|
| Câmeras baratas → inteligentes | Analytics server-side transforma qualquer bullet em câmera com IA |
| Self-hosted / LGPD nativo | Zero dependência de cloud externa — dados ficam no cliente |
| Sem licença por câmera | Modelo por instância/tenant — TCO 80% menor que concorrentes BR |
| Multi-protocolo | RTSP pull, RTMP push, ONVIF — qualquer câmera do mercado |
| Gravação 24/7 alta qualidade | Encoder da câmera, ffmpeg -c copy, armazenamento cíclico por câmera |

### Decisões de produto já fixadas

1. **Analytics em cima de gravações** (não real-time)
   - Câmeras bullet/baratas: plugins YOLOv8 processam os `.mp4` gravados (60s segments)
   - Latência de detecção ~60-120s — aceitável para ALPR, people count, vehicle count
   - Qualidade superior: frames completos sem drops de rede, retry natural via ARQ
   - Economiza 2-3 sprints de infraestrutura de streaming analytics

2. **Exceção: intrusão é real-time** (opt-in por ROI)
   - Câmeras com ROI de `ia_type=intrusion` ativo: analytics service mantém 1fps live
   - Limitado ao conjunto de câmeras que realmente precisam
   - Câmeras caras com ANPR nativo: webhook direto → evento imediato (já existe)

3. **Gravação: encoder da câmera, sem re-encode**
   - `ffmpeg -c copy` no edge agent — copia bitstream puro, zero CPU de encode
   - Qualidade = qualidade da câmera (H.264 ou H.265, sem perda)
   - MediaMTX grava os segmentos e **também serve VOD/playback nativamente**
   - VMS só precisa proxiar o endpoint de playback do MediaMTX com autenticação

4. **Retenção cíclica FIFO por câmera**
   - `retention_days` por câmera (1-90 dias), configurável na criação e editável
   - Upgrade de retenção (ex: 5→15 dias): aplica só ao fim do ciclo atual (não onera storage de surpresa)
   - Downgrade (ex: 15→5 dias): aplica imediatamente, libera disco
   - Implementado via `retention_days_pending` + `retention_pending_from` na Camera

---

## 2. Arquitetura Completa

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           REDE DO CLIENTE (on-prem)                          │
│                                                                               │
│  Câmera IP (RTSP)          Câmera RTMP nativa        Câmera ONVIF             │
│  Hik/Intelbras/Dahua       Reolink, Intelbras         Qualquer ONVIF S        │
│        │                         │                         │                 │
│        │ RTSP pull                │ RTMP push direto        │ RTSP (após probe│
│        ▼                         │                         │                 │
│  ┌─────────────┐                 │                         │                 │
│  │ Edge Agent  │                 │                         │                 │
│  │ ffmpeg      │                 │                         │                 │
│  │ -c copy     │                 │                         │                 │
│  │ (sem re-    │                 │                         │                 │
│  │  encode)    │                 │                         │                 │
│  └──────┬──────┘                 │                         │                 │
│         │ RTMP push              │                         │                 │
└─────────┼────────────────────────┼─────────────────────────┼─────────────────┘
          │                        │                         │
          │                        │  (via VMS cloud/on-prem)│
          ▼                        ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        VMS (cloud ou on-prem do integrador)                  │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                           Nginx                                       │   │
│  │  TLS termination · HSTS · CSP · auth_request para /hls/ /webrtc/    │   │
│  │  /recordings/ protegido por JWT · rate limiting                       │   │
│  └──────┬─────────────────────────────────────────────────────┬─────────┘   │
│         │ /api/v1/*                                            │ /hls/ /webrtc/ /recordings/
│         ▼                                                      ▼             │
│  ┌─────────────────────────────┐          ┌────────────────────────────┐    │
│  │        VMS API              │          │        MediaMTX             │    │
│  │  FastAPI + Uvicorn          │          │                            │    │
│  │  Python 3.12 async          │◄────────►│  :1935  RTMP ingest        │    │
│  │                             │  hooks   │  :8554  RTSP               │    │
│  │  Bounded Contexts:          │          │  :8888  HLS live           │    │
│  │  ├── IAM                    │          │  :8889  WebRTC             │    │
│  │  ├── Cameras                │          │  :9997  API REST           │    │
│  │  ├── Streaming              │          │                            │    │
│  │  ├── Recordings             │          │  Grava segmentos 60s:      │    │
│  │  ├── Events                 │          │  /recordings/              │    │
│  │  ├── Notifications          │          │    tenant-X/               │    │
│  │  ├── Analytics Config       │          │      cam-Y/                │    │
│  │  ├── PTZ                    │          │        2026/04/01/         │    │
│  │  └── SSE                    │          │          14-30-00.mp4      │    │
│  └──────┬──────────────────────┘          │                            │    │
│         │                                 │  VOD/playback nativo:      │    │
│         │                                 │  GET /recording/get?...    │    │
│         │                                 │  → HLS playlist dinâmica   │    │
│         │                                 └────────────────────────────┘    │
│         │                                                                    │
│  ┌──────▼──────────────────────────────────────────────────────────────┐   │
│  │                    Infraestrutura de dados                            │   │
│  │                                                                       │   │
│  │  PostgreSQL 16        Redis 7              RabbitMQ 3                │   │
│  │  ├── tenants          ├── ALPR dedup       topic exchange:           │   │
│  │  ├── users            │   alpr:dedup:      ├── alpr.detected         │   │
│  │  ├── api_keys         │   {cam}:{plate}    ├── camera.online         │   │
│  │  ├── cameras          │   TTL 60s          ├── analytics.intrusion   │   │
│  │  ├── agents           ├── SSE pub/sub      └── system.task_failed    │   │
│  │  ├── stream_sessions  │   tenant:{id}:*                              │   │
│  │  ├── recording_segs   ├── agent config                               │   │
│  │  ├── clips            │   agent:{id}:      ARQ (Redis-backed):       │   │
│  │  ├── vms_events       │   config           ├── index_segment         │   │
│  │  ├── notification_    ├── ARQ queue        ├── analytics_segment     │   │
│  │  │   rules/logs       └── rate limiting    ├── dispatch_webhook      │   │
│  │  └── rois                                  ├── cleanup_segments      │   │
│  │                                            └── apply_pending_ret.    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    Analytics Service (separado)                        │   │
│  │                                                                       │   │
│  │  FastAPI + YOLOv8                                                     │   │
│  │                                                                       │   │
│  │  Modo 1 — Pós-gravação (padrão bullets):                             │   │
│  │    ARQ task analytics_segment(segment_id)                             │   │
│  │      → lê .mp4 do disco                                              │   │
│  │      → ffmpeg extrai frames (ex: 1fps)                               │   │
│  │      → YOLOv8 detect                                                 │   │
│  │      → POST /internal/analytics/ingest/                              │   │
│  │                                                                       │   │
│  │  Modo 2 — Real-time (somente ROIs ia_type=intrusion):               │   │
│  │    RTSP pull 1fps do MediaMTX                                        │   │
│  │    → YOLOv8 detect                                                   │   │
│  │    → POST /internal/analytics/ingest/ (alerta imediato)             │   │
│  │                                                                       │   │
│  │  Plugins: intrusion · people_count · vehicle_count · lpr            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Viewers (browser / app)                               │
│                                                                               │
│  HLS live:    http://vms/hls/tenant-X/cam-Y/index.m3u8?token=<jwt>          │
│  WebRTC live: http://vms/webrtc/tenant-X/cam-Y/whep?token=<jwt>             │
│  VOD/timeline: MediaMTX /recording/get → HLS.js scrubbing                   │
│  Eventos SSE:  GET /api/v1/sse  (JWT, filtrado por tenant)                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Fluxos Principais

### 3.1 Gravação 24/7 e Indexação

```
Câmera → Agent (ffmpeg -c copy) → MediaMTX :1935
                                        │
                                        ├── grava /recordings/tenant-X/cam-Y/YYYY/MM/DD/HH-MM-SS.mp4
                                        │   (segmentos de 60s, encoder original da câmera)
                                        │
                                        ▼ runOnRecordSegmentComplete hook
                              POST /webhooks/mediamtx/segment_ready
                                        │
                                        ▼
                              ARQ: index_segment(segment_id)
                                        │
                                        ├── RecordingSegment no DB
                                        │   (tenant_id, camera_id, started_at, ended_at,
                                        │    file_path, size_bytes, duration_seconds)
                                        │
                                        └── ARQ: analytics_segment(segment_id)  ← novo
                                                  (se câmera tiver ROIs analytics ativos)
```

### 3.2 Timeline / VOD Playback

```
Frontend HLS.js
  │
  │  1. GET /api/v1/cameras/{id}/timeline?date=2026-04-01
  │     → { "14": 60, "15": 58, ... }  (minutos gravados por hora, do DB)
  │
  │  2. Usuário clica em 14:30
  │
  │  3. GET /api/v1/cameras/{id}/vod?from=T&to=T
  │     → VMS proxia MediaMTX GET /recording/get?path=tenant-X/cam-Y&start=T&duration=N
  │     → MediaMTX gera HLS playlist dinâmica dos .mp4 existentes
  │     → VMS injeta token de autenticação
  │
  │  4. HLS.js reproduz → scrubbing funciona nativamente
  │     Nginx valida token em /recordings/ via auth_request
```

### 3.3 ALPR — Três Fluxos

```
Fluxo A — Câmera cara com ANPR nativo (real-time, já implementado ✅)
  Câmera → HTTP webhook → POST /webhooks/alpr/{manufacturer}
    → normalizer → dedup Redis (60s) → VmsEvent → SSE + Notifications

Fluxo B — Câmera bullet (analytics pós-gravação, a implementar)
  Segmento .mp4 indexado → ARQ analytics_segment()
    → YOLOv8 lpr plugin → POST /internal/analytics/ingest/
    → EventService.ingest_alpr() → (mesmo fluxo A a partir do dedup)

Fluxo C — Intrusão real-time (já implementado, opt-in por ROI ✅)
  MediaMTX RTSP → Analytics Service 1fps
    → YOLOv8 intrusion + polígono ROI → alerta imediato
```

### 3.4 Retenção Cíclica

```
Por câmera: retention_days (padrão 7, editável 1-90)

Upgrade (5 → 15 dias):
  retention_days = 5               ← mantém
  retention_days_pending = 15
  retention_pending_from = now() + 5 dias
  ARQ daily: se now() >= retention_pending_from → aplica pending

Downgrade (15 → 5 dias):
  retention_days = 5 imediatamente
  ARQ cleanup → deleta segments onde started_at < now() - 5d

Cleanup task (ARQ periódica):
  DELETE segments WHERE started_at < NOW() - INTERVAL retention_days
  + delete arquivo físico do disco
```

### 3.5 Auth MediaMTX

```
Publish (Agent/câmera → MediaMTX):
  MediaMTX → POST /streaming/publish-auth
    body: { action: "publish", path: "tenant-X/cam-Y", query: "key=abc" }
    VMS valida: stream_key de câmera RTMP push OU API key de agent
    → 200 (aceito) | 401 (rejeitado)

Read (Viewer → MediaMTX):
  Nginx auth_request → GET /streaming/auth-check?token=<jwt>&path=<path>
    VMS valida ViewerToken JWT (claims: camera_id, tenant_id, exp 15min)
    → 200 | 401
```

---

## 4. Path Convention MediaMTX

```
Stream live:  tenant-{tenant_id}/cam-{camera_id}
Gravação:     /recordings/tenant-{tenant_id}/cam-{camera_id}/YYYY/MM/DD/HH-MM-SS.mp4

Exemplos:
  tenant-550e8400/cam-f47ac10b          → stream live
  /recordings/tenant-550e8400/cam-f47ac10b/2026/04/01/14-30-00.mp4
```

---

## 5. Estado dos Sprints

```
Sprint 0   ✅  Estrutura, docs, infra configs
Sprint 1   ✅  IAM + Foundation          (51 testes)
Sprint 2   ✅  Cameras + Agents + ONVIF  (+multi-protocol, +viewer URLs)
Sprint 2.5 ✅  PTZ & ONVIF Avançado      (14 testes, 156 total)
Sprint 3   ✅  Streaming + Recordings    (+viewer auth, RTMP push, download)
Sprint 4   ✅  Events + ALPR             (42 testes + 3 BDD)
Sprint 5   ✅  Notifications + EventBus + SSE + Health
Sprint 6   ✅  Edge Agent                (+WebSocket push, STUN/TURN)
Sprint 7   ✅  Analytics Service         (4 plugins: intrusion, people, vehicle, lpr)
Sprint 8   ✅  Segurança + Polish        (nginx auth, DLQ, structured logging)
Sprint 9   🔲  Frontend                  (React 18 + HLS.js + Recharts)

Pendente (não tem sprint ainda):
  - VOD proxy endpoint + timeline heat map (MediaMTX recording API + auth)
  - retention_days_pending / retention_pending_from na Camera
  - ARQ task apply_pending_retention() diária
  - Analytics em pós-gravação (analytics_segment ARQ task)
```

---

## 6. Arquitetura Hexagonal — Regras Invioláveis

```
Domain      → zero imports externos (sem SQLAlchemy, Redis, FastAPI)
Port        → interface Protocol/ABC, sem implementação
Service     → orquestra domain + ports, sem HTTP/SQL direto
Adapter     → implementa port, conhece o framework externo
Router      → HTTP only, delega 100% ao service
```

Toda query filtra `tenant_id` — sem exceção. Nunca retornar dados de outro tenant.

---

## 7. Convenções de Código

- Python 3.12, `from __future__ import annotations` em todo arquivo
- Pydantic v2, SQLAlchemy 2.0 async
- `ruff` para linting, `mypy` para tipos
- Testes: `pytest-asyncio` modo AUTO, classes `Test*`, fixtures em `conftest.py`
- Migrations: `001_nome.py` sequencial, `down_revision` correto
- Commit: `feat(sprint N): descrição` — commitar só com testes passando

---

## 8. Comandos Úteis

```bash
# Instalar dependências (api)
cd api && pip install -e ".[dev]"

# Rodar testes
cd api && python -m pytest tests/unit/ -v

# Rodar todos os testes
cd api && python -m pytest -v

# Subir stack completa
docker compose up

# Migrations
cd api && alembic upgrade head
```

---

## 9. Decisões Técnicas Fixadas (ADRs)

| Decisão | Escolha | Razão |
|---------|---------|-------|
| Framework API | FastAPI (não Django) | Async nativo, OpenAPI auto, sem overhead |
| Arquitetura | Hexagonal Bounded Contexts | Testabilidade, isolamento, evolução independente |
| Task queue | ARQ (não Celery) | Async-native, Redis-backed, simples |
| Analytics timing | Pós-gravação (não real-time) | Precisão superior, infraestrutura 10x mais simples |
| Encode de vídeo | -c copy no ffmpeg | Zero perda de qualidade, zero CPU de encode |
| VOD playback | MediaMTX nativo (proxy + auth) | Já gera m3u8 dinâmico, sem implementar do zero |
| Retenção | FIFO por timestamp, pending para upgrade | Sem surpresa de custo, downgrade imediato |

---

## 10. Variáveis de Ambiente Críticas

```env
DATABASE_URL=postgresql+asyncpg://vms:vms@postgres:5432/vms
REDIS_URL=redis://redis:6379/0
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
SECRET_KEY=<256-bit random>
MEDIAMTX_API_URL=http://mediamtx:9997
MEDIAMTX_RTMP_URL=rtmp://mediamtx:1935
ENVIRONMENT=production  # desabilita rate limit override em testes
```
