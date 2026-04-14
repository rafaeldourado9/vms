# 🗺️ ROADMAP REORDENADO — VMS Production-Ready
## Status Atual + Sprints Remanescentes (Kit Unificado)

> Atualizado: 13 de Abril de 2026
> Baseado na auditoria completa do código existente

---

## 💰 MODELO DE NEGÓCIO (definido)

### Dois Modos de Deploy

```
┌─────────────────────────────────────────────────────────────┐
│  White Label (Managed) — R$ 15.000/ano                      │
│  Cuidamos da sua infra                                      │
│                                                             │
│  ✅ Incluso: Streaming, Câmeras, Users, Relatórios,         │
│             Acesso total, LPR (webhooks)                   │
│  💾 Storage: R$ 50/cam/mês (obrigatório)                   │
│     opções: 7 dias | 15 dias | 30 dias (por câmera)       │
│  🧠 Analytics: pago por plugin/câmera/mês                  │
│     Analytics leves: a partir de R$ 6,90/dia              │
│     Analytics Pro: a partir de R$ 9,90/dia                │
│  🎯 SLA Dedicado, Suporte Prioritário                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  White Label (Self-Hosted) — R$ 20.000/ano                 │
│  Você cuida da sua infra                                    │
│                                                             │
│  ✅ Incluso: Streaming, Câmeras, Users, Relatórios,         │
│             Acesso total, LPR (webhooks)                   │
│  💾 Storage: Por conta do cliente                          │
│  🧠 Analytics: Por conta do cliente                        │
└─────────────────────────────────────────────────────────────┘
```

### Formato da License Key
```
XXXX-XXXXX-XXXXX-XXXXX-XXXXX
Ex: VKMH-WXSAQ-XQQWR-CAMWQ-QDAFW
```

---

## ✅ O QUE JÁ ESTÁ IMPLEMENTADO (Sprints 0–8)

| Sprint | Status | O que existe |
|--------|--------|-------------|
| **Sprint 0** — Foundation Fixes | ✅ FEITO | Webhooks ALPR (6 normalizers), Events API, SSE, frontend EventsPage |
| **Sprint 1** — Camera Intelligence | ✅ FEITO | 8 plugins YOLO (intrusion, people, vehicle, LPR, PPE, biker, fire/smoke, horse_cart, face_recognition), Shared Inference, orchestrator |
| **Sprint 2** — Tactical Map | ✅ FEITO | TacticalViewPage, MapTimelinePanel, pins por status, sidebar com filtros |
| **Sprint 3** — LPR Webhooks | ✅ FEITO | Endpoints Hikvision + Intelbras + genérico, dedup Redis, normalização VmsEvent |
| **Sprint 4** — Batch Pipeline | ✅ FEITO | ARQ tasks, index_segment, cleanup, file_frame_source.py |
| **Sprint 5** — UI/UX Polish | ✅ PARCIAL | RecordingPlayer, CameraTimeline, ROIManagementPage, 14 páginas frontend |
| **Sprint 6** — Performance & Scale | ✅ FEITO | Shared inference, GPU check, detection_cache, frame_source otimizado |
| **Sprint 7** — Production Hardening | ✅ FEITO | Multi-tenant, audit_log, correlation_id, rate_limit, structured_logging, health checks |
| **Sprint 8** — Audit Trail | ✅ FEITO | AuditLog modelo, service, router, middleware audit_action |

---

## 🔄 IMPLEMENTADO MAS INCOMPLETO (precisa de frontend ou polimento)

| Sprint | Backend | Frontend | O que falta |
|--------|---------|----------|-------------|
| **Sprint 9** — Cadeia de Custódia | ✅ SHA-256 em segments, verify-integrity | ❌ Não existe | Página de verificação de integridade, export forense UI |
| **Sprint 10** — Relatórios | ✅ PDF generation, templates HTML, ARQ tasks, 4 endpoints | ❌ Não existe | Página Relatórios (gerar, listar, download, histórico) |
| **Sprint 11** — Hikvision ISAPI | ✅ ISAPIClient, isapi_router, campos no modelo | ❌ Não existe | Página config ISAPI por câmera, status sync, capabilities |
| **Sprint 12** — Intelbras Deep | ✅ Normalizers intelbras_smart | ❌ Não existe | Mesma UI da Hikvision, auto-detect de capabilities |
| **Sprint 13** — Financeiro | ✅ Billing plans, licenses, usage_records, retention_policies | ❌ Não existe | Dashboard financeiro, página de consumo, alertas de cota |
| **Sprint 14** — LGPD Avançado | ✅ Consent records, anonymization, retention_policies | ⚠️ Parcial | Página LGPD (consentimento, retenção, exportação de dados) |
| **Sprint 15** — HA & Resiliência | ✅ Health endpoint com todos os checks | ⚠️ Parcial | Dashboard SystemHealth, alertas, failover UI |

