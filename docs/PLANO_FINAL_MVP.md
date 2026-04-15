# Plano Final — MVP VMS

> Documento operacional para fechar o MVP. Atualizado: 2026-04-14.
> Ordem obrigatória: **Backend → Analytics → Edge Agent → Infra/QA → Frontend (rewrite)**.
> O frontend só começa quando o backend estiver 100% verde.

---

## 0. Princípios

- Frontend será **reescrito** para refletir fielmente o backend atual. **NÃO mudar**: design, tipografia, paleta de cores, ícones da sidebar. Apenas estrutura de páginas, chamadas de API, estados e fluxos.
- Backend é fonte da verdade. Toda página nova nasce de um contrato existente em `api/src/vms/*/router.py`.
- Sem features novas fora deste plano. Fechar escopo, estabilizar, lançar.
- Cada item do checklist deve fechar com: código + teste + CI verde + doc atualizado quando aplicável.

---

## 1. Estado Atual (audit 2026-04-14)

| Camada | Estado | Observação |
|--------|--------|------------|
| Backend core (IAM, Cameras, Streaming, Recordings, VOD, Events, Notifications, Plugins, Audit, Health, SSE) | ✅ 95% | Produção-ready, coberto por testes |
| Analytics service + 8 plugins | ✅ ready | fire_smoke, intrusion, people, vehicle, ppe, lpr, biker, face_recognition |
| Reports | 🟡 50% | PDF comentado, `_collect_data` só implementa CAMERAS_STATUS |
| Billing | 🔴 chain migrations quebrada | 017b/018 conflito, quota não aplicada |
| LGPD | 🟢 funciona | bug import `func` em `anonymization.py:52` |
| Edge Agent | 🟡 | streams + heartbeat OK; tunnel e orquestração de plugin faltam |
| Infra (docker-compose, CI) | ✅ | CI com lint, typecheck, unit, build |
| Frontend | 🔴 45% | desalinhado do backend, 3 testes unitários, 0 E2E |
| Testes backend | ✅ | 57 arquivos, unit+integração |
| Testes E2E | 🔴 | inexistentes |

---

## 2. FASE A — Correções Críticas de Backend (1–2 dias)

Bloqueadores curtos que impedem deploy limpo.

- [ ] **A1.** Corrigir import `func` em `api/src/vms/lgpd/anonymization.py:52` (adicionar `from sqlalchemy import func`).
- [ ] **A2.** Corrigir parsing XML do ISAPI em `api/src/vms/infrastructure/cameras/isapi_client.py` (`get_capabilities` usa `.json()` num retorno XML → trocar para `xmltodict` ou `lxml`).
- [ ] **A3.** Resolver conflito da cadeia de migrations Alembic:
  - revisar heads: `alembic heads` deve retornar 1.
  - mesclar 017b e 018 ou criar merge revision.
  - validar `alembic upgrade head` em base limpa.
- [ ] **A4.** Adicionar check do analytics service em `api/src/vms/health/router.py` (HTTP GET no `/health` do analytics com timeout 2s).
- [ ] **A5.** `audit.middleware`: parar de engolir exceção silenciosamente — logar em WARNING com `exc_info=True`.
- [ ] **A6.** Rodar `make lint && make typecheck && make test` e garantir verde.

**Saída:** pipeline limpo, `alembic upgrade head` em base nova funciona, health check completo.

---

## 3. FASE B — Fechar Reports (1 dia)

- [ ] **B1.** Implementar `_collect_data` para os 4 templates restantes em `api/src/vms/reports/service.py` (EVENTS_SUMMARY, ALPR_SUMMARY, STORAGE, AUDIT).
- [ ] **B2.** Reativar geração de PDF em `api/src/vms/reports/tasks.py` (ReportLab ou WeasyPrint). Mover execução para Celery queue `reports` (não síncrono no router).
- [ ] **B3.** Endpoint `GET /api/v1/reports/{id}` retorna status (`pending|running|done|failed`) e URL de download quando pronto.
- [ ] **B4.** Teste: criar report → polling até `done` → baixar PDF não vazio.

