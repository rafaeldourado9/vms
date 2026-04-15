# VMS — Plano de Refatoração: Core + Analytics Plugins Standalone

> Criado: 2026-04-10  
> Última atualização: 2026-04-13  
> Status: **Em execução — 72% completo**

---

## 1. Contexto e Motivação

O VMS precisa garantir que seu **core funcione de forma robusta e independente**, cobrindo os requisitos essenciais da plataforma:

1. Streaming (RTSP, RTMP, HLS, WebRTC)
2. Persistência e gravação de todas as câmeras
3. Webhooks de entrada (câmera → VMS, payloads Hikvision e Intelbras)
4. Câmeras: suporte exclusivo a Hikvision e Intelbras
5. CRUD e gerenciamento de usuários
6. Relatórios
7. Protocolos IP: RTSP e RTMP

Analytics (inteligência em câmeras burras) é uma **camada opcional** que se conecta ao core via contrato público de API. Cada plugin roda em sua própria hospedagem e não tem dependência do código interno do VMS.

---

## 2. Diagnóstico do Estado Atual (Auditoria 2026-04-13)

### O que funciona bem

- ✅ Core API (FastAPI) com **17 bounded contexts** implementados
- ✅ MediaMTX para RTSP/RTMP/HLS/WebRTC — provisionamento automático no startup
- ✅ Edge agent completo (HTTP polling + WebSocket config push + stream manager)
- ✅ **9 plugins de analytics** (intrusion, people_count, vehicle_count, lpr, face_recognition, fire_smoke, ppe, biker, horse_cart)
- ✅ Frontend com **20 páginas** (incluindo Audit, Billing, LGPD, Reports, SystemHealth)
- ✅ **24 migrations** Alembic aplicáveis
- ✅ **363+ testes** (unit, integration, BDD) no backend
- ✅ Webhooks públicos: Hikvision, Intelbras, Smart Events unificados
- ✅ ISAPI Router + Client para Hikvision
- ✅ SSE em tempo real
- ✅ ARQ Worker com 4 tasks + cron jobs
- ✅ Rate limiting (slowapi), middleware de correlation ID, audit action
- ✅ VOD Service completo (HLS on-demand)
- ✅ Reports com 7 templates HTML + WeasyPrint

### Problemas identificados

| Problema | Impacto | Prioridade |
|----------|---------|------------|
| Zero testes para Audit, Billing, LGPD, Reports, ISAPI | Risco de regressão altíssimo | 🔴 Crítico |
| Frontend: apenas 3 testes unitários | Nenhuma página testada | 🔴 Crítico |
| Decorator `@audit_action` não aplicado em todos os endpoints | Audit trail incompleto | 🟡 Importante |
| Exportação forense não implementada como endpoint | Cadeia de custódia parcial | 🟡 Importante |
| Batch Analytics Worker separado não existe no API | Processamento offline depende do analytics service | 🟡 Importante |
| HA/DR (Sprint 15) zero iniciado | Sem redundância | 🟢 Pós-MVP |
| Nginx config precisa verificar se serve frontend dist | Deploy pode falhar | 🟡 Importante |

---

## 3. Arquitetura Target

```
┌─────────────────────────────────────────────────────────┐
│                     VMS CORE PLATFORM                   │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐             │
│  │ API :8000│  │ MediaMTX │  │  Worker   │             │
│  │ FastAPI  │  │RTSP/RTMP │  │  (ARQ)    │             │
│  └────┬─────┘  └────┬─────┘  └───────────┘             │
│       │              │                                  │
│  ┌────▼──────────────────────────────────┐             │
│  │  PostgreSQL  │  Redis  │  RabbitMQ*   │             │
│  └───────────────────────────────────────┘             │
│                   * opcional                            │
└────────────────────────┬────────────────────────────────┘
                         │  Contrato Público de Plugin
           ┌─────────────┼─────────────┐
           │             │             │
    ┌──────▼─────┐ ┌─────▼──────┐ ┌───▼───────────┐
    │  Plugin A  │ │  Plugin B  │ │   Plugin C    │
    │  intrusion │ │  LPR       │ │  people_count │
    │  (próprio  │ │  (próprio  │ │  (próprio     │
    │   hosting) │ │   hosting) │ │   hosting)    │
    └────────────┘ └────────────┘ └───────────────┘
```