---

## 📋 SPRINTS REORDENADOS (10–18)

> **Prioridade:** Frontend primeiro (telas faltando), depois polimento, depois governo avançado.

```
Sprint 10 [AGORA]  Frontend — Telas Faltando     — Billing, Reports, LGPD, Audit, ISAPI, Health
Sprint 11          Frontend — UI/UX Polish        — Timeline redesign, Analytics Dashboard, DetectionOverlay
Sprint 12          Agents & P2P                   — AgentsPage, Agent tunnel, WebSocket reconnect
Sprint 13          Testes & Hardening             — E2E Playwright, frontend unit tests, CI pipeline
Sprint 14          Cadeia de Custódia UI          — Verify integrity, export forense, custody chain
Sprint 15          Relatórios Governamentais UI   — Página completa, templates, assinatura, agendamento
Sprint 16          Compliance LGPD UI             — Retenção, anonimização, RIPD, e-SIC, direitos do titular
Sprint 17          Financeiro UI Completo         — Dashboard admin global, cotas, alertas, faturamento
Sprint 18          HA & Resiliência               — SystemHealth dashboard, failover, backup UI, DR runbook
```

---

## 🎯 SPRINT 10 — Frontend: Telas Faltando (PRIORIDADE MÁXIMA)

> **Meta:** Todas as funcionalidades backend têm tela no frontend. Zero endpoints órfãos.

### 10.1 — Página de Relatórios (Reports)

```
Arquivo: frontend/src/pages/ReportsPage.tsx

Funcionalidades:
- Lista de relatórios gerados (GET /api/v1/reports)
- Botão "Gerar Relatório" → modal com tipo + filtros
- Status: pending | generating | ready | failed
- Download do PDF quando pronto
- Histórico com paginação
- Polling automático para relatórios em geração

Tipos de relatório disponíveis:
- camera_status, coverage_quality, event_summary, alpr_report,
  intrusion_report, people_flow, access_log, recording_access,
  user_activity, incident_report, custody_report, system_health,
  storage_usage, retention_compliance

Design: Cards com ícone por tipo + tabela com status colorido
```

### 10.2 — Página de Auditoria (Audit Log)

```
Arquivo: frontend/src/pages/AuditPage.tsx

Funcionalidades:
- Tabela paginada com filtros (GET /api/v1/audit/logs)
- Filtros: usuário, ação, tipo de recurso, período
- Export CSV
- Detalhes do payload em modal
- Badge de severidade por tipo de ação
- Timeline visual de ações recentes

Colunas: occurred_at | usuário | ação | recurso | IP | resultado
```

### 10.3 — Página de Billing / Licenças

```
Arquivo: frontend/src/pages/BillingPage.tsx

Funcionalidades:
- Consumo atual do tenant (GET /api/v1/billing/usage)
- Métricas: câmeras ativas, câmeras com IA, storage GB, eventos analytics
- Barra de progresso por métrica (valor vs limite do plano)
- Plano atual e features ativas
- Histórico de uso (últimos 12 meses)
- Alertas de cota (80% = amarelo, 100% = vermelho)

Design: Cards com métricas + barras de progresso + gráfico de uso mensal
```

### 10.4 — Página de Configuração ISAPI (por câmera)

```
Arquivo: frontend/src/pages/CameraISAPIPage.tsx

Acessível via: CameraDetailPage → aba "ISAPI"

Funcionalidades:
- Status da conexão ISAPI (online/offline)
- Botão "Configurar Push" → configura webhook na câmera
- Botão "Sincronizar Hora" → NTP sync
- Lista de capabilities detectadas (VCA, LPR, Face, People Counting)
- Info do dispositivo: modelo, serial, firmware
- Snapshot ao vivo via ISAPI
- Configuração de Smart Events (linhas, zonas)

Design: Abas dentro da página de detalhe da câmera
```