---

## 4. FASE C — Fechar Billing (2 dias)

- [ ] **C1.** Revisar modelos em `api/src/vms/billing/models.py` contra o plano `Managed (R$15k)` e `Self-Hosted (R$20k)` documentado em `docs/SPRINTS.md`.
- [ ] **C2.** Implementar aferição de uso:
  - contador de câmeras ativas por tenant.
  - storage consumido (reutilizar task de quota).
  - analytics-cameras ativas (por plugin instalado).
- [ ] **C3.** Middleware/guard de quota em `cameras.service.create_camera` — bloqueia quando excede plano.
- [ ] **C4.** Endpoint `GET /api/v1/billing/usage` → uso do mês corrente + limite do plano.
- [ ] **C5.** Seeds e scripts em `scripts/seed_billing_plans.py` e `seed_pricing_rules.py` validados e idempotentes.
- [ ] **C6.** Testes: quota excedida → 402/403; uso zera no início do ciclo.

---

## 5. FASE D — Forense / Custody Chain (meio dia)

- [ ] **D1.** Persistir custody chain em `api/src/vms/recordings/router.py::export_forensic` (gravar JSON assinado em `/static/forensic/{export_id}.json` + hash SHA-256 no ZIP).
- [ ] **D2.** Endpoint `GET /api/v1/recordings/forensic/{id}/custody` devolve cadeia verificável.
- [ ] **D3.** Teste: export → alterar byte do vídeo → verificação falha.

---

## 6. FASE E — Edge Agent (3–4 dias)

- [ ] **E1.** Tunnel reverso: já há suporte cloudflared no docker-compose; adicionar orquestração no agent (`edge_agent/src/agent/tunnel.py`) e documentar em `docs/DEPLOY.md`.
- [ ] **E2.** Download/execução de plugin local (opcional ao MVP — avaliar se fica em V1.1). Se ficar, implementar:
  - `plugin_manager.py` com cache de modelos em `~/.vms/models/`.
  - download assinado via API do servidor.
  - execução em subprocesso isolado.
- [ ] **E3.** Adicionar suíte mínima em `edge_agent/tests/` (config poll, ffmpeg start/stop, heartbeat).
- [ ] **E4.** Criar `make agent-test` no Makefile.

**Decisão a confirmar com usuário**: E2 entra no MVP ou vai para V1.1?

---

## 7. FASE F — QA, Infra e Observabilidade (2–3 dias)

- [ ] **F1.** Escrever suíte E2E com Playwright contra stack Docker completa:
  - login → criar câmera → stream HLS ativo → gerar evento ALPR → ver na lista.
  - criar usuário → permissões → acesso negado em área proibida.
  - gerar report → polling → download PDF.
- [ ] **F2.** Load test com `locust` ou `k6`: 200 câmeras, 24h de recording, 50 viewers simultâneos. Relatório salvo em `docs/load-test-2026.md`.
- [ ] **F3.** Validar backup `infra/scripts/backup_db.sh` + restore em container efêmero.
- [ ] **F4.** Validar `docs/VPS_DEPLOY.md` ponta a ponta em VPS limpa.
- [ ] **F5.** CI: adicionar job E2E headless (pode rodar em branch protected only).

---

## 8. FASE G — Frontend Rewrite (5–7 dias)

> **Regras invioláveis do rewrite**
> - Design, tipografia, paleta de cores e ícones da sidebar permanecem **IDÊNTICOS** ao atual.
> - Reaproveitar tokens Tailwind, componentes de design system, assets de `frontend/src/assets/`.
> - Reescrever apenas: roteamento, páginas, chamadas de API, hooks, estados, tipos.

### G.1 Preparação

- [ ] Inventariar tokens de design (cores, fontes, spacing) e consolidar em `frontend/src/design/` como fonte única.
- [ ] Congelar `Sidebar.tsx` — ícones, ordem, labels intocados.
- [ ] Gerar client TypeScript a partir do OpenAPI do FastAPI (`openapi-typescript` ou `orval`) em `frontend/src/api/generated/`.
- [ ] Configurar Playwright + Vitest.

