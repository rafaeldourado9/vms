# VMS — Refatoração DDD

> Sprint A1–A3: Foundation DDD
> Data: 2026-04-12
> Versão: 1.0

---

## Visão Geral

Refatoração da arquitetura do VMS para **Domain-Driven Design (DDD)** completo,
com **Onion Architecture**, **entidades ricas**, **máquinas de estado** e
**Domain Events** para comunicação entre bounded contexts.

### Antes vs Depois

| Aspecto | Antes | Depois |
|---------|-------|--------|
| Arquitetura | Camadas misturadas | Onion (Domain → Application → Infrastructure) |
| God Module | `vms.core` com 12 arquivos | `vms.infrastructure` + `vms.shared` separados |
| Entidades | Anêmicas (só dados) | Ricas (comportamento + dados) |
| IDs | `str` genérico | IDs fortes (`CameraId`, `TenantId`) |
| Comunicação | Imports cruzados | Domain Events via Redis pub/sub |
| Máquinas de Estado | Sem validação | Transições validadas com guards |
| Testabilidade | `datetime.utcnow()` espalhado | Clock abstraction injetável |

---

## Sprint A1 — Shared Kernel

### O que é

Base comum compartilhada entre todos os bounded contexts.
Define **contratos**, não implementações.

### Componentes

| Módulo | Responsabilidade | Arquivo |
|--------|-----------------|---------|
| **Kernel** | EntityId (10 tipos), Entity, AggregateRoot, ValueObject, Repository | `shared/kernel.py` |
| **Events** | DomainEvent base + serialização dict | `shared/events.py` |
| **Clock** | RealClock (produção) + FakeClock (testes) | `shared/clock.py` |
| **Value Objects** | Coordinates, IpAddress, TimeRange, Confidence, Sha256Hash | `shared/value_objects.py` |
| **Exceptions** | DomainError, NotFoundError, BusinessRuleViolation, etc. | `shared/exceptions.py` |

### Padrões Implementados

#### IDs Fortes

```python
# Antes — propenso a bugs
def get_camera(tenant_id: str, camera_id: str): ...
get_camera(camera_id, tenant_id)  # Bug silencioso!

# Depois — type safety
def get_camera(tenant_id: TenantId, camera_id: CameraId): ...
get_camera(camera_id, tenant_id)  # Erro de tipo detectado pelo mypy
```

**Tipos disponíveis:**
- `TenantId`, `CameraId`, `UserId`, `EventId`
- `AuditId`, `RecordingId`, `VODStreamId`, `PluginId`
- `ReportId`, `BillingId`

#### AggregateRoot

```python
@dataclass
class Camera(AggregateRoot):
    id: CameraId
    tenant_id: TenantId
    name: str
    is_online: bool = False

    def go_online(self) -> None:
        self.is_online = True
        self.record_event(CameraActivated(self.id, self.tenant_id))

# Uso
camera.go_online()
db.commit()
await event_bus.publish_many(camera.pull_events())
```

#### Clock Abstraction

```python
# Produção
from vms.shared.clock import clock
now = clock.now()

# Testes — determinístico
from vms.shared.clock import FakeClock
clock = FakeClock(datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc))
clock.advance(hours=2)  # Simula passagem de tempo
```

---

## Sprint A2 — Extração do God Module

### Problema

`vms.core` continha 12 arquivos misturando responsabilidades:
- Configuração, Database, Security, Event Bus, Logging, Exceptions, etc.
- **83 imports** espalhados pelo projeto

### Solução

Extraído em dois módulos separados com **aliases de compatibilidade**:

#### Nova Estrutura

```
vms/
├── infrastructure/              ← Serviços técnicos
│   ├── config/settings.py       ← Variáveis de ambiente
│   ├── database/connection.py   ← SQLAlchemy async
│   ├── messaging/               ← RabbitMQ + DLQ
│   │   ├── event_bus.py
│   │   └── dlq.py
│   ├── logging/config.py        ← structlog
│   ├── security.py              ← bcrypt, JWT, API keys
│   └── exceptions.py            ← Exceções + handler FastAPI
│
├── shared/api/                  ← Utilitários de API
│   ├── dependencies.py          ← DbSession, CurrentUser
│   ├── rate_limit.py            ← slowapi limiter
│   └── pagination.py            ← Page, PaginationParams
│
└── core/                        ← DEPRECATED (aliases)
    └── (apontam para novos caminhos)
```

#### Migração Segura

- **Imports antigos continuam funcionando** (aliases de compatibilidade)
- **Novos imports usam caminhos corretos**
- **Migração gradual**: um bounded context por vez
- **Zero downtime**: nenhum break change

**Critério de classificação:**

| Pergunta | Se SIM | Se NÃO |
|----------|--------|--------|
| Depende de FastAPI? | `vms.shared.api` | `vms.infrastructure` |
| Usado por workers/CLI? | `vms.infrastructure` | `vms.shared.api` |