### 10.5 — Página LGPD / Compliance

```
Arquivo: frontend/src/pages/LGPDPage.tsx

Funcionalidades:
- Toggle Reconhecimento Facial (com modal de consentimento LGPD Art. 11)
- Histórico de consentimentos (GET /api/v1/lgpd/consent-log)
- Políticas de retenção por tipo de dado
- Botão "Solicitar Exportação de Dados" (direito do titular)
- Botão "Revogar Consentimento" (face recognition)
- Status de anonimização de eventos expirados
- Botão "Gerar RIPD" (Relatório de Impacto à Proteção de Dados)

Design: Seções com cards + toggles + modais de consentimento
```

### 10.6 — Dashboard System Health

```
Arquivo: frontend/src/pages/SystemHealthPage.tsx

Funcionalidades:
- Status em tempo real dos serviços (via SSE + GET /health)
  - Database, Redis, RabbitMQ, MediaMTX, Analytics
  - Semáforo: verde/amarelo/vermelho
- Métricas de câmeras: uptime, cobertura de gravação, gaps
- Armazenamento: uso atual + projeção "disco cheio em X dias"
- Analytics: eventos por hora (sparkline), plugins com erro
- Últimas ações de auditoria (últimos 10 downloads, 5 logins)

Design: Cards de semáforo + sparklines Recharts + barras de progresso
```

### Critérios de Aceite Sprint 10

- [ ] 6 novas páginas criadas e registradas no App.tsx
- [ ] Sidebar atualizada com novos ícones (reaproveitando padrão existente)
- [ ] Todas as páginas consomem APIs existentes (nenhuma API nova necessária)
- [ ] Design escuro consistente com páginas existentes
- [ ] SSE integrado para atualizações em tempo real onde aplicável
- [ ] Loading states, error states, empty states em todas as páginas
- [ ] Responsivo (1280px até 4K)

---

## 🎨 SPRINT 11 — Frontend: UI/UX Polish

### 11.1 — Timeline de Gravações Redesign

```
Arquivo: frontend/src/components/camera/RecordingTimeline.tsx (refatorar)

Design especificado:
- Barra horizontal com blocos coloridos de cobertura
- Hover → tooltip com hora exata (HH:mm:ss)
- Eventos marcados como ◆ na timeline (cor por severidade)
- Controles: ⏮ ◀◀ ▶ ▶▶ ⏭ | velocidade 0.5x 1x 2x 4x
- Download segmento | Criar Clip (range selecionável)
- Zoom com scroll do mouse
- Sem scrollbar horizontal visível
```

### 11.2 — Analytics Dashboard (Nova Página)

```
Arquivo: frontend/src/pages/AnalyticsDashboardPage.tsx

Layout:
- 4 cards resumo: Total | Críticos | Alertas | Info
- Gráfico de linha: eventos por hora (últimas 24h), linha por plugin
- Tabela "Top Câmeras": câmera + contagem
- Gráfico de barras: distribuição por plugin
- Seletor de período: 1h | 6h | 24h | 7d | 30d
- SSE: analytics.* atualiza cards em tempo real

Design: Recharts para gráficos, cores por severidade
```

### 11.3 — DetectionOverlay (Camada de detecção no vídeo)

```
Arquivo: frontend/src/components/camera/DetectionOverlay.tsx

Funcionalidades:
- Renderiza bounding boxes de detecções sobre o vídeo
- Cores por classe: pessoa=verde, veículo=azul, etc.
- Labels com confiança e classe
- ROI desenhadas sobre o vídeo (polígonos)
- Toggle on/off
- Integração com events de analytics em tempo real
```

### 11.4 — Sidebar: Novos Ícones e Organização

```
Arquivo: frontend/src/components/layout/Sidebar.tsx

Novos itens na sidebar (reaproveitando ícones existentes):
- 📊 Analytics Dashboard (novo)
- 📋 Relatórios (novo)
- 🔍 Auditoria (novo)
- 💰 Billing / Licenças (novo)
- 🛡️ LGPD / Compliance (novo)
- 🏥 System Health (novo)
- 📡 ISAPI (sub-item de Câmeras)

Reorganizar seções:
┌─ OPERAÇÕES ─────────┐
│  Dashboard           │
│  Câmeras             │
│  Mosaico             │
│  Gravações           │
│  Eventos             │
│  Mapa Tático         │
├─ INTELIGÊNCIA ───────┤
│  Analytics Dashboard │
│  Analytics Eventos   │
│  ROI Management      │
│  Detecções (overlay) │
├─ ADMINISTRAÇÃO ──────┤
│  Relatórios          │
│  Auditoria           │
│  Billing             │
│  Notificações        │
│  Usuários            │
├─ COMPLIANCE ─────────┤
│  LGPD                │
│  Cadeia de Custódia  │
├─ SISTEMA ────────────┤
│  System Health       │
│  Configurações       │
└──────────────────────┘
```