### G.2 Páginas (ordem de implementação)

Cada página: route + fetch tipado + estados loading/error/empty + testes mínimos.

- [ ] **Auth**: Login, Logout, refresh silencioso, rotas protegidas por role.
- [ ] **Dashboard**: KPIs (câmeras online, eventos 24h, storage) via `/health`, `/analytics/stats`.
- [ ] **Cameras**: list, detail, create, edit, delete, snapshot, PTZ, ONVIF discovery.
- [ ] **Mosaic**: grade HLS/WebRTC com tokens assinados.
- [ ] **Recordings**: timeline, playback VOD, export forense com custody visível.
- [ ] **Events**: lista filtrada, detalhe, SSE realtime.
- [ ] **Analytics**: catálogo de plugins, instalações por câmera, dashboard por tipo, ROI editor.
- [ ] **Notifications**: rules CRUD, teste de webhook, log.
- [ ] **Users / IAM**: users, roles, API keys.
- [ ] **Audit**: log, filtros, export.
- [ ] **Billing**: plano, uso atual, histórico.
- [ ] **LGPD**: solicitações, anonimização, export de dados.
- [ ] **Reports**: criar, acompanhar status, baixar PDF.
- [ ] **Agents (edge)**: list, status, config, revoke.
- [ ] **System Health**: serviços, filas, MediaMTX, storage.
- [ ] **Settings**: tenant, branding (sem trocar design global).

### G.3 Testes

- [ ] Unit tests: hooks (useSSE, usePermission, useAuth), componentes críticos (VideoPlayer, ROI editor, Mosaic cell).
- [ ] E2E Playwright: golden paths da fase F1 rodando pelo UI novo.
- [ ] Snapshot visual de páginas-chave (regressão de estilo).

### G.4 Handoff

- [ ] Limpar código legado em `frontend/src/legacy/` (se existir) após paridade total.
- [ ] Atualizar `docs/ARCHITECTURE.md` com mapa rotas ↔ endpoints.

---

## 9. FASE H — Go-Live (1 dia)

- [ ] Deploy em VPS de staging seguindo `docs/VPS_DEPLOY.md`.
- [ ] Smoke tests manuais: cadastro, câmera real, gravação 1h, evento ALPR, notificação webhook externa.
- [ ] Monitoramento: logs JSON agregados, alertas de health 5xx.
- [ ] Tag `v1.0.0`, CHANGELOG atualizado, release GitHub.
- [ ] Backup automático habilitado (cron).
- [ ] Documento `docs/RUNBOOK.md` com comandos operacionais (restart, restore, rotate secret).

---

## 10. Checklist Macro

```
[ ] Fase A — Correções críticas backend         (1–2d)
[ ] Fase B — Reports completos                  (1d)
[ ] Fase C — Billing com quota                  (2d)
[ ] Fase D — Custody chain forense              (0.5d)
[ ] Fase E — Edge Agent (tunnel + testes)       (3–4d)
[ ] Fase F — QA, E2E, load test, deploy docs    (2–3d)
[ ] Fase G — Frontend rewrite                   (5–7d)
[ ] Fase H — Go-Live staging + v1.0.0           (1d)
```

**Estimativa total:** 15–20 dias úteis (~3 semanas).

**Marcos:**
- M1 (fim da F): backend 100%, infra validada, E2E verde → sinal verde para frontend.
- M2 (fim da G): frontend em paridade com backend, design preservado.
- M3 (fim da H): v1.0.0 em produção.

---

## 11. Regras de Execução

1. Trabalhar em branches por fase (`phase/A-backend-fixes`, `phase/G-frontend-rewrite`).
2. PR por item do checklist — commits atômicos conforme `CLAUDE.md`.
3. Marcar item feito apenas após CI verde + teste escrito.
4. Qualquer desvio de escopo vai para `docs/POST_MVP.md`, não entra aqui.
5. Nenhuma mudança de design no frontend. Em caso de dúvida: **manter o atual**.
