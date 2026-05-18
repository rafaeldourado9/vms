# Modelagem de Banco de Dados

> Estratégias, técnicas e decisões de modelagem do PostgreSQL no VMS.

---

## 1. Tipo de Modelagem

O VMS usa **modelagem relacional normalizada** (3NF) como base, com extensões específicas para performance e compliance:

| Técnica | Onde | Motivo |
|---------|------|--------|
| **Relacional normalizada (3NF)** | Todas as tabelas core | Integridade referencial, sem anomalias de atualização |
| **Multi-tenancy por coluna** | `tenant_id UUID` em todas as tabelas | Shared database, shared schema — simples e eficiente para o volume atual |
| **UUID v4 como PK** | Todos os registros | Sem colisão cross-tenant, seguro para expor via API, sem lock de auto-increment |
| **JSONB para dados semi-estruturados** | `payload`, `custody_chain`, `isapi_capabilities`, `parameters` | Flexibilidade sem schema migration, indexável via GIN |
| **Particionamento por data** | `audit_logs` | Tabela de alto volume, cleanup por DROP PARTITION em vez de DELETE |
| **Índices compostos** | Queries críticas | Evitar seq scans em tabelas grandes multi-tenant |
| **Soft constraints via enum string** | `status`, `role`, `manufacturer` | Flexibilidade para adicionar valores sem migration destrutiva |
| **Cascade behavior explícito** | FKs com `ON DELETE CASCADE / SET NULL` | Controle explícito de integridade referencial por contexto |

---

## 2. Multi-Tenancy: Shared Database, Shared Schema

### Estratégia escolhida
```
Tenant A │ Tenant B │ Tenant C
   ↓           ↓          ↓
    ┌──────────────────────┐
    │  Mesma tabela cameras │
    │  tenant_id = A|B|C   │
    └──────────────────────┘
```

**Por que não "1 banco por tenant" (Database-per-tenant)?**
- Número de tenants pode chegar a centenas → gerenciar centenas de bancos é inviável
- Migrations precisariam rodar em cada banco separadamente
- Connection pooling seria proibitivo

**Por que não "schema por tenant"?**
- PostgreSQL tem limite de ~10k schemas por banco
- Migrations ainda complexas
- Não suportado nativamente pelo SQLAlchemy async de forma simples

**Custo da abordagem shared:**
- Todo QuerySet DEVE filtrar por `tenant_id` — isso é enforced no Repository (não na view)
- Índices precisam ser compostos: `(tenant_id, campo_filtrado)`
- Row-level Security (RLS) do PostgreSQL seria alternativa mais segura — não implementado ainda

### Índices obrigatórios por tabela multi-tenant

```sql
-- cameras
CREATE INDEX ix_cameras_tenant_online ON cameras(tenant_id, is_online);

-- vms_events
CREATE INDEX ix_events_tenant_occurred ON vms_events(tenant_id, occurred_at DESC);
CREATE INDEX ix_events_plate ON vms_events(plate);

-- recording_segments
CREATE INDEX ix_recordings_tenant_camera_started
    ON recording_segments(tenant_id, camera_id, started_at DESC);

-- audit_logs (particionado)
CREATE INDEX ix_audit_tenant_occurred ON audit_logs(tenant_id, occurred_at DESC);
CREATE INDEX ix_audit_user ON audit_logs(user_id, occurred_at DESC);
CREATE INDEX ix_audit_action ON audit_logs(action, occurred_at DESC);
CREATE INDEX ix_audit_resource ON audit_logs(resource_type, resource_id);
```

---

## 3. UUID v4 como Chave Primária

### Vantagens neste contexto
- **Sem colisão cross-tenant**: dois tenants criando câmera ao mesmo tempo nunca geram o mesmo ID
- **Seguro para expor via API**: não revela sequência nem volume de dados
- **Gerado no application layer**: sem round-trip ao banco para obter ID antes do INSERT
- **Suporte nativo no PostgreSQL** com tipo `UUID`

### Desvantagem conhecida
- UUID v4 é aleatório → fragmentação do B-tree index (page splits frequentes)
- Para tabelas de altíssimo volume (audit_logs, analytics_events): considerar UUID v7 (timestamp-prefixed) no futuro

```sql
-- UUID v7 seria ordenado por tempo, melhor para B-tree:
-- 01956a1c-2d4b-7000-8000-000000000000
-- vs UUID v4 aleatório:
-- f47ac10b-58cc-4372-a567-0e02b2c3d479
```

---

