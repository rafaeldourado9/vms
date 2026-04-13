# 🏛️ VMS DDD + GOVERNO — Guia Completo de Refatoração

> Complemento ao VMS_PROMPT_KIT.md
> Versão: 1.0 · Data: 2026-04-12
> **Objetivo:** Refatorar para 100% DDD + Adicionar Sprints 8-15 (Governo)

---

## 📋 ÍNDICE

1. [Por que DDD?](#por-que-ddd)
2. [Arquitetura DDD Alvo](#arquitetura-ddd-alvo)
3. [Plano de Refatoração Passo a Passo](#plano-de-refatoração-passo-a-passo)
4. [Controle de Complexidade](#controle-de-complexidade)
5. [Sprints 8-15: Governo](#sprints-8-15-governo)
6. [Prompt Kit Atualizado](#prompt-kit-atualizado)
7. [ADRs DDD](#adrs-ddd)

---

## POR QUE DDD?

### Problemas da Arquitetura Atual

```
❌ vms.core é god module (15 arquivos misturados)
❌ Dependências cruzadas entre bounded contexts
❌ Services anêmicos (CRUD glorificado)
❌ Sem Domain Events reais (VmsEvent ≠ DomainEvent)
❌ Sem Value Objects (tudo é string primitiva)
❌ Naming inconsistente
```

### O que DDD Resolve

```
✅ Bounded Contexts isolados (sem imports cruzados)
✅ Entidades Ricas (comportamento + dados)
✅ Value Objects (tipos fortes para conceitos de domínio)
✅ Domain Events (comunicação entre contexts)
✅ Ubiquitous Language (naming consistente)
✅ Anti-Corruption Layers (integração externa segura)
```

---

## 🏗️ ARQUITETURA DDD ALVO

### Visão Geral (Onion Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│                    FRAMEWORKS & DRIVERS                     │
│  FastAPI │ React │ PostgreSQL │ Redis │ RabbitMQ │ MediaMTX │
├─────────────────────────────────────────────────────────────┤
│                    ADAPTERS (Interface)                     │
│  Routers │ Repositories │ Webhooks │ SSE │ ISAPI Client     │
├─────────────────────────────────────────────────────────────┤
│                    APPLICATION LAYER                        │
│  Services │ Use Cases │ Commands │ Queries │ Event Handlers  │
├─────────────────────────────────────────────────────────────┤
│                    DOMAIN LAYER (CORE)                      │
│  Entities │ Value Objects │ Domain Events │ Aggregates       │
│  Domain Services │ Repository Interfaces │ Specifications   │
└─────────────────────────────────────────────────────────────┘

DEPENDENCY RULE: Dependências apontam PARA DENTRO.
                 Domain NUNCA depende de Application ou Infrastructure.
```

### Estrutura de Diretórios Final

```
api/src/vms/
│
├── shared/                          # Shared Kernel
│   ├── kernel.py                    # Tipos base, IDs, Exceptions de domínio
│   ├── value_objects.py             # Value Objects compartilhados
│   ├── events.py                    # DomainEvent base
│   └── clock.py                     # Abstração de tempo (testável)
│
├── iam/                             # Bounded Context: IAM
│   ├── domain/
│   │   ├── entities.py              # Tenant, User, ApiKey
│   │   ├── value_objects.py         # Email, Password, Role
│   │   ├── events.py                # TenantCreated, UserLoggedIn
│   │   └── exceptions.py            # AuthError, TenantNotFoundError
│   ├── application/
│   │   ├── commands/                # CreateUserCommand, etc.
│   │   ├── queries/                 # GetUserByIdQuery, etc.
│   │   └── services/                # AuthService, TenantService
│   ├── infrastructure/
│   │   ├── models.py                # SQLAlchemy models
│   │   ├── repositories.py          # UserRepository impl
│   │   └── jwt.py                   # JWT provider
│   └── interfaces/
│       └── router.py                # FastAPI endpoints
│
├── cameras/                         # Bounded Context: Cameras
│   ├── domain/
│   │   ├── entities.py              # Camera, Agent, PTZ
│   │   ├── value_objects.py         # StreamUrl, RetentionPolicy, Coordinates
│   │   ├── events.py                # CameraCreated, CameraWentOffline
│   │   └── exceptions.py            # CameraNotFoundError
│   ├── application/
│   │   ├── commands/
│   │   ├── queries/
│   │   └── services/                # CameraService, PTZService
│   ├── infrastructure/
│   │   ├── models.py
│   │   ├── repositories.py
│   │   ├── mediamtx.py              # MediaMTX client
│   │   └── isapi/                   # ISAPI clients
│   │       ├── client.py            # Base ISAPIClient
│   │       ├── hikvision.py         # Hikvision ISAPI impl
│   │       └── intelbras.py         # Intelbras ISAPI impl
│   └── interfaces/
│       └── router.py
│
├── streaming/                       # Bounded Context: Streaming
│   ├── domain/
│   │   ├── entities.py              # StreamSession, ViewerToken
│   │   ├── value_objects.py         # StreamPath, Protocol
│   │   └── events.py                # StreamStarted, StreamStopped
│   ├── application/
│   │   └── services/                # StreamingService, AuthService
│   ├── infrastructure/
│   │   ├── models.py
│   │   ├── repositories.py
│   │   └── mediamtx.py
│   └── interfaces/
│       └── router.py
│
├── recordings/                      # Bounded Context: Recordings
│   ├── domain/
│   │   ├── entities.py              # RecordingSegment, Clip
│   │   ├── value_objects.py         # FilePath, Sha256Hash, TimeRange
│   │   ├── events.py                # SegmentIndexed, ClipReady
│   │   └── custody.py               # CustodyChain (cadeia de custódia)
│   ├── application/
│   │   ├── commands/
│   │   ├── queries/
│   │   └── services/                # RecordingService, CustodyService
│   ├── infrastructure/
│   │   ├── models.py
│   │   ├── repositories.py
│   │   └── integrity.py             # SHA-256 verification
│   └── interfaces/
│       └── router.py
│
├── vod/                             # Bounded Context: VOD (já existe)
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   └── interfaces/
│
├── events/                          # Bounded Context: Events
│   ├── domain/
│   │   ├── entities.py              # VmsEvent, EventType
│   │   ├── value_objects.py         # Confidence, Severity, Plate
│   │   ├── events.py                # EventPublished
│   │   └── dedup.py                 # Dedup logic
│   ├── application/
│   │   └── services/                # EventService, DedupService
│   ├── infrastructure/
│   │   ├── models.py
│   │   ├── repositories.py
│   │   └── redis_dedup.py           # Redis dedup impl
│   └── interfaces/
│       └── router.py
│
├── analytics/                       # Bounded Context: Analytics
│   ├── domain/
│   │   ├── entities.py              # PluginInstallation, AnalyticsEvent
│   │   ├── value_objects.py         # ROI, PluginConfig
│   │   └── events.py                # PluginDetected
│   ├── application/
│   │   └── services/                # PluginService, ROIManager
│   ├── infrastructure/
│   │   ├── models.py
│   │   ├── repositories.py
│   │   └── plugins/                 # Plugin implementations
│   └── interfaces/
│       └── router.py
│
├── audit/                           # Bounded Context: Audit (NOVO - Sprint 8)
│   ├── domain/
│   │   ├── entities.py              # AuditLog
│   │   ├── value_objects.py         # Action, ResourceId, IpAddress
│   │   └── events.py                # AuditLogCreated
│   ├── application/
│   │   └── services/                # AuditService
│   ├── infrastructure/
│   │   ├── models.py
│   │   └── repositories.py
│   └── interfaces/
│       └── router.py
│
├── billing/                         # Bounded Context: Billing (NOVO - Sprint 13)
│   ├── domain/
│   │   ├── entities.py              # BillingPlan, UsageRecord
│   │   ├── value_objects.py         # MetricValue, Period
│   │   └── events.py                # QuotaExceeded
│   ├── application/
│   │   └── services/                # BillingService, QuotaChecker
│   ├── infrastructure/
│   │   ├── models.py
│   │   └── repositories.py
│   └── interfaces/
│       └── router.py
│
├── reports/                         # Bounded Context: Reports (NOVO - Sprint 10)
│   ├── domain/
│   │   ├── entities.py              # Report
│   │   └── value_objects.py         # ReportType, Parameters
│   ├── application/
│   │   └── services/                # ReportService, PDFGenerator
│   ├── infrastructure/
│   │   ├── models.py
│   │   ├── repositories.py
│   │   └── templates/               # Jinja2 HTML templates
│   └── interfaces/
│       └── router.py
│
├── compliance/                      # Bounded Context: Compliance (NOVO - Sprint 14)
│   ├── domain/
│   │   ├── entities.py              # ConsentRecord, RetentionPolicy
│   │   └── value_objects.py         # PersonalData, AnonymizedData
│   ├── application/
│   │   └── services/                # LGPDService, RetentionService
│   ├── infrastructure/
│   │   ├── models.py
│   │   └── repositories.py
│   └── interfaces/
│       └── router.py
│
├── webhooks/                        # Cross-cutting: Webhooks Externos
│   ├── hikvision/
│   │   ├── normalizers.py           # Tabela de dispatch
│   │   └── router.py
│   ├── intelbras/
│   │   ├── normalizers.py
│   │   └── router.py
│   └── shared/
│       └── event_ingestor.py        # Ingester comum → Events context
│
└── infrastructure/                  # Shared Infrastructure
    ├── database/
    │   ├── connection.py            # Engine, session factory
    │   └── base.py                  # Base model
    ├── messaging/
    │   ├── redis.py                 # Redis client + pub/sub
    │   └── rabbitmq.py              # RabbitMQ client
    ├── logging/
    │   └── config.py                # Structured logging setup
    └── config/
        └── settings.py              # Settings (env vars)
```

---

## 📐 PLANO DE REFACTORIZAÇÃO PASSO A PASSO

### Fase 1: Fundação (2-3 dias)

#### 1.1 Criar Shared Kernel

```python
# api/src/vms/shared/kernel.py
"""
Shared Kernel — tipos base para todos os bounded contexts.

REGRA: Este módulo NUNCA importa de outro bounded context.
       Ele define contratos, não implementações.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid4


# ─── IDs Fortes (evita confusão entre tipos de ID) ──────────────────────────

@dataclass(frozen=True)
class EntityId:
    """ID forte para entidades — previne confusão entre tipos de ID."""
    value: UUID

    @classmethod
    def new(cls) -> EntityId:
        return cls(uuid4())

    def __str__(self) -> str:
        return str(self.value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EntityId):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)


class TenantId(EntityId): ...
class CameraId(EntityId): ...
class UserId(EntityId): ...
class EventId(EntityId): ...
class AuditId(EntityId): ...


# ─── Entity Base ─────────────────────────────────────────────────────────────

@dataclass
class Entity:
    """Entidade base — toda entidade tem identidade e igualdade por ID."""
    id: EntityId

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


# ─── Aggregate Root ──────────────────────────────────────────────────────────

@dataclass
class AggregateRoot(Entity):
    """
    Aggregate Root — entidade principal de um aggregate.
    Coleciona Domain Events que ocorreram dentro do aggregate.
    """
    _domain_events: list[DomainEvent] = field(default_factory=list, repr=False)

    def record_event(self, event: DomainEvent) -> None:
        """Registra um Domain Event (será publicado após commit)."""
        self._domain_events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        """Extrai e limpa os events pendentes."""
        events = list(self._domain_events)
        self._domain_events.clear()
        return events


# ─── Domain Event ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DomainEvent:
    """
    Domain Event — algo que aconteceu no passado.
    Imutável por definição. Usado para comunicação entre bounded contexts.
    """
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def event_type(self) -> str:
        """Nome do evento: 'CameraCreated', 'AuditLogCreated', etc."""
        return self.__class__.__name__


# ─── Value Object Base ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class ValueObject:
    """
    Value Object — definido por seus atributos, não por identidade.
    Imutável. Igualdade estrutural.
    """
    pass


# ─── Repository Port (Interface) ─────────────────────────────────────────────

class Repository(Protocol):
    """Interface base para repositórios."""

    async def get_by_id(self, id: EntityId) -> Entity | None: ...
    async def add(self, entity: Entity) -> None: ...
    async def remove(self, entity: Entity) -> None: ...


# ─── Domain Exception ────────────────────────────────────────────────────────

class DomainError(Exception):
    """Exceção de domínio — regra de negócio violada."""
    pass


class NotFoundError(DomainError):
    """Entidade não encontrada."""
    pass


class BusinessRuleViolation(DomainError):
    """Regra de negócio violada."""
    pass
```

#### 1.2 Criar Clock Abstraction (testabilidade)

```python
# api/src/vms/shared/clock.py
"""
Clock abstraction — permite mock de tempo em testes.

Em vez de datetime.utcnow() espalhado, use clock.now().
Em produção: RealClock. Em testes: FakeClock.
"""
from datetime import datetime, timezone
from abc import ABC, abstractmethod


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...


class RealClock(Clock):
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FakeClock(Clock):
    def __init__(self, fixed_time: datetime) -> None:
        self._fixed_time = fixed_time

    def now(self) -> datetime:
        return self._fixed_time


# Instância global (substituível em testes)
clock: Clock = RealClock()
```

#### 1.3 Criar Value Objects Compartilhados

```python
# api/src/vms/shared/value_objects.py
"""Value Objects compartilhados entre bounded contexts."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar

from vms.shared.kernel import ValueObject


@dataclass(frozen=True)
class Coordinates(ValueObject):
    """Coordenadas geográficas de uma câmera."""
    latitude: Decimal
    longitude: Decimal

    def __post_init__(self) -> None:
        if not (-90 <= self.latitude <= 90):
            raise ValueError(f"Latitude inválida: {self.latitude}")
        if not (-180 <= self.longitude <= 180):
            raise ValueError(f"Longitude inválida: {self.longitude}")

    @classmethod
    def brazil_center(cls) -> Coordinates:
        """Centro aproximado do Brasil."""
        return cls(Decimal("-14.2350"), Decimal("-51.9253"))

    def __str__(self) -> str:
        return f"{self.latitude:.4f}, {self.longitude:.4f}"


@dataclass(frozen=True)
class IpAddress(ValueObject):
    """Endereço IP validado."""
    value: str

    # Regex simples para IPv4
    _IPV4_RE: ClassVar = r"^\d{1,3}(\.\d{1,3}){3}$"

    def __post_init__(self) -> None:
        import re
        if not re.match(self._IPV4_RE, self.value):
            # Pode ser IPv6 ou hostname — aceita sem validar
            pass

    @property
    def is_private(self) -> bool:
        """Verifica se é IP privado (192.168.x.x, 10.x.x.x, etc)."""
        return (
            self.value.startswith("192.168.")
            or self.value.startswith("10.")
            or self.value.startswith("172.")
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class TimeRange(ValueObject):
    """Intervalo de tempo com início e fim."""
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("end deve ser posterior a start")

    @property
    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()

    def contains(self, timestamp: datetime) -> bool:
        return self.start <= timestamp <= self.end


@dataclass(frozen=True)
class Confidence(ValueObject):
    """Confiança de detecção (0.0 a 1.0)."""
    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"Confiança deve estar entre 0 e 1: {self.value}")

    def __float__(self) -> float:
        return self.value

    @property
    def is_high(self) -> bool:
        return self.value >= 0.8

    @property
    def is_low(self) -> bool:
        return self.value < 0.5


@dataclass(frozen=True)
class Sha256Hash(ValueObject):
    """Hash SHA-256 de arquivo."""
    value: str

    def __post_init__(self) -> None:
        if len(self.value) != 64:
            raise ValueError(f"Hash SHA-256 deve ter 64 chars: {len(self.value)}")

    def __str__(self) -> str:
        return self.value
```

---

### Fase 2: Extrair vms.core (1-2 dias)

```bash
# Antes (god module):
vms.core/
├── config.py          → vms.infrastructure.config.settings
├── database.py        → vms.infrastructure.database.connection
├── deps.py            → vms.shared.api.dependencies
├── event_bus.py       → vms.infrastructure.messaging.event_bus
├── rate_limit.py      → vms.shared.api.rate_limit
├── exceptions.py      → vms.shared.kernel (já criado)
├── logging_config.py  → vms.infrastructure.logging.config
└── ...

# Depois (organizado):
vms.infrastructure/
├── database/connection.py
├── messaging/event_bus.py
├── logging/config.py
└── config/settings.py

vms.shared/
├── kernel.py
├── clock.py
├── value_objects.py
└── api/
    ├── dependencies.py
    └── rate_limit.py
```

**Prompt para executar:**

```
Refatore o módulo vms.core em módulos separados seguindo DDD.

Regras:
1. Cada arquivo vai para seu novo caminho
2. Atualize TODOS os imports no projeto (use grep para encontrar)
3. Mantenha compatibilidade: crie aliases temporários nos caminhos antigos
4. Teste após cada move: pytest tests/ -x

Ordem:
1. config.py → infrastructure/config/settings.py
2. database.py → infrastructure/database/connection.py
3. event_bus.py → infrastructure/messaging/event_bus.py
4. logging_config.py → infrastructure/logging/config.py
5. deps.py → shared/api/dependencies.py
6. rate_limit.py → shared/api/rate_limit.py

Após cada move: rode pytest e verifique que nada quebrou.
```

---

### Fase 3: Enriquecer Entidades (2-3 dias)

**Antes (anêmico):**
```python
@dataclass
class Camera:
    id: str
    name: str
    rtsp_url: str | None
    is_active: bool
    # ... só dados
```

**Depois (rico com comportamento):**
```python
@dataclass
class Camera(AggregateRoot):
    """
    Câmera de vigilância.

    Aggregate Root do Camera Aggregate.
    Controla streaming, PTZ, analytics e gravações.
    """
    id: CameraId
    tenant_id: TenantId
    name: CameraName  # Value Object
    location: Coordinates | None  # Value Object
    stream_config: StreamConfig  # Value Object
    is_active: bool
    last_seen_at: datetime | None

    def go_online(self) -> None:
        """Transição de estado: câmera conectou."""
        if not self.is_active:
            raise BusinessRuleViolation("Câmera inativa não pode ficar online")
        self.last_seen_at = clock.now()
        self.record_event(CameraWentOnline(self.id, self.tenant_id))

    def go_offline(self) -> None:
        """Transição de estado: câmera desconectou."""
        self.record_event(CameraWentOffline(self.id, self.tenant_id))

    def get_stream_url(self, protocol: StreamProtocol) -> StreamUrl:
        """Gera URL de streaming para protocolo específico."""
        return StreamUrl.build(
            protocol=protocol,
            tenant_id=self.tenant_id,
            camera_id=self.id,
        )

    def enable_analytics(self, plugins: list[str]) -> None:
        """Habilita analytics na câmera."""
        if not self.is_active:
            raise BusinessRuleViolation("Câmera inativa não pode ter analytics")
        # ... lógica
        self.record_event(AnalyticsEnabled(self.id, plugins))
```

---

### Fase 4: Resolver Dependências Cruzadas (1-2 dias)

**Problema:** `recordings.service` importa `cameras.models`

**Solução:** Inverter dependência

```python
# ❌ Antes (recordings depende de cameras)
from vms.cameras.models import CameraModel

class RecordingService:
    async def cleanup_expired_segments(self, camera_id: str, ...):
        camera = await db.get(CameraModel, camera_id)
        retention = camera.retention_days
        ...

# ✅ Depois (dependência injetada)
class CameraPort(Protocol):
    async def get_retention_days(self, camera_id: str) -> int: ...

class RecordingService:
    def __init__(self, camera_port: CameraPort) -> None:
        self._cameras = camera_port

    async def cleanup_expired_segments(self, camera_id: str, ...):
        retention = await self._cameras.get_retention_days(camera_id)
        ...
```

---

### Fase 5: Adicionar Domain Events (1 dia)

```python
# api/src/vms/cameras/domain/events.py
"""Domain Events do Cameras Context."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from vms.shared.kernel import DomainEvent, CameraId, TenantId


@dataclass(frozen=True)
class CameraCreated(DomainEvent):
    camera_id: CameraId
    tenant_id: TenantId
    name: str


@dataclass(frozen=True)
class CameraWentOnline(DomainEvent):
    camera_id: CameraId
    tenant_id: TenantId
    connected_at: datetime


@dataclass(frozen=True)
class CameraWentOffline(DomainEvent):
    camera_id: CameraId
    tenant_id: TenantId
    disconnected_at: datetime


@dataclass(frozen=True)
class CameraUpdated(DomainEvent):
    camera_id: CameraId
    tenant_id: TenantId
    changed_fields: list[str]


@dataclass(frozen=True)
class CameraDeleted(DomainEvent):
    camera_id: CameraId
    tenant_id: TenantId
    deleted_at: datetime
```

---

### Fase 6: Implementar Event Bus (1 dia)

```python
# api/src/vms/infrastructure/messaging/event_bus.py
"""
Event Bus — publica e subscreve Domain Events.

Usa Redis pub/sub para comunicação entre bounded contexts.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Awaitable
from typing import Any

import redis.asyncio as aioredis

from vms.shared.kernel import DomainEvent

logger = logging.getLogger(__name__)

# Handler: recebe DomainEvent e processa assincronamente
EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventBus:
    """
    Barramento de eventos de domínio.

    Publica eventos no Redis pub/sub e dispatch para handlers locais.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis
        self._handlers: dict[str, list[EventHandler]] = {}
        self._pubsub: aioredis.client.PubSub | None = None

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Registra handler para tipo de evento."""
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event: DomainEvent) -> None:
        """Publica evento para todos os bounded contexts interessados."""
        payload = {
            "event_type": event.event_type,
            "data": self._serialize_event(event),
            "occurred_at": event.occurred_at.isoformat(),
        }
        await self._redis.publish("domain_events", json.dumps(payload))
        await self._dispatch_locally(event)

    async def _dispatch_locally(self, event: DomainEvent) -> None:
        """Dispatch para handlers locais."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    "Erro ao processar evento %s",
                    event.event_type,
                    extra={"event": self._serialize_event(event)},
                )

    @staticmethod
    def _serialize_event(event: DomainEvent) -> dict[str, Any]:
        """Serializa Domain Event para dict."""
        from dataclasses import asdict
        return asdict(event)

    async def start_listening(self) -> None:
        """Inicia listener de Redis pub/sub (background task)."""
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe("domain_events")

        async for message in self._pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                # Reconstruir evento e dispatch
                # (implementação simplificada — em produção usar registry)
                logger.debug("Evento recebido: %s", data.get("event_type"))


# Instância global (injetada via DI)
event_bus: EventBus | None = None
```

---

## 🎛️ CONTROLE DE COMPLEXIDADE

### Regra #1: Comentários Explicam POR QUÊ, não O QUÊ

```python
# ❌ Ruim (explica o óbvio)
def calculate_hash(file_path: str) -> str:
    """Calcula o hash SHA-256 do arquivo."""  # ← Já sei pelo nome da função
    h = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

# ✅ Bom (explica a razão)
def compute_sha256(file_path: str) -> str:
    """
    Calcula hash SHA-256 de arquivo de gravação.

    Streaming (64KB chunks) para não carregar arquivo inteiro em memória.
    Necessário porque gravações podem ter GBs.
    """
    h = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()
```

### Regra #2: Docstrings de Módulo Explicam Arquitetura

```python
# api/src/vms/recordings/domain/__init__.py
"""
Bounded Context: Recordings — Domínio

Responsabilidade:
    Gerenciar gravações de vídeo, segmentos e clipes.
    Garantir integridade via cadeia de custódia (SHA-256).

Atores:
    - MediaMTX: gera segmentos de 60s
    - RecordingService: indexa e consulta segmentos
    - CustodyService: verifica integridade e gera exports forenses
    - RetentionWorker: limpa segmentos expirados (ARQ cron)

Integrações:
    - Events Context: publica SegmentIndexed event
    - Audit Context: registra viewing/downloading/export
    - VOD Context: fornece segmentos para geração de HLS

Regras de Negócio:
    1. Segmento só pode ser deletado após expirar retenção
    2. Hash SHA-256 calculado no momento da indexação (imutável)
    3. Cadeia de custódia registra TODO acesso à gravação
    4. Export forense gera ZIP com todos os artefatos de integridade

Não faz:
    - Transcoding (responsabilidade do VOD Context)
    - Streaming ao vivo (responsabilidade do Streaming Context)
    - Detecção de eventos (responsabilidade do Events Context)
"""
```

### Regra #3: ADRs Documentam Decisões

Cada decisão arquitetural importante vira um ADR no projeto:

```markdown
# ADR-009: Domain Events para Comunicação entre Contexts

## Contexto
Bounded contexts precisam se comunicar sem acoplamento direto.
Usar imports cruzados viola isolamento de contextos.

## Decisão
Usar Domain Events publicados via Redis pub/sub.
Cada context subscreve eventos de interesse.

## Consequências
+ Desacoplamento total entre contexts
+ Fácil adicionar novos consumers
- Eventual consistency (não imediato)
- Necessário idempotência nos handlers
```

### Regra #4: Complexidade Ciclomática ≤ 5

```python
# ❌ CC = 9 (muito alto)
def normalize_event(raw: dict, camera: Camera) -> dict | None:
    event_type = raw.get("eventType")
    if event_type == "ANPR":
        if "plate" in raw:
            return normalize_anpr(raw, camera)
        else:
            return None
    elif event_type == "VMD":
        return normalize_motion(raw, camera)
    elif event_type == "Face":
        if "faceId" in raw:
            return normalize_face(raw, camera)
        else:
            return None
    else:
        return None

# ✅ CC = 2 (tabela de dispatch)
_NORMALIZERS = {
    "ANPR": normalize_anpr,
    "VMD": normalize_motion,
    "Face": normalize_face,
}

def normalize_event(raw: dict, camera: Camera) -> dict | None:
    event_type = raw.get("eventType")
    normalizer = _NORMALIZERS.get(event_type)
    if not normalizer:
        return None
    return normalizer(raw, camera)
```

### Regra #5: Arquivos ≤ 300 linhas

Se um arquivo passa de 300 linhas, quebre em módulos menores:

```
# ❌ Antes: recordings/service.py (450 linhas)

# ✅ Depois:
recordings/application/services/
├── recording_service.py       # 120 linhas — CRUD básico
├── custody_service.py         # 90 linhas — cadeia de custódia
├── retention_service.py       # 80 linhas — limpeza e retenção
└── export_service.py          # 110 linhas — export forense
```

---

## 🗺️ ROADMAP ATUALIZADO — SPRINTS 0-15

### Roadmap Completo (Refatoração DDD + Governo)

```
FASE A — DDD Foundation (refatoração)
  Sprint A1  Shared Kernel          — Entity, Value Object, DomainEvent base
  Sprint A2  Extrair Core           — Quebrar vms.core god module
  Sprint A3  Enriquecer Entities    — Adicionar comportamento às entidades
  Sprint A4  Event Bus              — Redis pub/sub entre bounded contexts
  Sprint A5  Resolver Dependencies  — Eliminar imports cruzados

FASE B — Government Sprints (novas features)
  Sprint 8   Audit Trail            — AuditLog imutável, quem fez o quê
  Sprint 9   Cadeia de Custódia     — SHA-256, integridade, forense
  Sprint 10  Relatórios Gov         — PDF assinado, agendado
  Sprint 11  Hikvision ISAPI Deep   — Smart Events, VCA, configuração remota
  Sprint 12  Intelbras Deep         — Face Rec, People Counting nativo
  Sprint 13  Financeiro & Licenças  — Faturamento, cotas, alertas
  Sprint 14  Compliance & LGPD      — Retenção, anonimização, e-SIC
  Sprint 15  HA & Resiliência       — SLA 99.9%, failover, DR

FASE C — Original (não mudado)
  Sprint 0   Foundation Fixes       — Webhooks ALPR, Events frontend
  Sprint 1   Camera Intelligence   — Dual-Pipeline RT
  Sprint 2   Tactical Map           — Mapa real com pins
  Sprint 3   LPR Webhooks           — Intelbras + Hikvision → frontend
  Sprint 4   Batch Pipeline         — Processamento offline
  Sprint 5   UI/UX Polish           — Timeline, Analytics dashboard
  Sprint 6   Performance & Scale    — KV Cache, GPU arbiter
  Sprint 7   Production Hardening   — Multi-tenant, observabilidade
```

### Ordem Recomendada de Execução

```
SEM DDD ANTES:          COM DDD ANTES:
Sprint 0 (2 bugs)       Sprint A1-A2 (fundação DDD, 3-5 dias)
Sprint 1-7 (features)   Sprint 0 (bugs agora são mais fáceis)
Sprint 8-15 (gov)       Sprint 1-7 (features)
                        Sprint 8-15 (gov, muito mais fáceis com DDD)
```

**Minha recomendação:** Faça **Sprint A1-A2 primeiro** (fundação DDD). Os sprints seguintes ficam 40-60% mais rápidos.

---

## 📋 PROMPT KIT ATUALIZADO (DDD + GOVERNO)

### P0 — Injeção de Contexto (Atualizado)

```
Você é meu pair programmer sênior neste projeto VMS (Video Management System).

ESTE PROJETO SEGUE DDD (DOMAIN-DRIVEN DESIGN):
- Bounded Contexts isolados (sem imports cruzados)
- Entidades Ricas (comportamento + dados, não só dados)
- Value Objects (tipos fortes para conceitos de domínio)
- Domain Events (comunicação entre contexts via Redis pub/sub)
- Repository Pattern (interfaces no domínio, impl em infra)
- Onion Architecture (dependências apontam para dentro)

ANTES DE QUALQUER COISA, leia:
- VMS_PROMPT_KIT.md         → stack, roadmap, prompts
- VMS_DDD_GOVERNO.md        → arquitetura DDD alvo + governo
- ARCHITECTURE.md           → modelos de dados, fluxos
- API.md                    → contratos de API
- PLUGINS.md                → catálogo de plugins

CONFIRME que entendeu:
1. Stack técnico (FastAPI, PostgreSQL, Redis, RabbitMQ, MediaMTX, YOLOv8, React)
2. Arquitetura DDD (onion, bounded contexts, domain events)
3. Sprints de governo (8-15: audit, custody, reports, ISAPI, billing, LGPD, HA)
4. Regras de qualidade (CC ≤ 5, SOLID, TDD, comentários de POR QUÊ)

REGRAS INVIOLÁVEIS:

DDD:
1. Entities têm comportamento — não são só dados
2. Value Objects são imutáveis e definidos por atributos
3. Domain Events comunicam entre bounded contexts
4. Repository interfaces ficam no domínio, implementação em infra
5. Bounded contexts NÃO importam uns dos outros (use events ou ports)
6. Aggregate Roots controlam consistência interna

QUALIDADE:
7. CC ≤ 5 — se passar, quebre em funções privadas
8. Tabela de dispatch — NUNCA elif por fabricante
9. TDD OBRIGATÓRIO — teste antes do código
10. Comentários explicam POR QUÊ, não O QUÊ
11. Docstrings de módulo explicam arquitetura
12. Arquivos ≤ 300 linhas — quebre se passar

GOVERNO:
13. AuditLog é append-only (nunca UPDATE/DELETE)
14. SHA-256 no momento da gravação (integridade)
15. Webhooks sempre retornam 200 (não derrube câmeras)
16. Face recognition requer consentimento explícito (LGPD)
17. Anonimização > Deleção (manter estatísticas)
18. Relatórios PDF gerados async (nunca sync no request)

Confirme que leu os arquivos e liste os 5 pontos de entendimento.
```

### P2 — Planejamento DDD (Novo)

```
Feature: [DESCREVA]

Planeje a implementação seguindo DDD:

1. QUAL Bounded Context é afetado?
2. É um novo BC ou extensão de existente?
3. Quais ENTITIES estão envolvidas?
4. Quais VALUE OBJECTS são necessários?
5. Quais DOMAIN EVENTS serão emitidos?
6. Qual AGGREGATE é o root?
7. Há dependências de outros contexts? (resolver via events/ports)
8. Quais são as REGRAS DE NEGÓCIO? (invariantes do aggregate)

MOSTRE:
- Diagrama das classes (entidades, VOs, events)
- Fluxo de comandos (command → aggregate → event → handler)
- Contratos de repositório (interfaces no domínio)

NÃO escreva código. Aguarde aprovação do design DDD.
```

### P4 — Testes DDD (Novo)

```
Escreva testes para: [ENTIDADE/SERVICE]

ESTRUTURA (Given-When-Then / AAA):

def test_camera_go_offline_emits_event():
    # Given (Arrange)
    camera = CameraFactory.online()

    # When (Act)
    camera.go_offline()

    # Then (Assert)
    events = camera.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], CameraWentOffline)
    assert events[0].camera_id == camera.id

COBRIR:
1. Happy path — comportamento esperado
2. Edge cases — limites, valores nulos
3. Business rules — violações levantam exceção
4. State transitions — transições válidas e inválidas
5. Value objects — validação e igualdade
6. Domain events — eventos corretamente emitidos

Escreva os testes. Nenhum código de produção ainda.
```

### PE-GOV Adicionais (Integrados ao Kit Original)

Os prompts PE-GOV-1 a PE-GOV-7 e PE-GOV-ERR-1 a PE-GOV-ERR-3 do seu documento original **permanecem válidos**. Apenas adicione ao mapa de prompts:

```
| Situação | Prompts Recomendados |
|----------|---------------------|
| Refatorar para DDD | P0 → P1 → P2(DDD) → P4(DDD) → P5 → P6 → P7 → P8 |
| Sprint A1 (Shared Kernel) | P0 → P2(DDD) → testes kernel → implementação |
| Sprint A2 (Extrair Core) | P0 → P1 → mover arquivos → atualizar imports → testar |
| Sprint A3 (Entities Ricas) | P0 → P2(DDD) → P4(DDD) → comportamento + testes |
| Sprint A4 (Event Bus) | P0 → P2(DDD) → testes pub/sub → implementação |
| Sprint A5 (Deps) | P0 → P1 → identificar deps → inverter → testar |
```

---

## 📚 ADRs DDD

### ADR-009: Domain Events para Comunicação entre Contexts

**Contexto:** Bounded contexts precisam se comunicar sem acoplamento direto.

**Decisão:** Domain Events publicados via Redis pub/sub.

**Consequências:**
- ✅ Desacoplamento total
- ✅ Fácil adicionar consumers
- ⚠️ Eventual consistency
- ⚠️ Necessário idempotência

---

### ADR-010: Value Objects para Tipos de Domínio

**Contexto:** Strings primitivas causam confusão (camera_id vs tenant_id).

**Decisão:** Value Objects fortes (`CameraId`, `TenantId`, `Coordinates`).

**Consequências:**
- ✅ Type safety (mypy detecta erros)
- ✅ Validação no construtor
- ✅ Imutabilidade garantida
- ⚠️ Mais boilerplate
- ⚠️ Curva de aprendizado

---

### ADR-011: Entidades Ricas (não anêmicas)

**Contexto:** Services anêmicos viram "transaction scripts" (não DDD).

**Decisão:** Entidades têm comportamento. Services orquestram, não implementam.

**Exemplo:**
```python
# ❌ Anêmico
camera.is_active = True
db.save(camera)

# ✅ Rico
camera.activate()  # valida, muda estado, emite evento
db.commit()        # persiste
publish_events(camera.pull_events())  # publica eventos
```

---

### ADR-012: Repository Interfaces no Domínio

**Contexto:** Onde colocar interfaces de repositório?

**Decisão:** Interfaces no domínio, implementação em infra.

```python
# domínio/cameras/repository.py (interface)
class CameraRepository(Protocol):
    async def get_by_id(self, id: CameraId) -> Camera | None: ...
    async def save(self, camera: Camera) -> None: ...

# infra/cameras/repository.py (implementação)
class SQLAlchemyCameraRepository:
    async def get_by_id(self, id: CameraId) -> Camera | None: ...
```

---

### ADR-013: Clock Abstraction para Testabilidade

**Contexto:** `datetime.utcnow()` em testes é não-determinístico.

**Decisão:** Abstração `Clock` injetável.

```python
# Produção
clock = RealClock()

# Testes
clock = FakeClock(datetime(2026, 4, 12, 10, 0, 0))
```

---

## 🚀 PRÓXIMOS PASSOS — ORDEM DE EXECUÇÃO

### Opção A: DDD Primeiro (Recomendado)

```
Semana 1: Sprint A1 (Shared Kernel) + A2 (Extrair Core)
Semana 2: Sprint A3 (Entities Ricas) + A4 (Event Bus)
Semana 3: Sprint A5 (Resolver Dependencies) + Sprint 0 (bugs)
Semana 4+: Sprints 1-7 originais (agora mais fáceis)
Semana 8+: Sprints 8-15 (governo)
```

### Opção B: Intercalado

```
Semana 1: Sprint A1 (Shared Kernel) → fundação
Semana 2: Sprint 0 (bugs) → valor imediato
Semana 3: Sprint A2-A3 → DDD
Semana 4: Sprint 1 → valor
Semana 5: Sprint A4-A5 → DDD
Semana 6-7: Sprints 2-3 → valor
Semana 8+: Sprints 8-15 (governo, facilitados pelo DDD)
```

### Minha Recomendação

**Opção A** é mais limpa. Você investe 3 semanas em fundação DDD e depois **todos os sprints seguintes são 40-60% mais rápidos**.

Quer que eu comece executando o **Sprint A1 (Shared Kernel)** agora?

---

> **DDD não é burocracia — é controle de complexidade.**
> Cada Value Object, cada Domain Event, cada interface de repositório
> é uma decisão explícita sobre ONDE a complexidade vive.
>
> *"Sem DDD, a complexidade se espalha. Com DDD, a complexidade se organiza."*