**Regra central:** O VMS Core não conhece modelos de IA, ROIs nem lógica de detecção. Plugins são serviços externos que consomem streams e postam eventos via API pública.

---

## 4. Contrato Público de Plugin

O VMS expõe 3 endpoints exclusivos para plugins. Autenticação via **API Key** criada pelo operador no VMS e configurada no ambiente do plugin.

```
# 1. Plugin solicita token de stream (acesso RTSP ao MediaMTX)
GET /api/v1/plugins/stream-token?camera_id={uuid}
Authorization: Agent <api_key>
→ {
    "rtsp_url": "rtsp://token@mediamtx:8554/tenant-1/cam-42",
    "token": "...",
    "expires_at": "2026-04-10T12:00:00Z"
  }

# 2. Plugin posta evento detectado
POST /api/v1/events/
Authorization: Agent <api_key>
Body: {
  "camera_id": "uuid",
  "event_type": "intrusion.detected",
  "confidence": 0.92,
  "payload": { ...qualquer estrutura... }
}
→ { "id": "uuid", "status": "accepted" }

# 3. Plugin lista câmeras ativas do tenant
GET /api/v1/plugins/cameras
Authorization: Agent <api_key>
→ [{ "id": "uuid", "name": "Entrada", "stream_protocol": "rtsp_pull" }]
```

Esses são os **únicos pontos de contato** entre o VMS e qualquer plugin. Sem imports compartilhados, sem rede interna, sem endpoints internos.

---

## 5. Fases de Execução — Status Atualizado

---

### ✅ Fase 1 — Limpeza do Core API [CONCLUÍDA]

**Objetivo:** Remover acoplamento analytics do core. Garantir os 7 requisitos funcionando limpos.

#### 1.1 — Remover `analytics_config` do core

- [x] `/api/src/vms/analytics_config/` removido
- [x] `analytics_internal_router` removido do `main.py`
- [x] Migration `005_remove_roi_table.py` criada e aplicada
- [x] ROIs movidas para bounded context `analytics/` próprio

#### 1.2 — Tornar RabbitMQ opcional

- [x] `core/event_bus.py`: conexão envolta em try/except no lifespan
- [x] Log warning se não conectar — core continua funcionando via Redis/SSE
- [x] Publicação de eventos: no-op silencioso se RabbitMQ não estiver disponível

#### 1.3 — Auditoria dos 7 requisitos core

| Requisito | Status | Verificação |
|-----------|--------|------------|
| Streaming | ✅ | RTSP pull + RTMP push + HLS + WebRTC via MediaMTX |
| Persistência/Gravação | ✅ | MediaMTX grava em `/recordings/{tenant_id}/cam-{id}/` |
| Webhooks entrada | ✅ | `POST /webhooks/hik_pro_connect` + `/webhooks/intelbras_events` |
| Câmeras | ✅ | Hikvision + Intelbras nos normalizers (6 normalizers) |
| CRUD usuários | ✅ | Login, criação, roles admin/operator/viewer |
| Relatórios | ✅ | 5 tipos de relatório + 7 templates HTML |
| Protocolos | ✅ | RTSP, RTMP, ONVIF no schema de câmera |

#### Arquivos modificados

```
api/src/vms/main.py                       ← remove analytics_config router ✅
api/src/vms/analytics_config/             ← deletado ✅
api/src/vms/core/event_bus.py             ← RabbitMQ opcional ✅
api/migrations/versions/005_remove_roi.py ← criada ✅
```

---

### ✅ Fase 2 — Plugin Contract no Core API [CONCLUÍDA]

**Objetivo:** Adicionar os 3 endpoints do contrato de plugin como bounded context próprio.

#### 2.1 — Stream token endpoint

- [x] `GET /api/v1/plugins/stream-token` — valinda API key, gera JWT, retorna RTSP URL
- [x] Verifica `camera_id` pertence ao tenant da key
- [x] Token JWT de curta duração para MediaMTX

#### 2.2 — Cameras list endpoint

- [x] `GET /api/v1/plugins/cameras` — lista câmeras ativas do tenant