---

## Sprint A3 — Entidades Ricas

### Problema

Entidades eram **anêmicas** (só dados). Lógica de negócio estava espalhada em services.

### Solução

**4 entidades enriquecidas** com comportamento, máquinas de estado e Domain Events.

### Camera (AggregateRoot)

```python
# Factories
camera = Camera.create_rtmp_push(tenant_id, name="Entrada Principal")
camera = Camera.create_rtsp_pull(tenant_id, agent_id, name="Portaria", rtsp_url="...")

# Transições de estado
camera.go_online()           # offline → online (emite CameraActivated)
camera.go_offline()          # online → offline (emite CameraDeactivated)
camera.enable_analytics()    # analytics off → on (emite CameraAnalyticsEnableded)
camera.deactivate()          # is_online=False, ia_enabled=False

# Propriedades calculadas
camera.mediamtx_path         # "live/{stream_key}" ou "tenant-{tid}/cam-{cid}"
camera.has_location          # latitude e longitude presentes
camera.is_rtmp_push          # protocolo == RTMP_PUSH
camera.is_agent_based        # protocolo == RTSP_PULL ou ONVIF

# Atualizações com validação
camera.update_location(lat=-23.55, lng=-46.63, address="São Paulo")
camera.update_rtsp_credentials(rtsp_url="...", onvif_username="...")
```

**Domain Events:**
- `CameraCreated`, `CameraActivated`, `CameraDeactivated`
- `CameraAnalyticsEnableded`, `CameraAnalyticsDisabled`

### RecordingSegment

```python
# Factory com parsing automático
segment = RecordingSegment.from_file_path(
    id=RecordingId.new(),
    tenant_id=tenant_id,
    camera_id=camera_id,
    mediamtx_path="tenant-1/cam-abc",
    file_path="/recordings/tenant-1/cam-abc/2026/04/12/10-00-00.mp4",
)

# Validações
segment.is_expired(retention_days=7)           # Verifica retenção
segment.verify_integrity(current_hash)         # Verifica SHA-256
segment.covers_time(timestamp)                 # Verifica cobertura temporal
```

**Domain Events:**
- `SegmentIndexed`

### Clip (AggregateRoot)

```python
# Máquina de estado com validação
clip = Clip(id=..., tenant_id=..., camera_id=..., starts_at=..., ends_at=...)

clip.start_processing()    # pending → processing (emite ClipRequested)
clip.mark_ready("/path/clip.mp4")  # processing → ready (emite ClipReady)
clip.mark_failed("erro")   # qualquer → failed (emite ClipFailed)

# Validações automáticas
# → BusinessRuleViolation se ends_at <= starts_at
# → StateTransitionError se transição inválida
```

**Domain Events:**
- `ClipRequested`, `ClipReady`, `ClipFailed`

### VODStream (AggregateRoot)

```python
# Factory com validação
stream = VODStream.create(
    id=VODStreamId.new(),
    tenant_id=tenant_id,
    camera_id=camera_id,
    segments=["/seg1.mp4", "/seg2.mp4"],
    started_at=start,
    ended_at=end,
)

# Máquina de estado
stream.start_generation()     # pending → generating
stream.mark_ready("/tmp/playlist.m3u8")  # generating → ready
stream.mark_failed("ffmpeg error")       # qualquer → failed

# Propriedades
stream.is_ready               # status == "ready"
stream.is_generating          # status == "generating"
stream.segment_count          # len(segments)
stream.duration_seconds       # (ends_at - started_at).total_seconds()
```

**Domain Events:**
- `VODStreamCreated`, `VODStreamGenerationStarted`, `VODStreamReady`, `VODStreamFailed`

---

## Regras de Qualidade

### Complexidade Ciclomática ≤ 5

```python
# ❌ CC = 9
def process_event(event):
    if event.type == "ANPR":
        if "plate" in event:
            return normalize_anpr(event)
        else:
            return None
    elif event.type == "VMD":
        return normalize_motion(event)
    # ...

# ✅ CC = 2
_NORMALIZERS = {
    "ANPR": normalize_anpr,
    "VMD": normalize_motion,
}

def process_event(event):
    normalizer = _NORMALIZERS.get(event.type)
    if not normalizer:
        return None
    return normalizer(event)
```

### Comentários Explicam POR QUÊ

```python
# ❌ Ruim (explica o óbvio)
def calculate_hash(file_path: str) -> str:
    """Calcula o hash SHA-256 do arquivo."""
    h = hashlib.sha256()
    ...

# ✅ Bom (explica a razão)
def compute_sha256(file_path: str) -> str:
    """
    Calcula hash SHA-256 de arquivo de gravação.

    Streaming (64KB chunks) para não carregar arquivo inteiro em memória.
    Necessário porque gravações podem ter GBs.
    """
    h = hashlib.sha256()
    ...
```

