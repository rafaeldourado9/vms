# VMS — Plano de Refatoração: Core + Analytics Plugins Standalone

> Criado: 2026-04-10
> Status: Em planejamento

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

## 2. Diagnóstico do Estado Atual

### O que funciona bem

- Core API (FastAPI) com câmeras, usuários, eventos, gravações, notificações, streaming
- MediaMTX para RTSP/RTMP/HLS/WebRTC
- Edge agent para push de streams locais
- 4 plugins de analytics (intrusion, people_count, vehicle_count, lpr)
- Frontend com 13 páginas

### Problemas identificados

| Problema | Impacto |
|----------|---------|
| `analytics_config` está no core — ROIs são responsabilidade dos plugins | Acoplamento errado no core |
| Analytics service consulta VMS via `/internal/rois/` | Dependência invertida via endpoint interno |
| RabbitMQ como dependência dura | Overhead desnecessário para rotas core |
| Frontend mistura ROIEditorPage e AnalyticsPage com features core | UI acoplada a features que serão dos plugins |
| Sem contrato formal de registro de plugins | Cada plugin futuro exige mudança no core |

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

## 5. Fases de Execução

---

### Fase 1 — Limpeza do Core API

**Objetivo:** Remover acoplamento analytics do core. Garantir os 7 requisitos funcionando limpos.

#### 1.1 — Remover `analytics_config` do core

- Deletar `/api/src/vms/analytics_config/` (pasta completa)
- Remover `analytics_internal_router` do `main.py`
- Criar migration `005_remove_roi_table.py` — drop `regions_of_interest`

#### 1.2 — Tornar RabbitMQ opcional

- `core/event_bus.py`: envolver conexão em try/except no lifespan
- Log warning se não conectar — core continua funcionando via Redis/SSE
- Publicação de eventos: no-op silencioso se RabbitMQ não estiver disponível

#### 1.3 — Auditoria dos 7 requisitos core

| Requisito | Verificação |
|-----------|------------|
| Streaming | RTSP pull + RTMP push + HLS + WebRTC via MediaMTX |
| Persistência/Gravação | MediaMTX grava em `/recordings/{tenant_id}/cam-{id}/` |
| Webhooks entrada | `POST /api/v1/events/webhook/` com normalizers Hikvision e Intelbras |
| Câmeras | Apenas Hikvision e Intelbras nos normalizers |
| CRUD usuários | Login, criação, roles admin/viewer |
| Relatórios | Eventos com filtros + gravações (ver Fase 5) |
| Protocolos | RTSP e RTMP no schema de câmera |

#### Arquivos modificados

```
api/src/vms/main.py                       ← remove analytics_config router
api/src/vms/analytics_config/             ← deletar pasta
api/src/vms/core/event_bus.py             ← RabbitMQ opcional
api/migrations/versions/005_remove_roi.py ← nova migration
```

---

### Fase 2 — Plugin Contract no Core API

**Objetivo:** Adicionar os 3 endpoints do contrato de plugin como bounded context próprio.

#### 2.1 — Stream token endpoint

```
GET /api/v1/plugins/stream-token?camera_id={uuid}
```

- Valida API key (tabela `api_keys` existente)
- Verifica `camera_id` pertence ao tenant da key
- Gera token JWT de curta duração para autenticação no MediaMTX
- Retorna RTSP URL + token

#### 2.2 — Cameras list endpoint

```
GET /api/v1/plugins/cameras
```

- Lista câmeras ativas do tenant
- Plugin usa para descobrir quais streams processar

#### 2.3 — Event ingest via plugin

- `POST /api/v1/events/` já existe — garantir que aceita `event_type` livre
- `payload: dict` arbitrário — sem validação rígida do conteúdo
- Registrar origem como plugin via API key

#### Arquivos novos/modificados

```
api/src/vms/plugins/           ← novo bounded context
api/src/vms/plugins/router.py  ← stream-token + cameras endpoints
api/src/vms/plugins/service.py ← lógica de geração de token
api/src/vms/plugins/schemas.py ← request/response schemas
api/src/vms/main.py            ← registrar plugins_router
```

