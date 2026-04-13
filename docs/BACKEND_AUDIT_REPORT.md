# 🔍 AUDITORIA BACKEND — Relatório Completo
## Gaps, Bugs e Plano de Correções

> Data: 13 de Abril de 2026
> Módulos auditados: LGPD, Billing, Reports, Audit, Custody, ISAPI, Health

---

## 📊 RESUMO EXECUTIVO

| Módulo | Status | Críticos | Moderados | Menores |
|--------|--------|----------|-----------|---------|
| **LGPD** | 🔴 CRÍTICO | 2 | 1 | 0 |
| **Billing** | 🔴 CRÍTICO | 1 | 2 | 1 |
| **Reports** | 🟡 PARCIAL | 3 | 3 | 2 |
| **Audit** | 🟢 BOM | 0 | 1 | 0 |
| **Custody/Integrity** | 🟢 BOM | 0 | 1 | 1 |
| **ISAPI** | 🟢 BOM | 0 | 1 | 0 |
| **Health** | 🟢 BOM | 0 | 0 | 1 |

---

## 🔴 PROBLEMAS CRÍTICOS (precisam de fix imediato)

### LGPD-1: Router não existe
**Arquivo:** `api/src/vms/lgpd/__init__.py` linha 2
```python
from vms.lgpd.router import router  # ← ESTE ARQUIVO NÃO EXISTE
```
**Impacto:** O módulo LGPD **não carrega**. O `__init__.py` tenta importar um router que não foi criado.
**Fix:** Criar `api/src/vms/lgpd/router.py` com endpoints LGPD e registrar em `main.py`.

### LGPD-2: Router não registrado em main.py
**Arquivo:** `api/src/vms/main.py`
**Impacto:** Mesmo que o router existisse, ele **não está registrado** no `_include_routers()`.
**Fix:** Adicionar `from vms.lgpd.router import router as lgpd_router` + `app.include_router(lgpd_router, prefix="/api/v1")`.

### BILLING-1: Conflito de migrações
**Arquivos:** 
- `api/migrations/versions/017b_cleanup_old_billing.py`
- `api/migrations/versions/018_create_usage_records.py`

**Problema:** A migração `017b` tenta dropar `usage_records` mas a tabela é criada pela migração `018` que tem `down_revision='017'`. As cadeias são:
```
015 → 016 → 017 → 017b  (cleanup — dropa usage_records)
015 → 017 → 018         (cria usage_records)
```
A migração `017b` referencia uma tabela que **ainda não existe** na cadeia principal.
**Impacto:** `alembic upgrade head` **pode falhar** dependendo da ordem de execução.
**Fix:** Corrigir `down_revision` da `018` para apontar para `017b`, ou fundir as migrações.

### REPORTS-1: ARQ task não gera PDF
**Arquivo:** `api/src/vms/reports/tasks.py`
**Problema:** A linha que geraria o PDF está **comentada**:
```python
# await svc.generate_report_pdf(report, data={...})
```
**Impacto:** A task ARQ **não faz nada** — só abre sessão, busca o report, e faz commit.
**Fix:** Descomentar e implementar coleta de dados na task.

### REPORTS-2: Geração síncrona no router
**Arquivo:** `api/src/vms/reports/router.py`
**Problema:** O `request_report` gera o PDF **sincronamente** na request HTTP, não via ARQ.
**Impacto:** Relatórios grandes causam timeout do Nginx (60s).
**Fix:** Usar ARQ task assíncrona + polling via `GET /reports/{id}`.

### REPORTS-3: Templates faltando
**Arquivos:** `api/src/vms/reports/templates/`
**Problema:** Apenas 3 de 5 templates existem:
- ✅ `cameras_report.html` — funcional
- ✅ `events_report.html` — funcional
- ✅ `recordings_report.html` — funcional
- ❌ `audit_trail.html` — **não existe** (aponta para "base")
- ❌ `analytics_events.html` — **não existe** (aponta para "base")
**Fix:** Criar os 2 templates faltando.

---

## 🟡 PROBLEMAS MODERADOS

### LGPD-3: Anonymization usa `func` sem importar
**Arquivo:** `api/src/vms/lgpd/anonymization.py` linha 52
```python
occurred_at=func.date_trunc('day', VmsEventModel.occurred_at),
```
**Problema:** `func` não está importado no topo do arquivo. Importado apenas dentro de `anonymize_face_event`.
**Fix:** Adicionar `from sqlalchemy import func` no topo.

### BILLING-2: Sem quota checks
**Arquivo:** `api/src/vms/billing/service.py`
**Problema:** Nenhum método de verificação de quota. O módulo é **apenas licenciamento**, não billing real.
**Impacto:** Não há limite de câmeras, storage, eventos por tenant.
**Fix:** Criar métodos `check_camera_quota()`, `check_storage_quota()`, `check_ai_quota()`.

### BILLING-3: Sem usage tracking
**Problema:** Tabelas `billing_plans` e `usage_records` foram deletadas pela migração `017b`.
**Impacto:** Não há registro de consumo por tenant.
**Fix:** Recriar migrações de `billing_plans` e `usage_records` com chain correta.

### REPORTS-4: _collect_data só implementa 1 tipo
**Arquivo:** `api/src/vms/reports/router.py`
**Problema:** A função `_collect_data()` só coleta dados para `CAMERAS_STATUS`. Outros tipos retornam dados vazios.
**Fix:** Implementar coleta para `EVENTS_SUMMARY`, `RECORDINGS_COVERAGE`, `AUDIT_TRAIL`, `ANALYTICS_EVENTS`.