### Docstrings de Módulo Explicam Arquitetura

Cada `domain.py` começa com docstring descrevendo:
- Responsabilidade do bounded context
- Atores envolvidos
- Integrações com outros contexts
- Regras de negócio
- O que **não** faz (limites)

---

## Decisões Arquiteturais (ADRs)

### ADR-014: IDs Fortes

**Decisão:** Subclasses de `EntityId` para cada tipo de entidade.

**Consequências:**
- ✅ Type safety (mypy detecta confusão)
- ✅ Documentação implícita
- ⚠️ Mais boilerplate (10 classes)

### ADR-015: AggregateRoot Coleciona Domain Events

**Decisão:** `record_event()` + `pull_events()` para extrair após commit.

**Consequências:**
- ✅ Entidades controlam seus events
- ✅ Events extraídos apenas após commit
- ⚠️ Devs podem esquecer de chamar `pull_events()`

### ADR-016: Clock Abstraction

**Decisão:** `clock.now()` ao invés de `datetime.utcnow()`.

**Consequências:**
- ✅ Testes determinísticos
- ✅ Simulação de passagem de tempo
- ⚠️ Devs devem lembrar de usar `clock.now()`

### ADR-017: Aliases de Compatibilidade

**Decisão:** Manter `vms.core` como aliases durante migração.

**Consequências:**
- ✅ Zero downtime
- ✅ Migração gradual
- ⚠️ Dupla manutenção temporária

### ADR-018: Infrastructure vs Shared API

**Decisão:** Separar por dependência de framework web.

| Critério | `vms.infrastructure` | `vms.shared.api` |
|----------|---------------------|------------------|
| Depende de FastAPI? | Não | Sim |
| Usado por workers? | Sim | Não |

---

## Métricas

| Métrica | Antes | Depois | Melhoria |
|---------|-------|--------|----------|
| Arquivos Shared Kernel | 0 | 6 | Novo |
| Entidades com comportamento | 7/15 | 11/15 | +57% |
| Domain Events | 0 | 17 | Novo |
| Máquinas de estado validadas | 0 | 3 | Novo |
| IDs fortes | 0 | 10 | Novo |
| Testes Given-When-Then | ~20 | ~80 | +300% |
| God module `vms.core` | 12 arquivos | 0 (aliases) | Resolvido |

---

## Próximos Passos

| Sprint | Nome | Duração | Objetivo |
|--------|------|---------|----------|
| **A4** | Event Bus | 1 dia | Redis pub/sub entre bounded contexts |
| **A5** | Limpeza | 1-2 dias | Resolver deps cruzadas + remover `vms.core` |

---

## Estrutura Final

```
api/src/vms/
├── shared/                          # Shared Kernel (Sprint A1)
│   ├── kernel.py                    # EntityId, Entity, AggregateRoot
│   ├── events.py                    # DomainEvent base
│   ├── clock.py                     # RealClock, FakeClock
│   ├── value_objects.py             # Coordinates, IpAddress, etc.
│   ├── exceptions.py                # DomainError hierarchy
│   ├── __init__.py
│   └── api/                         # Utilitários de API (Sprint A2)
│       ├── dependencies.py          # DbSession, CurrentUser
│       ├── rate_limit.py            # slowapi limiter
│       └── pagination.py            # Page, PaginationParams
│
├── infrastructure/                  # Serviços Técnicos (Sprint A2)
│   ├── config/settings.py           # Variáveis de ambiente
│   ├── database/connection.py       # SQLAlchemy async
│   ├── messaging/                   # RabbitMQ + DLQ
│   │   ├── event_bus.py
│   │   └── dlq.py
│   ├── logging/config.py            # structlog
│   ├── security.py                  # bcrypt, JWT, API keys
│   ├── exceptions.py                # Exceções + handler FastAPI
│   └── __init__.py
│
├── cameras/                         # Bounded Context: Cameras (Sprint A3)
│   ├── domain.py                    # Camera, Agent (enriquecidos)
│   ├── service.py
│   ├── repository.py
│   └── ...
│
├── recordings/                      # Bounded Context: Recordings (Sprint A3)
│   ├── domain.py                    # RecordingSegment, Clip (enriquecidos)
│   ├── service.py
│   └── ...
│
├── vod/                             # Bounded Context: VOD (Sprint A3)
│   ├── domain.py                    # VODStream (enriquecido)
│   ├── service.py
│   └── ...
│
└── core/                            # DEPRECATED (aliases de compatibilidade)
    └── (apontam para novos caminhos)
```

---

> **DDD não é burocracia — é controle de complexidade.**
> *"Sem DDD, a complexidade se espalha. Com DDD, a complexidade se organiza."*