---

### Fase 3 — Analytics Service como Plugin Real

**Objetivo:** Transformar o `analytics/` em serviço standalone que usa apenas o contrato público.

#### 3.1 — Remover dependência de `/internal/rois/`

- `vms_client.py`: remover `get_rois()` completamente
- Cada plugin gerencia sua própria config local (env vars ou YAML)

```yaml
# analytics/config/intrusion.yaml  (não versionado — por deploy)
plugin: intrusion_detection
cameras:
  - camera_id: "uuid"
    zones:
      - name: "entrada"
        polygon: [[0,0],[100,0],[100,100],[0,100]]
```

#### 3.2 — Usar endpoint público de câmeras

- `orchestrator.py`: substituir chamada interna por `GET /api/v1/plugins/cameras`
- Autenticar com `VMS_API_KEY` na env

#### 3.3 — Usar stream token para acessar MediaMTX

- `frame_source.py`: antes de conectar ao RTSP, buscar token via `GET /api/v1/plugins/stream-token`
- Montar URL: `rtsp://{token}@mediamtx:8554/{path}`

#### 3.4 — Postar eventos via API pública

- `vms_client.py`: `post_event()` usa `POST /api/v1/events/` com a API key
- Remover qualquer referência a endpoints internos

#### Arquivos modificados

```
analytics/src/analytics/core/vms_client.py    ← remove get_rois, usa endpoints públicos
analytics/src/analytics/core/orchestrator.py  ← usa cameras endpoint público
analytics/src/analytics/core/frame_source.py  ← usa stream token
analytics/src/analytics/core/config.py        ← VMS_API_KEY, remove vars internas
analytics/config/                             ← nova pasta, ignorada no git
docker-compose.yml                            ← analytics como serviço opcional
```

---

### Fase 4 — Frontend Cleanup

**Objetivo:** Remover páginas e features não usadas. Frontend cobre apenas o core.

#### Páginas mantidas

| Página | Observação |
|--------|------------|
| `LoginPage` | Sem alteração |
| `DashboardPage` | Remover widgets de analytics/contagem |
| `CamerasPage` | Sem alteração |
| `CameraDetailPage` | Remover aba de Analytics/ROI |
| `MosaicPage` | Sem alteração |
| `RecordingsPage` | Sem alteração |
| `EventsPage` | Mostrar eventos de qualquer tipo, inclusive de plugins |
| `NotificationsPage` | Sem alteração |
| `UsersPage` | Sem alteração |
| `SettingsPage` | Sem alteração |
| `AgentsPage` | Sem alteração |

#### Páginas removidas

| Página | Motivo |
|--------|--------|
| `ROIEditorPage` | ROI é responsabilidade do plugin |
| `AnalyticsPage` | Sem analytics no core |

#### Componentes e hooks a remover

```
frontend/src/pages/ROIEditorPage.tsx
frontend/src/pages/AnalyticsPage.tsx
frontend/src/components/camera/DetectionOverlay.tsx
frontend/src/hooks/useROIEditor.ts
frontend/src/services/analytics.ts
```

#### Arquivos modificados

```
frontend/src/App.tsx                             ← remove rotas ROIEditor + Analytics
frontend/src/pages/DashboardPage.tsx             ← remove widgets de analytics
frontend/src/pages/CameraDetailPage.tsx          ← remove aba de analytics/ROI
frontend/src/components/layout/Sidebar.tsx       ← remove nav items Analytics e ROI
```

---

### Fase 5 — Relatórios (Reports)

**Objetivo:** Endpoint + UI de relatórios básicos (requisito core).

#### API