#### 2.3 — Event ingest via plugin

- [x] `POST /api/v1/events/` aceita `event_type` livre
- [x] `payload: dict` arbitrário — sem validação rígida
- [x] Origem registrada via API key

#### Arquivos novos/modificados

```
api/src/vms/plugins/           ← criado ✅
api/src/vms/plugins/router.py  ← stream-token + cameras ✅
api/src/vms/plugins/service.py ← lógica de token ✅
api/src/vms/plugins/schemas.py ← request/response schemas ✅
api/src/vms/plugins/ports.py   ← port pattern ✅
api/src/vms/main.py            ← plugins_router registrado ✅
```

---

### ✅ Fase 3 — Analytics Service como Plugin Real [CONCLUÍDA]

**Objetivo:** Transformar o `analytics/` em serviço standalone que usa apenas o contrato público.

#### 3.1 — Remover dependência de `/internal/rois/`

- [x] `vms_client.py`: `get_rois()` removido
- [x] Plugins gerenciam config local (env vars / YAML)
- [x] `core/config.py` usa `VMS_API_KEY` para auth

#### 3.2 — Usar endpoint público de câmeras

- [x] `orchestrator.py`: usa `GET /api/v1/plugins/cameras`
- [x] Autentica com `VMS_API_KEY`

#### 3.3 — Usar stream token para acessar MediaMTX

- [x] `frame_source.py`: busca token antes de conectar RTSP
- [x] URL montada: `rtsp://{token}@mediamtx:8554/{path}`

#### 3.4 — Postar eventos via API pública

- [x] `vms_client.py`: `post_event()` usa `POST /api/v1/events/`
- [x] Sem referências a endpoints internos

#### 3.5 — Shared Inference + GPU Arbiter + Detection Cache

- [x] `core/shared_inference.py` — 1 inferência → N plugins
- [x] `core/gpu_check.py` — verifica GPU antes de batch
- [x] `core/detection_cache.py` — cache de detecções por ROI
- [x] `core/metrics.py` — métricas Prometheus

#### Arquivos modificados

```
analytics/src/analytics/core/vms_client.py    ← usa endpoints públicos ✅
analytics/src/analytics/core/orchestrator.py  ← usa cameras endpoint público ✅
analytics/src/analytics/core/frame_source.py  ← usa stream token ✅
analytics/src/analytics/core/config.py        ← VMS_API_KEY ✅
analytics/src/analytics/core/shared_inference.py ← compartilhado ✅
analytics/src/analytics/core/gpu_check.py     ← GPU check ✅
analytics/src/analytics/core/detection_cache.py ← cache ✅
analytics/src/analytics/core/metrics.py       ← métricas ✅
analytics/config/                             ← pasta criada ✅
```

---

### ✅ Fase 4 — Frontend Cleanup [CONCLUÍDA]

**Objetivo:** Frontend cobre core + funcionalidades gov (Audit, Billing, LGPD, Reports).

#### Páginas mantidas (20 páginas)

| Página | Status | Observação |
|--------|--------|------------|
| `LoginPage` | ✅ | Auth + refresh token |
| `DashboardPage` | ✅ | Widgets de analytics incluídos |
| `CamerasPage` | ✅ | Grid + list view |
| `CameraDetailPage` | ✅ | Tabs: Ao Vivo, Info, ROIs, Eventos, Clips |
| `MosaicPage` | ✅ | 6 layouts + fullscreen |
| `RecordingsPage` | ✅ | Timeline + forensic export |
| `EventsPage` | ✅ | Filtros + export CSV |
| `NotificationsPage` | ✅ | Regras + logs |
| `UsersPage` | ✅ | CRUD + roles |
| `SettingsPage` | ✅ | Instância, Segurança, Integrações |
| `AgentsPage` | ✅ | Cards + API key + Docker command |
| `ROIManagementPage` | ✅ | ROI editor + polygon editor |
| `TacticalViewPage` | ✅ | Mapa com pins + sidebar |
| `ReportsPage` | ✅ | Geração + download PDF |
| `AuditPage` | ✅ | Tabela de audit logs + filtros |
| `BillingPage` | ✅ | Planos, licenças, consumo |
| `LGPDPage` | ✅ | Consentimento, retenção, RIPD |
| `SystemHealthPage` | ✅ | Dashboard de saúde gov |
| `AnalyticsDashboardPage` | ✅ | Gráficos + métricas |
| `AnalyticsCatalogPage` | ✅ | Catálogo de plugins |