### Critérios de Aceite Sprint 11

- [ ] Timeline redesenhada com UX minimalista
- [ ] Analytics Dashboard gerando gráficos corretos
- [ ] DetectionOverlay funcional sobre o player de vídeo
- [ ] Sidebar reorganizada com seções lógicas
- [ ] Todos os ícones consistentes (mesma biblioteca)
- [ ] Transições suaves entre páginas (no flicker)

---

## 📡 SPRINT 12 — Agents & P2P

### 12.1 — AgentsPage

```
Arquivo: frontend/src/pages/AgentsPage.tsx
Service: frontend/src/services/agents.ts (criar)

Funcionalidades:
- Lista de edge agents registrados
- Status: online/offline (SSE camera.online/offline)
- Métricas do agente: CPU, RAM, GPU, network
- Último heartbeat
- Câmeras vinculadas ao agente
- Botão "Restart Agent" (via API)
- Logs do agente em modal
```

### 12.2 — Agent Tunnel Reverso

```
Arquivo: edge_agent/src/agent/tunnel.py (criar)
         api/src/vms/agents/tunnel_router.py (criar)

Funcionalidades:
- WebSocket persistente entre agent e cloud
- Fallback para HTTP polling se WebSocket cair
- Reconexão automática com exponential backoff
- Comandos remotos: restart, update, config, snapshot
- Health check via tunnel
```

### 12.3 — E2E de Agentes

```
Funcionalidades:
- Testar conexão agent → cloud
- Testar push de eventos
- Testar comando remoto (snapshot, restart)
- Testar reconexão após queda
```

### Critérios de Aceite Sprint 12

- [ ] AgentsPage listando agentes com status em tempo real
- [ ] Tunnel WebSocket funcionando com reconexão
- [ ] Comandos remotos executando no agent
- [ ] Métricas de hardware exibidas (CPU, RAM, GPU)
- [ ] Heartbeat atualizando via SSE

---

## 🧪 SPRINT 13 — Testes & Hardening

### 13.1 — E2E Tests (Playwright)

```
Arquivos: api/tests/e2e/ (criar)
          frontend/tests/e2e/ (criar)

Testes obrigatórios:
1. Login → Dashboard → Câmeras → Gravações → Eventos (fluxo completo)
2. Adicionar câmera → verificar stream → criar ROI → verificar evento
3. Webhook ALPR → evento aparece no frontend via SSE
4. Gerar relatório → download PDF
5. Auditoria: ação registrada no audit log
6. LGPD: consentimento de face recognition
7. Billing: consumo registrado
```

### 13.2 — Frontend Unit Tests

```
Arquivos: frontend/src/tests/unit/ (expandir)

Testes obrigatórios:
1. useSSE hook (conexão, reconexão, disconnect)
2. usePermission hook (permissões por role)
3. VideoPlayer (play, pause, seek, error)
4. RecordingPlayer (VOD mode, MP4 fallback)
5. ROIEditor (criar, editar, deletar polígono)
6. DetectionOverlay (bounding boxes, labels)
7. Sidebar (renderização por permissão)
8. Todas as services (mock de API)
```

### 13.3 — CI Pipeline

```
Arquivo: .github/workflows/ci.yml (criar)

Pipeline:
1. lint (ruff + mypy + eslint)
2. test unit (backend + frontend)
3. test integration (backend com DB real)
4. test BDD (behave)
5. build (Docker images)
6. push (registry)
```

### Critérios de Aceite Sprint 13

- [ ] 7 testes E2E passando
- [ ] 20+ testes unitários frontend
- [ ] CI pipeline rodando em < 15min
- [ ] Coverage > 80% backend, > 60% frontend
- [ ] Zero warnings no lint

---

## 🔒 SPRINT 14 — Cadeia de Custódia UI