## 4. JSONB para Dados Semi-Estruturados

### Onde e por que

| Campo | Tabela | Justificativa |
|-------|--------|--------------|
| `payload` | `vms_events` | Payload bruto do evento varia por fabricante |
| `custody_chain` | `recording_segments` | Append-only log, lido como array inteiro |
| `isapi_capabilities` | `cameras` | Capabilities variam por modelo de câmera Hikvision |
| `parameters` | `reports` | Filtros de relatório variam por tipo |
| `settings` | `plugin_installations` | Config de plugin varia por plugin |
| `polygon` | `analytics_rois` | Array de pontos [[x,y], ...] normalizado |
| `config` | `analytics_rois` | Config adicional por plugin |
| `payload` | `audit_logs` | Dados adicionais variáveis por action |

### Consultas JSONB usadas

```sql
-- Buscar eventos com placa específica no payload
SELECT * FROM vms_events
WHERE tenant_id = $1
  AND payload->>'plate' = 'ABC1234';

-- Buscar custody chain de uma gravação
SELECT custody_chain FROM recording_segments WHERE id = $1;

-- Append a um custody chain existente
UPDATE recording_segments
SET custody_chain = custody_chain || $1::jsonb
WHERE id = $2;
```

### GIN Index para JSONB (quando necessário)

```sql
-- Habilitar busca rápida dentro do JSONB
CREATE INDEX idx_events_payload_gin ON vms_events USING GIN(payload);
-- Permite: WHERE payload @> '{"plate": "ABC1234"}'
```

---

## 5. Particionamento de Tabela (audit_logs)

### Por que particionar
- `audit_logs` é append-only e cresce indefinidamente
- Retenção: dados com > 12 meses podem ser dropados
- `DELETE FROM audit_logs WHERE occurred_at < ...` em tabela de 100M rows é proibitivo
- `DROP TABLE audit_logs_2024_01` é instantâneo

### Estratégia: RANGE por mês

```sql
CREATE TABLE audit_logs (
    id           UUID NOT NULL,
    tenant_id    UUID NOT NULL,
    occurred_at  TIMESTAMPTZ NOT NULL,
    ...
) PARTITION BY RANGE (occurred_at);

-- Partição criada mensalmente (automatizar via pg_partman ou cron)
CREATE TABLE audit_logs_2026_04
    PARTITION OF audit_logs
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

-- Drop de dados antigos é instantâneo
DROP TABLE audit_logs_2024_01;  -- sem VACUUM, sem bloqueio
```

---

## 6. Cascade Behavior (FK)

| Relacionamento | ON DELETE | Motivo |
|---------------|-----------|--------|
| `tenant` → `user` | CASCADE | Deleta tenant → remove todos os usuários |
| `tenant` → `camera` | CASCADE | Deleta tenant → remove todas as câmeras |
| `tenant` → `vms_events` | CASCADE | Deleta tenant → remove todos os eventos |
| `tenant` → `recording_segments` | CASCADE | Deleta tenant → remove todas as gravações do DB (arquivo físico: separado) |
| `tenant` → `notification_rules` | CASCADE | Regras pertencem ao tenant |
| `tenant` → `notification_logs` | CASCADE | Logs pertencem ao tenant |
| `camera` → `vms_events` | SET NULL | Evento permanece mesmo sem câmera (histórico) |
| `camera` → `recording_segments` | CASCADE | Sem câmera → segmento órfão sem uso |
| `camera` → `clips` | CASCADE | Clip sem câmera é inútil |
| `vms_events` → `clips` | SET NULL | Clip pode existir sem evento associado |
| `vms_events` → `notification_logs` | CASCADE | Log de evento sem evento é inútil |
| `notification_rules` → `notification_logs` | CASCADE | Log sem regra é inútil |
| `plugin_installations` → `analytics_events` | SET NULL | Evento analytics permanece no histórico |

---

## 7. Constraints e Unicidade

```sql
-- tenants
UNIQUE (slug)                           -- slug para URL/identificação

-- cameras
UNIQUE (rtmp_stream_key)               -- stream key global cross-tenant

-- api_keys
UNIQUE (tenant_id, owner_type, owner_id) -- 1 key por owner por tenant
INDEX  (prefix)                         -- lookup rápido por prefixo visível

-- users
INDEX  (email)                          -- login por email (+ verificação de unicidade por tenant no service)

-- analytics_pricing
UNIQUE (plugin_name)                    -- 1 preço por plugin

-- retention_policies
UNIQUE (tenant_id, data_type)           -- 1 política por tipo por tenant
```