#### Páginas removidas (conforme planejamento original)

| Página | Status | Motivo |
|--------|--------|--------|
| `ROIEditorPage` (antiga) | ✅ Removida | Substituída por `ROIManagementPage` |
| `AnalyticsPage` (antiga) | ✅ Removida | Substituída por `AnalyticsDashboardPage` + `AnalyticsCatalogPage` |

#### Componentes existentes

```
✅ UI: Modal, Badge, Spinner, Tooltip, Confirm, DateRangePicker
✅ Camera: VideoPlayer, DetectionOverlay, CameraCard, RecordingPlayer, Thumbnail, CameraTimeline
✅ ROI: PolygonEditor, ROIEditorPanel, ROIListPanel, PluginConfigForm
✅ Wizard: OnboardingWizard, AddCameraWizard
✅ Map: MapTimelinePanel, ModernTimeline, TacticalTimelineModal
✅ Recording: ForensicExportModal, CustodyChainViewer, IntegrityBadge
✅ Hooks: useSSE, usePermission, useTheme, useConfirm, useOnboarding, useConnectionTest
✅ Stores: authStore, themeStore, cameraStore
✅ Services (15): api, auth, cameras, agents, recordings, events, notifications, analytics,
                  dashboard, users, vod, reports, audit, billing, lgpd, health
```

#### Arquivos modificados

```
frontend/src/App.tsx                   ← 20 rotas registradas ✅
frontend/src/pages/DashboardPage.tsx   ← widgets analytics incluídos ✅
frontend/src/pages/CameraDetailPage.tsx ← tabs completas ✅
frontend/src/components/layout/Sidebar.tsx ← nav items atualizados ✅
```

---

### ✅ Fase 5 — Relatórios (Reports) [CONCLUÍDA — CÓDIGO]

**Objetivo:** Endpoint + UI de relatórios com PDF gerado via WeasyPrint.

#### API

- [x] `GET /api/v1/reports` — lista relatórios do tenant
- [x] `POST /api/v1/reports` — cria solicitação de relatório (async via ARQ)
- [x] `GET /api/v1/reports/{id}` — status do relatório
- [x] `GET /api/v1/reports/{id}/download` — stream do PDF
- [x] 5 tipos: events_summary, cameras_status, recordings_coverage, audit_trail, analytics_events
- [x] Templates HTML: 7 templates + CSS base
- [x] SHA-256 do PDF calculado e persistido
- [x] ARQ task `task_generate_report` para geração assíncrona

#### Frontend

- [x] `ReportsPage.tsx` — geração sob demanda + histórico + download
- [x] `services/reports.ts` — API client
- [x] Adicionada no Sidebar como "Relatórios"

#### Arquivos implementados

```
api/src/vms/reports/domain.py          ✅
api/src/vms/reports/models.py          ✅
api/src/vms/reports/repository.py      ✅
api/src/vms/reports/service.py         ✅
api/src/vms/reports/pdf_generator.py   ✅
api/src/vms/reports/schemas.py         ✅
api/src/vms/reports/router.py          ✅
api/src/vms/reports/tasks.py           ✅
api/src/vms/reports/templates/         ✅ (7 templates HTML + CSS)
frontend/src/pages/ReportsPage.tsx     ✅
frontend/src/services/reports.ts       ✅
```

---

## 6. Resumo de Mudanças por Serviço

### API (`/api/`)