### REPORTS-5: Acesso direto a _repo no router
**Arquivo:** `api/src/vms/reports/router.py`
**Problema:** Router acessa `svc._repo` diretamente, quebrando encapsulamento.
**Fix:** Adicionar métodos públicos no service (`list_reports`, `get_report`).

### REPORTS-6: REPORTS_PATH incompatível com Windows
**Arquivo:** `api/src/vms/reports/service.py`
**Problema:** Default `/tmp/reports` não existe no Windows.
**Fix:** Usar `tempfile.gettempdir()` ou variável de ambiente.

### AUDIT-1: Falha silenciosa no audit_action
**Arquivo:** `api/src/vms/infrastructure/middleware/audit_action.py`
**Problema:** Se INSERT do audit log falha, o erro é swallowado com `logger.debug`.
**Impacto:** Ações podem não ser auditadas sem ninguém saber.
**Fix:** Adicionar `logger.critical` + métrica Prometheus de falhas.

### CUSTODY-1: Custody chain não é persistida
**Arquivo:** `api/src/vms/recordings/router.py` → `export_forensic`
**Problema:** O `custody_chain` é lido do segmento mas **nunca é atualizado** após exportação forense.
**Fix:** Adicionar entrada ao `custody_chain` e persistir no banco.

### CUSTODY-2: Export forense não salva arquivo
**Arquivo:** `api/src/vms/recordings/router.py` → `export_forensic`
**Problema:** O ZIP é gerado em memória mas **nunca salvo em disco**. Retorna apenas metadata.
**Fix:** Salvar ZIP em `/forensic_exports/` + retornar URL de download.

### ISAPI-1: Respostas XML não são parseadas
**Arquivo:** `api/src/vms/infrastructure/cameras/isapi_client.py` → `get()`
**Problema:** A Hikvision retorna **XML**, mas o client tenta `response.json()` e fallback para `response.text`. O XML não é parseado para dict.
**Impacto:** `get_capabilities()` retorna string XML em vez de dict.
**Fix:** Adicionar `xmltodict.parse()` para respostas XML.

---

## ⚪ PROBLEMAS MENORES

### BILLING-4: is_active não atualiza status
**Arquivo:** `api/src/vms/billing/domain.py` → `License.is_active`
**Problema:** Propriedade retorna `False` se expirado, mas **não atualiza** o status no banco.
**Fix:** Adicionar método `expire_if_past()` que atualiza o status.

### REPORTS-7: Sem CSS externo nos templates
**Arquivo:** `api/src/vms/reports/pdf_generator.py`
**Problema:** WeasyPrint não recebe CSS externo. CSS precisa estar embutido.
**Fix:** Adicionar parâmetro `css` opcional + CSS base em `templates/base.css`.

### HEALTH-1: Analytics service não checado
**Arquivo:** `api/src/vms/health/router.py`
**Problema:** Health check não verifica se o Analytics Service está rodando.
**Fix:** Adicionar `_check_analytics()` com HTTP GET ao health endpoint do analytics.

---

## 📋 PLANO DE CORREÇÕES — Ordem de Prioridade

### Fase 1: Críticos (1-2 horas)

| # | Ação | Arquivos | Tempo |
|---|------|----------|-------|
| 1 | **Criar LGPD router** | `api/src/vms/lgpd/router.py` | 30min |
| 2 | **Registrar LGPD router em main.py** | `api/src/vms/main.py` | 5min |
| 3 | **Fix migration chain** | `017b`, `018` | 15min |
| 4 | **Fix ISAPI XML parse** | `isapi_client.py` | 15min |
| 5 | **Fix func import em anonymization** | `anonymization.py` | 5min |

### Fase 2: Reports (2-3 horas)

| # | Ação | Arquivos | Tempo |
|---|------|----------|-------|
| 6 | **Criar templates faltando** | `audit_trail.html`, `analytics_events.html` | 30min |
| 7 | **Implementar _collect_data** | `reports/router.py` | 45min |
| 8 | **Fix ARQ task** | `reports/tasks.py` | 20min |
| 9 | **Migrar para async** | `reports/router.py`, `reports/tasks.py` | 45min |
| 10 | **Fix REPORTS_PATH** | `reports/service.py` | 5min |
| 11 | **Add métodos públicos no service** | `reports/service.py` | 15min |

### Fase 3: Billing & Custody (2-3 horas)

| # | Ação | Arquivos | Tempo |
|---|------|----------|-------|
| 12 | **Recriar billing_plans migration** | `021_create_billing_plans.py` | 20min |
| 13 | **Recriar usage_records migration** | `022_create_usage_records.py` | 20min |
| 14 | **Implementar quota checks** | `billing/service.py` | 45min |
| 15 | **Persistir custody_chain** | `recordings/repository.py`, `router.py` | 30min |
| 16 | **Salvar forensic export** | `recordings/router.py` | 30min |

### Fase 4: Polimento (1-2 horas)

| # | Ação | Arquivos | Tempo |
|---|------|----------|-------|
| 17 | **Fix audit_action silent failure** | `audit_action.py` | 15min |
| 18 | **Fix License.is_active** | `billing/domain.py` | 10min |
| 19 | **Add CSS externo PDF** | `pdf_generator.py`, `base.css` | 15min |
| 20 | **Add analytics health check** | `health/router.py` | 15min |

---

## 🎯 PRÓXIMO PASSO

**Recomendação:** Começar pela **Fase 1** (críticos). São 5 fixes rápidos que desbloqueiam o resto.

Quer que eu comece a implementar as correções da Fase 1 agora?