```
GET /api/v1/reports/events
  ?from=2026-04-01T00:00:00Z
  &to=2026-04-10T23:59:59Z
  &camera_id=uuid      (opcional)
  &event_type=alpr     (opcional)
  &format=json         (json | csv)

GET /api/v1/reports/recordings
  ?from=&to=&camera_id=

GET /api/v1/reports/cameras/summary
  → uptime estimado, total de eventos, total de gravações por câmera
```

#### Frontend

- Nova página `ReportsPage.tsx`
- Filtros: período, câmera, tipo de evento
- Tabela paginada com resultados
- Botão "Exportar CSV"
- Adicionada no Sidebar como "Relatórios"

#### Arquivos novos

```
api/src/vms/reports/router.py
api/src/vms/reports/service.py
api/src/vms/reports/schemas.py
frontend/src/pages/ReportsPage.tsx
frontend/src/services/reports.ts
```

---

## 6. Resumo de Mudanças por Serviço

### API (`/api/`)

| Ação | Alvo |
|------|------|
| Remover | `analytics_config/` (pasta completa) |
| Remover | `analytics_internal_router` do `main.py` |
| Adicionar | `plugins/` (bounded context — 3 endpoints) |
| Adicionar | `reports/` (bounded context — relatórios) |
| Modificar | `main.py`, `core/event_bus.py` |
| Migration | `005_remove_roi_table.py` |

### Analytics (`/analytics/`)

| Ação | Alvo |
|------|------|
| Modificar | `vms_client.py` — remove `get_rois`, usa API pública |
| Modificar | `orchestrator.py` — usa cameras endpoint público |
| Modificar | `frame_source.py` — usa stream token |
| Modificar | `config.py` — adiciona `VMS_API_KEY`, remove vars internas |
| Adicionar | `config/` — YAMLs de configuração por plugin (gitignored) |

### Frontend (`/frontend/`)

| Ação | Alvo |
|------|------|
| Deletar | `pages/ROIEditorPage.tsx` |
| Deletar | `pages/AnalyticsPage.tsx` |
| Deletar | `components/camera/DetectionOverlay.tsx` |
| Deletar | `hooks/useROIEditor.ts` |
| Deletar | `services/analytics.ts` |
| Adicionar | `pages/ReportsPage.tsx` |
| Adicionar | `services/reports.ts` |
| Modificar | `App.tsx`, `DashboardPage.tsx`, `CameraDetailPage.tsx`, `Sidebar.tsx` |

### Infrastructure (`/infra/`)

| Ação | Alvo |
|------|------|
| Modificar | `docker-compose.yml` — analytics como serviço opcional |
| Modificar | analytics env: `VMS_API_KEY` ao invés de rede interna |

---

## 7. Ordem de Execução

```
Fase 1  Core Cleanup         ← garante os 7 requisitos limpos
Fase 2  Plugin Contract      ← 3 endpoints novos no core
Fase 3  Analytics Refactor   ← plugin vira standalone real
Fase 4  Frontend Cleanup     ← remove ROI/analytics, ajusta nav
Fase 5  Reports              ← endpoint + UI de relatórios
```

---

## 8. O que NÃO muda

- Lógica de câmeras (CRUD, ONVIF, PTZ)
- MediaMTX e toda a infra de streaming
- Edge agent
- Sistema de usuários e multi-tenant
- Gravação de segmentos e clips
- Normalizers Hikvision e Intelbras
- Sistema de notificações e webhooks de saída
- Auth JWT + API Keys

---

## 9. Checklist de Conclusão

```
[ ] Fase 1: analytics_config removido, RabbitMQ opcional, 7 requisitos auditados
[ ] Fase 2: /api/v1/plugins/* funcionando com testes
[ ] Fase 3: analytics service usando apenas endpoints públicos
[ ] Fase 4: ROIEditorPage e AnalyticsPage removidos do frontend
[ ] Fase 5: ReportsPage funcionando com export CSV
[ ] make test → todos passam
[ ] make lint → sem erros
[ ] docker-compose up → stack completa sobe sem analytics (opcional)
[ ] docker-compose up --profile analytics → analytics sobe e conecta via API pública
```