| Ação | Alvo | Status |
|------|------|--------|
| ✅ Removido | `analytics_config/` (pasta completa) | Concluído |
| ✅ Removido | `analytics_internal_router` do `main.py` | Concluído |
| ✅ Adicionado | `plugins/` (bounded context — 3 endpoints) | Concluído |
| ✅ Adicionado | `reports/` (bounded context — relatórios PDF) | Concluído |
| ✅ Adicionado | `audit/` (bounded context — audit trail) | Concluído |
| ✅ Adicionado | `billing/` (bounded context — licenças + planos) | Concluído |
| ✅ Adicionado | `lgpd/` (bounded context — compliance LGPD) | Concluído |
| ✅ Adicionado | `vod/` (bounded context — VOD HLS) | Concluído |
| ✅ Modificado | `main.py` — 18 routers registrados | Concluído |
| ✅ Modificado | `core/event_bus.py` — RabbitMQ opcional | Concluído |
| ✅ Migration | 24 migrations (001–021) | Concluído |
| ❌ Pendente | Testes para audit, billing, lgpd, reports, isapi | **Falta** |

### Analytics (`/analytics/`)

| Ação | Alvo | Status |
|------|------|--------|
| ✅ Modificado | `vms_client.py` — usa API pública | Concluído |
| ✅ Modificado | `orchestrator.py` — cameras endpoint público | Concluído |
| ✅ Modificado | `frame_source.py` — usa stream token | Concluído |
| ✅ Modificado | `config.py` — VMS_API_KEY | Concluído |
| ✅ Adicionado | `shared_inference.py` — frame compartilhado | Concluído |
| ✅ Adicionado | `gpu_check.py` — GPU arbiter | Concluído |
| ✅ Adicionado | `detection_cache.py` — KV cache por ROI | Concluído |
| ✅ Adicionado | `metrics.py` — métricas | Concluído |
| ✅ Adicionado | 9 plugins completos | Concluído |
| ⚠️ Pendente | Testes completos (apenas 5 arquivos de teste) | **Parcial** |

### Frontend (`/frontend/`)

| Ação | Alvo | Status |
|------|------|--------|
| ✅ Deletado | `pages/ROIEditorPage.tsx` (antiga) | Concluído |
| ✅ Deletado | `pages/AnalyticsPage.tsx` (antiga) | Concluído |
| ✅ Adicionado | `pages/ReportsPage.tsx` | Concluído |
| ✅ Adicionado | `pages/AuditPage.tsx` | Concluído |
| ✅ Adicionado | `pages/BillingPage.tsx` | Concluído |
| ✅ Adicionado | `pages/LGPDPage.tsx` | Concluído |
| ✅ Adicionado | `pages/SystemHealthPage.tsx` | Concluído |
| ✅ Adicionado | `pages/AnalyticsDashboardPage.tsx` | Concluído |
| ✅ Adicionado | `pages/AnalyticsCatalogPage.tsx` | Concluído |
| ✅ Adicionado | `services/reports.ts`, `audit.ts`, `billing.ts`, `lgpd.ts`, `health.ts` | Concluído |
| ✅ Modificado | `App.tsx` — 20 rotas | Concluído |
| ❌ Pendente | Testes (apenas 3 testes unitários) | **Falta ~30 testes** |

### Infrastructure (`/infra/`)

| Ação | Alvo | Status |
|------|------|--------|
| ✅ Modificado | `docker-compose.yml` — analytics como serviço opcional | Concluído |
| ✅ Modificado | `mediamtx.yml` — hooks + provisionamento | Concluído |
| ✅ Adicionado | `worker.py` — ARQ com 4 tasks + cron | Concluído |
| ⚠️ Pendente | HA setup (load balancer, replica, sentinel) | **Pós-MVP** |

---

## 7. Ordem de Execução — Progresso Real

```
✅ Fase 1  Core Cleanup          — CONCLUÍDA
✅ Fase 2  Plugin Contract       — CONCLUÍDA
✅ Fase 3  Analytics Refactor    — CONCLUÍDA
✅ Fase 4  Frontend Cleanup      — CONCLUÍDA
✅ Fase 5  Reports               — CONCLUÍDA (código)

⏳ PRÓXIMAS ETAPAS (pós-refatoração):
⚠️ Sprint 10 — Testes Audit Trail          — 0/30 testes
⚠️ Sprint 11 — Testes ISAPI + Forense      — 0/25 testes
⚠️ Sprint 13 — Testes Billing/Licenças     — 0/25 testes
⚠️ Sprint 14 — Testes LGPD + Anon cron     — 0/25 testes
⚠️ Sprint 15 — Testes Reports + Async      — 0/20 testes
⚠️ Sprint 16 — Frontend testes unitários   — 3/~33 testes
⚠️ Sprint 17 — Frontend Polish & UX        — código: redesenhar telas para bater com backend
⚠️ Sprint 18 — E2E Playwright              — 0/8 cenários
⚠️ Sprint 19 — HA/DR                        — 0% iniciado
```