### 14.1 — Verificação de Integridade

```
Arquivo: frontend/src/components/recordings/IntegrityBadge.tsx

Funcionalidades:
- Badge visual de integridade (✅ verificada | ❌ comprometida | ⏳ pendente)
- Botão "Verificar Integridade" → chama GET /recordings/{id}/verify-integrity
- Modal com resultado: stored_hash, current_hash, verified_at
- Alerta visual se hash divergente
```

### 14.2 — Exportação Forense

```
Arquivo: frontend/src/components/recordings/ForensicExport.tsx

Funcionalidades:
- Botão "Export Forensic" em RecordingPage
- Modal com opções: período, câmeras, incluir eventos
- Gera ZIP: video.mp4 + metadata.json + custody_chain.json + integrity_report.pdf
- Acompanha status via polling (pending → generating → ready)
- Download quando pronto
- Registro no audit log automaticamente
```

### 14.3 — Custody Chain Viewer

```
Arquivo: frontend/src/components/recordings/CustodyChainViewer.tsx

Funcionalidades:
- Timeline visual de quem acessou/exportou a gravação
- Cada entry: usuário, ação, timestamp, IP
- Botão "Verificar cadeia completa"
- Indicador de integridade em cada ponto da cadeia
```

### Critérios de Aceite Sprint 14

- [ ] IntegrityBadge exibindo status correto
- [ ] Export forense gerando ZIP completo
- [ ] CustodyChainViewer mostrando timeline
- [ ] Audit log registrado em cada exportação
- [ ] Alerta automático se hash divergente

---

## 📄 SPRINT 15 — Relatórios Governamentais UI

### 15.1 — Página Completa de Relatórios

```
Arquivo: frontend/src/pages/ReportsPage.tsx (refinar Sprint 10)

Funcionalidades avançadas:
- Templates de relatório visuais (preview antes de gerar)
- Agendamento de relatórios (cron expression UI)
- Assinatura digital (upload de certificado ICP-Brasil)
- Status de geração com progresso visual
- Histórico com filtros (tipo, período, status)
- Download com nome padronizado
```

### 15.2 — Template Editor (avançado)

```
Arquivo: frontend/src/components/reports/TemplateEditor.tsx

Funcionalidades:
- Editor de template HTML para relatórios customizados
- Preview em tempo real
- Variáveis disponíveis listadas
- Upload de logo do tenant
- Configuração de marca d'água
```

### Critérios de Aceite Sprint 15

- [ ] Página de relatórios completa e polida
- [ ] Agendamento funcional via UI
- [ ] Assinatura digital com certificado
- [ ] Templates customizáveis
- [ ] Download com nome padronizado

---

## 🛡️ SPRINT 16 — Compliance LGPD UI Completo

### 16.1 — Página LGPD Refinada

```
Arquivo: frontend/src/pages/LGPDPage.tsx (refinar Sprint 10)

Funcionalidades adicionais:
- RIPD gerado automaticamente ao ativar face_recognition
- Download do RIPD em PDF
- Exportação de dados pessoais do titular (formato legível)
- Anonimização em massa de eventos expirados
- Relatório de conformidade de retenção
- Log completo de consentimentos com IP e timestamp
```

### 16.2 — e-SIC Integration

```
Arquivo: frontend/src/pages/ESICPage.tsx

Funcionalidades:
- Relatório de transparência ativa
- Export no formato e-SIC
- Dados do sistema (sem dados pessoais)
- Finalidade do VMS documentada
```

### Critérios de Aceite Sprint 16

- [ ] RIPD gerado e baixável
- [ ] Exportação de dados do titular funcionando
- [ ] Anonimização em massa executando
- [ ] e-SIC exportando no formato correto
- [ ] Consentimentos registrados com IP + timestamp

---

## 💰 SPRINT 17 — Financeiro UI Completo

### 17.1 — Dashboard Financeiro (Admin Global)

```
Arquivo: frontend/src/pages/AdminFinancePage.tsx

Funcionalidades:
- Total de tenants, câmeras, storage, MRR estimado
- Tabela de consumo por tenant
- Filtros por período e plano
- Export de relatório financeiro em PDF
- Alertas de cota por tenant
- Histórico de faturas
```

### 17.2 — Página de Planos e Licenças