---

## 8. Tipos de Dado Utilizados

| Tipo PostgreSQL | Uso | Observação |
|----------------|-----|------------|
| `UUID` | PKs e FKs | Gerado no app (Python `uuid.uuid4()`) |
| `TEXT` / `VARCHAR(n)` | Strings | VARCHAR com limite para campos críticos (email, slug) |
| `BOOLEAN` | Flags | `is_active`, `is_online`, `analytics_enabled` |
| `INTEGER` | Contadores e limites | `retention_days`, `max_cameras`, `streams_running` |
| `FLOAT` / `NUMERIC(10,n)` | Confidence, preços | FLOAT para ML scores, NUMERIC para dinheiro |
| `TIMESTAMPTZ` | Todos os timestamps | Timezone-aware. `server_default=func.now()` |
| `JSONB` | Semi-estruturado | Binary JSON, indexável por GIN |
| `TEXT` (não limitado) | Response bodies, user_agent | Sem limite de tamanho |

---

## 9. Encriptação em Repouso (campos sensíveis)

Os seguintes campos são encriptados antes de salvar no banco (Fernet symmetric encryption):

```python
# Em cameras/models.py
onvif_password: Mapped[str | None]  # armazenado como Fernet ciphertext
isapi_password: Mapped[str | None]  # armazenado como Fernet ciphertext
```

```python
# Em cameras/service.py
from cryptography.fernet import Fernet

fernet = Fernet(settings.encryption_key)

# Antes de salvar
encrypted = fernet.encrypt(plain_password.encode()).decode()

# Ao recuperar
plain = fernet.decrypt(encrypted.encode()).decode()
```

A `ENCRYPTION_KEY` é uma chave Fernet de 32 bytes base64, configurada via env var.

---

## 10. Migrations (Alembic)

```
api/
└── alembic/
    ├── env.py           → Configuração com SQLAlchemy sync URL
    └── versions/        → Migration scripts gerados automaticamente
```

**Workflow:**
```bash
# Gerar migration após alteração em models.py
alembic revision --autogenerate -m "add custody_chain to recording_segments"

# Aplicar migrations
alembic upgrade head

# Rollback 1 migration
alembic downgrade -1
```

**Observações:**
- `database_url_sync`: converte `asyncpg://` → `psycopg2://` para Alembic (Alembic não suporta async driver)
- Migrations de partição (`audit_logs`) são manuais — Alembic não detecta `PARTITION BY`
- Campos JSONB com `server_default='{}'` precisam de cast explícito no migration

---

## 11. Estratégia de Indexação Geral

```
Regra: INDEX WHERE THERE IS A WHERE CLAUSE

Queries frequentes identificadas:

1. Listar câmeras do tenant
   WHERE tenant_id = $1 [AND is_online = true]
   → INDEX (tenant_id, is_online)

2. Listar eventos por tenant e data
   WHERE tenant_id = $1 AND occurred_at BETWEEN $2 AND $3
   → INDEX (tenant_id, occurred_at DESC)

3. Buscar evento por placa
   WHERE plate = $1 [AND tenant_id = $2]
   → INDEX (plate)

4. Listar segmentos por câmera e data
   WHERE tenant_id = $1 AND camera_id = $2 AND started_at >= $3
   → INDEX (tenant_id, camera_id, started_at DESC)

5. Lookup de API key por prefixo
   WHERE prefix = $1 AND is_active = true
   → INDEX (prefix)

6. Audit log por usuário
   WHERE user_id = $1 AND occurred_at > $2
   → INDEX (user_id, occurred_at DESC)
```

---

## 12. Decisões Futuras a Considerar

| Problema potencial | Quando mitigar | Solução sugerida |
|-------------------|----------------|------------------|
| UUID v4 fragmentação em `analytics_events` | > 10M rows/mês | Migrar para UUID v7 (ordered) |
| SharedDB isolation | Vazamento de dado entre tenants | Implementar PostgreSQL Row Level Security (RLS) |
| `vms_events` cresce ilimitado | > 50M rows | Particionamento RANGE por `occurred_at` (como audit_logs) |
| Alembic lento em tabelas grandes | > 100M rows | Zero-downtime migrations via `pg_repack` ou `ALTER TABLE ... CONCURRENTLY` |
| `recording_segments.custody_chain` cresce | > 100 entries/segmento | Tabela separada `custody_chain_entries` |
| Analytics events de múltiplos plugins | > 1B rows | TimescaleDB (hypertable) para analytics_events |