---

## 8. O que NÃO muda

- ✅ Lógica de câmeras (CRUD, ONVIF, PTZ) — **já implementada**
- ✅ MediaMTX e toda a infra de streaming — **já configurada**
- ✅ Edge agent — **já implementado** (HTTP + WebSocket + stream manager)
- ✅ Sistema de usuários e multi-tenant — **já implementado**
- ✅ Gravação de segmentos e clips — **já implementado**
- ✅ Normalizers Hikvision e Intelbras — **6 normalizers** (incluindo smart events)
- ✅ Sistema de notificações e webhooks de saída — **já implementado**
- ✅ Auth JWT + API Keys — **já implementado**

---

## 9. Checklist de Conclusão — Atualizado

```
[x] Fase 1: analytics_config removido, RabbitMQ opcional, 7 requisitos auditados
[x] Fase 2: /api/v1/plugins/* funcionando (stream-token, cameras, event ingest)
[x] Fase 3: analytics service usando apenas endpoints públicos + shared inference + GPU check
[x] Fase 4: Frontend com 20 páginas, ROI/analytics refatorados, nav atualizada
[x] Fase 5: ReportsPage funcionando com 5 tipos de relatório + 7 templates HTML + WeasyPrint

[ ] Sprint 10: Testes unitários para Audit Service + Repository + Router (~30 testes)
[ ] Sprint 11: Testes ISAPI Client + Forensic Export endpoint (~25 testes)
[ ] Sprint 13: Testes Billing/Licenses + Quota checks (~25 testes)
[ ] Sprint 14: Testes LGPD + Anonymization cron + RIPD (~25 testes)
[ ] Sprint 15: Testes Reports + Async queue (~20 testes)
[ ] Sprint 16: Testes frontend unitários para componentes e hooks (~30 testes)
[ ] Sprint 17: Frontend Polish — redesenhar telas para bater com backend (ver seção 12)
[ ] Sprint 18: Testes E2E Playwright (~8 cenários)
[ ] Sprint 19: HA/DR setup (load balancer, replica, sentinel, backup)
[ ] make test → todos passam com coverage > 80%
[ ] make lint → zero erros
[ ] make typecheck → zero erros mypy
[ ] docker-compose up → stack completa sobe sem erros
[ ] docker-compose up --profile analytics → analytics conecta via API pública
```

---

## 10. Métricas do Projeto (Auditoria 2026-04-13)

| Métrica | Valor |
|---------|-------|
| **Bounded Contexts** | 17 |
| **Routers FastAPI** | 18 |
| **Models SQLAlchemy** | 14 |
| **Services** | 15 |
| **Repositories** | 12 |
| **Migrations Alembic** | 24 |
| **ARQ Tasks** | 4 + 1 cron |
| **Plugins Analytics** | 9 |
| **Páginas Frontend** | 20 |
| **Componentes Frontend** | 30+ |
| **Services Frontend** | 15 |
| **Hooks Frontend** | 6 |
| **Stores Frontend** | 3 |
| **Testes Backend** | ~363 |
| **Testes Frontend** | 3 |
| **Testes Analytics** | ~15 |
| **Testes Edge Agent** | ~15 |
| **Total de Testes** | ~396 |
| **Testes Faltando (estimado)** | ~130 |
| **Linhas de Código (estimado)** | ~25.000+ |
| **Progresso Global** | **~72%** |

---

## 11. Progresso por Sprint Real