```
Arquivo: frontend/src/pages/PlansPage.tsx

Funcionalidades:
- CRUD de billing plans (admin global)
- CRUD de licenses (admin global)
- Atribuição de plano a tenant
- Customização de limites por tenant
- Preview de fatura por tenant
```

### Critérios de Aceite Sprint 17

- [ ] Dashboard financeiro com métricas corretas
- [ ] CRUD de planos e licenças funcionando
- [ ] Alertas de cota em tempo real
- [ ] Relatório financeiro exportável em PDF

---

## 🏥 SPRINT 18 — HA & Resiliência

### 18.1 — System Health Dashboard (Refinado)

```
Arquivo: frontend/src/pages/SystemHealthPage.tsx (refinar Sprint 10)

Funcionalidades adicionais:
- Configuração de alertas (email, SMS, Slack)
- Runbook de disaster recovery (visual)
- Status de backup (último backup, próximo agendado)
- Configuração de retenção por câmera
- Métricas de performance (latência DB, throughput)
```

### 18.2 — Backup & DR UI

```
Arquivo: frontend/src/pages/BackupPage.tsx

Funcionalidades:
- Status de backups (último, tamanho, duração)
- Botão "Backup Now" (trigger manual)
- Configuração de agendamento
- Configuração de retention de backups
- Teste de restore (simulação)
- Métricas RTO/RPO
```

### Critérios de Aceite Sprint 18

- [ ] Health dashboard com todos os serviços
- [ ] Backup UI funcional
- [ ] Alertas configuráveis
- [ ] Runbook de DR documentado e acessível
- [ ] Métricas RTO/RPO exibidas

---

## 📊 RESUMO EXECUTIVO

```
SPRINTS COMPLETOS (0–8):        ████████████████████ 100% (9 sprints)
SPRINTS INCOMPLETOS (9–13):     ████████░░░░░░░░░░░░  40% (5 sprints, backend pronto)
SPRINTS NÃO INICIADOS (14–18):  ░░░░░░░░░░░░░░░░░░░░   0% (5 sprints)

BACKEND:   ████████████████████  95% (só faltam ajustes menores)
FRONTEND:  █████████░░░░░░░░░░░  45% (14 páginas prontas, 6+ faltando)
TESTES:    ██████░░░░░░░░░░░░░░  30% (backend bom, frontend fraco, E2E zero)
INFRA:     ███████████████░░░░░  75% (Terraform existe, AWS vazio)

PRIORIDADE IMEDIATA:
1. Sprint 10 — Telas faltando (billing, reports, LGPD, audit, ISAPI, health)
2. Sprint 11 — UI/UX polish (timeline, analytics dashboard, detection overlay)
3. Sprint 12 — Agents page + tunnel
4. Sprint 13 — E2E tests + CI
5. Sprints 14–18 — Governo avançado (cadeia de custódia, relatórios, LGPD, financeiro, HA)
```

---

## 🎯 ORDEM DE EXECUÇÃO RECOMENDADA

```
SEMANA 1:  Sprint 10 (6 telas novas)
SEMANA 2:  Sprint 11 (UI/UX polish)
SEMANA 3:  Sprint 12 (Agents + tunnel)
SEMANA 4:  Sprint 13 (Testes + CI)
SEMANA 5:  Sprint 14 (Cadeia de custódia UI)
SEMANA 6:  Sprint 15 (Relatórios UI completo)
SEMANA 7:  Sprint 16 (LGPD UI completo)
SEMANA 8:  Sprint 17 (Financeiro UI completo)
SEMANA 9:  Sprint 18 (HA & Resiliência)
```

> **Total estimado: 9 semanas para VMS 100% production-ready com UI completa.**

---

## 🚀 CHECKLIST PRÉ-SPRINT 10

Antes de começar o Sprint 10, verificar:

- [ ] Backend está rodando e acessível
- [ ] Frontend está rodando e conectado à API
- [ ] Todas as APIs existentes respondendo corretamente
- [ ] Sidebar atual tem ícones funcionais
- [ ] Sistema de rotas (App.tsx) funcionando
- [ ] Auth/permission hooks funcionando
- [ ] SSE conectado e funcionando
- [ ] Design system (cores, espaçamento, tipografia) consistente

---

*"Câmera que grava sem auditoria é câmera que ninguém confia."*
*"Frontend sem backend é bonito mas não funciona. Backend sem frontend é potente mas ninguém usa."*