```
✅ Sprint 0  — Estrutura + Docs                    100% código  100% testes
✅ Sprint 1  — IAM + Foundation                     100% código  100% testes
✅ Sprint 2  — Cameras + Agents + ONVIF + PTZ       100% código   95% testes
✅ Sprint 3  — Streaming + Recordings + VOD         100% código   90% testes
✅ Sprint 4  — Events + ALPR                        100% código  100% testes
✅ Sprint 5  — Notifications + SSE + Event Bus      100% código  100% testes
✅ Sprint 6  — Edge Agent                           100% código   80% testes
✅ Sprint 7  — Analytics (9 plugins)                100% código   80% testes
✅ Sprint 8  — Security + Polish                    100% código  100% testes
✅ Sprint 9  — Frontend (20 páginas)                 95% código   10% testes
⚠️ Sprint 10 — Audit Trail                          70% código    0% testes  ← FALTA TESTES
⚠️ Sprint 11 — Cadeia Custódia + ISAPI             70% código    0% testes  ← FALTA TESTES + FORENSIC
⚠️ Sprint 12 — Intelbras Smart Events             100% código  100% testes  ✅
⚠️ Sprint 13 — Billing + Licenças                   70% código    0% testes  ← FALTA TESTES
⚠️ Sprint 14 — LGPD Avançado                        70% código    0% testes  ← FALTA TESTES + CRON
⚠️ Sprint 15 — Reports PDF                          65% código    0% testes  ← FALTA TESTES
☐  Sprint 16 — Frontend Tests                        0% código   10% testes  ← TESTES UNITÁRIOS
☐  Sprint 17 — Frontend Polish & UX                  0% código    0% testes  ← REDESENHAR TELAS
☐  Sprint 18 — E2E Playwright                         0% código    0% testes  ← FLUXOS E2E
☐  Sprint 19 — HA/DR                                  0% código    0% testes  ← NÃO INICIADO
```

---

> *"Câmera que grava sem auditoria é câmera que ninguém confia."*

---

## 12. Sprint 17 — Frontend Polish & UX

> **Antes do E2E.** Redesenhar as 20 páginas do frontend para fazerem sentido com o backend atual.
> Esta é uma das **últimas sprints** antes do E2E e do HA/DR.

### Princípios (regras invioláveis)

| Regra | Detalhe |
|-------|---------|
| ❌ NÃO mudar cor primária | `--accent` e variáveis CSS permanecem idênticas |
| ❌ NÃO mudar ícones | Lucide icons existentes, mesmos nomes |
| ❌ NÃO mudar player de vídeo | `VideoPlayer.tsx` permanece com mesmos controles e estilos |
| ❌ NÃO mudar botões existentes | `.btn`, `.btn-primary`, `.btn-ghost`, `.btn-danger` intactos |
| ✅ MANTER tipografia | Mesmas fontes, tamanhos, pesos |
| ✅ CORRIGIR o que não bate com backend | Endpoints, campos, fluxos que não correspondem à API real |
| ✅ MELHORAR UI/UX | Layout, espaçamento, hierarquia visual, responsividade |
| ✅ MELHORAR carregamento | Skeleton screens, lazy loading, Suspense, error boundaries |

### O que será feito (por página)

| Página | Problema | Correção |
|--------|----------|----------|
| `DashboardPage` | Widgets podem não bater com endpoints reais | Ajustar dados exibidos, adicionar skeleton loading |
| `CamerasPage` | Cards podem ter campos inexistentes | Remover campos fantasmas, adicionar loading state |
| `CameraDetailPage` | Tabs podem não corresponder a rotas reais | Verificar cada tab: Ao Vivo (stream-urls), Info (GET camera), ROIs (analytics/rois), Eventos (GET events), Clips (GET clips) |
| `RecordingsPage` | Timeline pode não bater com `GET /timeline` | Ajustar formato da timeline, adicionar forensic export modal |
| `EventsPage` | Filtros podem não corresponder à API | Verificar filtros: camera_id, event_type, from, to, page_size |
| `AuditPage` | Tabela pode não exibir todos os campos | Verificar campos: action, user_email, resource_type, ip_address, result, occurred_at |
| `BillingPage` | Planos/licenças podem ter campos fantasmas | Ajustar para `GET /billing/plans`, `GET /licenses`, quota checks |
| `LGPDPage` | Consentimento pode não bater com endpoints | Verificar: `POST /lgpd/consent`, `GET /lgpd/retention-policies`, `POST /lgpd/generate-ripd` |
| `ReportsPage` | Geração pode não bater com async | Verificar polling de status: `GET /reports/{id}` → pending → ready → download |
| `SystemHealthPage` | Métricas podem não existir no `/health` | Ajustar para `GET /health` real: postgres, redis, mediamtx, cameras_online |
| `AnalyticsDashboardPage` | Gráficos podem usar dados mockados | Conectar com `GET /analytics/summary`, `GET /analytics/events` |
| `AgentsPage` | Pode não exibir versão/uptime | Ajustar para dados reais do agent: version, heartbeat, cameras_count |
| `NotificationsPage` | Regras podem não bater com API | Verificar: `GET/POST /notifications/rules`, pattern matching, HMAC |
| `MosaicPage` | Pode não usar stream-urls corretamente | Verificar `GET /cameras/{id}/stream-urls` para cada slot |
| `TacticalViewPage` | Pins podem não usar lat/lng real | Verificar campos `latitude`, `longitude` da câmera |
| `UsersPage` | CRUD pode não bater com endpoints | Verificar: `GET/POST/PATCH /users`, roles admin/operator/viewer |
| `SettingsPage` | Configurações podem ter campos fantasmas | Ajustar para `PATCH /tenants/me`, health check, storage usage |
| `AnalyticsCatalogPage` | Catálogo pode não bater com plugins reais | Verificar `GET /plugins/catalog`, status por câmera |
| `ROIManagementPage` | ROIs podem não bater com analytics | Verificar `GET/POST/DELETE /analytics/rois` |
| `LoginPage` | Funciona — sem mudanças | Apenas verificar loading state e error handling |

### Skeleton Screens (loading states)

```tsx
// Adicionar em TODAS as páginas que buscam dados:
<SkeletonCard />     — para stat cards
<SkeletonTable />    — para tabelas (events, cameras, audit logs)
<SkeletonChart />     — para gráficos (analytics dashboard)
<SkeletonForm />      — para formulários (settings, billing)
```

### Error Boundaries

```tsx
// Adicionar ErrorBoundary em páginas críticas:
<ErrorBoundary fallback={<PageError onRetry={refetch} />}>
  <DashboardPage />
</ErrorBoundary>
```

### Lazy Loading

```tsx
// Rotas com lazy loading para reduzir bundle inicial:
const AuditPage      = lazy(() => import('@/pages/AuditPage'))
const BillingPage    = lazy(() => import('@/pages/BillingPage'))
const LGPDPage       = lazy(() => import('@/pages/LGPDPage'))
const ReportsPage    = lazy(() => import('@/pages/ReportsPage'))
const SystemHealthPage = lazy(() => import('@/pages/SystemHealthPage'))
```

### Checklist Sprint 17

```
[ ] DashboardPage — dados reais + skeleton + error boundary
[ ] CamerasPage — campos reais + loading state
[ ] CameraDetailPage — tabs verificadas com API real
[ ] RecordingsPage — timeline + forensic export funcionando
[ ] EventsPage — filtros batendo com API
[ ] AuditPage — todos os campos visíveis + filtros
[ ] BillingPage — planos + licenças + quota checks reais
[ ] LGPDPage — consentimento + retenção + RIPD funcionando
[ ] ReportsPage — polling async + download correto
[ ] SystemHealthPage — métricas reais do /health
[ ] AnalyticsDashboardPage — dados reais do analytics
[ ] AgentsPage — version + heartbeat + cameras_count
[ ] NotificationsPage — rules CRUD + pattern matching
[ ] MosaicPage — stream-urls correto por slot
[ ] TacticalViewPage — lat/lng reais
[ ] UsersPage — roles + CRUD correto
[ ] SettingsPage — campos reais do tenant
[ ] AnalyticsCatalogPage — plugins reais
[ ] ROIManagementPage — ROIs funcionando com analytics API
[ ] Lazy loading nas rotas não-críticas
[ ] Skeleton screens em todas as páginas
[ ] Error boundaries em páginas críticas
[ ] Tipografia mantida (mesmas fontes, tamanhos)
[ ] Cores mantidas (--accent inalterado)
[ ] Ícones mantidos (Lucide, mesmos nomes)
[ ] VideoPlayer inalterado
[ ] Botões inalterados (.btn, .btn-primary, .btn-ghost, .btn-danger)
[ ] make build-fe → bundle size aceitável (< 500KB gzipped)
```
