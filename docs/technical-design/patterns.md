# Padrões de Projeto e Arquitetura

> Catálogo dos padrões usados no VMS, onde cada um aparece, e por que foi escolhido.

---

## 1. Domain-Driven Design (DDD)

### Onde está
Todo o `api/src/vms/` é organizado por **bounded contexts**, não por camada técnica.

```
api/src/vms/
├── iam/             ← Bounded Context: Identidade
├── cameras/         ← Bounded Context: Câmeras & Agentes
├── events/          ← Bounded Context: Eventos ALPR
├── recordings/      ← Bounded Context: Gravações
├── analytics/       ← Bounded Context: Plugins de IA
├── notifications/   ← Bounded Context: Notificações
├── audit/           ← Bounded Context: Auditoria
├── billing/         ← Bounded Context: Licenciamento
├── reports/         ← Bounded Context: Relatórios
└── lgpd/            ← Bounded Context: Compliance
```

### Como é aplicado

| Conceito DDD | Implementação |
|-------------|---------------|
| **Entity** | Classes em `domain.py` com `id: UUID` como identidade |
| **Value Object** | `AlprDetection`, `StreamUrls`, `OnvifProbeResult` — sem identidade, imutáveis |
| **Aggregate Root** | `Tenant` (raiz do aggregate que controla `User`, `Camera`, `Agent`) |
| **Repository** | `{Contexto}Repository` com métodos de persistência — interface Protocol |
| **Domain Service** | `{Contexto}Service` com lógica de negócio que não pertence a uma entidade |
| **Domain Event** | Eventos publicados no bus: `alpr.detected`, `camera.online`, `clip.ready` |
| **Ubiquitous Language** | Nomes de campo e método espelham o domínio: `plate`, `tenant_id`, `custody_chain` |

---

## 2. Ports & Adapters (Hexagonal Architecture)

### Onde está
Cada repositório define um **Port** (Protocol/interface) e uma **Adapter** (SQLAlchemy).

```python
# Port (interface)
class CameraRepositoryPort(Protocol):
    async def get_by_id(self, camera_id: UUID, tenant_id: UUID) -> Camera | None: ...
    async def create(self, camera: Camera) -> Camera: ...

# Adapter (implementação SQLAlchemy)
class CameraRepository:
    def __init__(self, session: AsyncSession): ...
    async def get_by_id(self, camera_id: UUID, tenant_id: UUID) -> Camera | None:
        # SQLAlchemy query
```

### Por que
- Testes podem substituir o adapter por mock sem mudar o service
- Repositório pode trocar de PostgreSQL para outro banco sem tocar no service
- MediaMTXClient, OnvifClient e EventBus são adapters para sistemas externos

---

## 3. Repository Pattern

### Onde está
`api/src/vms/{context}/repository.py` — presente em todos os bounded contexts.

### Características
- Sempre recebe `tenant_id` como parâmetro — **multi-tenancy enforced no repositório**
- Nunca expõe `SQLAlchemy ORM objects` para fora — converte para domain objects
- Queries otimizadas com índices compostos (tenant_id, occurred_at), etc.
- Sem lógica de negócio — apenas I/O com o banco

```python
# Correto — repositório só faz I/O
async def list_by_camera(
    self, tenant_id: UUID, camera_id: UUID,
    started_after: datetime, limit: int
) -> list[RecordingSegment]:
    ...

# Errado — lógica de negócio no repositório
async def list_available_segments(self, ...):
    # NÃO: calcular disponibilidade, filtrar por retenção, etc.
```

---

## 4. Service Layer Pattern

### Onde está
`api/src/vms/{context}/service.py` — toda a lógica de negócio vive aqui.

### Características
- Recebe dependências por construtor (injeção de dependência)
- Orquestra repositórios, adapters externos e publicação de eventos
- Funções públicas < 20 linhas (regra do projeto)
- Type hints obrigatórios

```python
class EventService:
    def __init__(
        self,
        event_repo: EventRepositoryPort,
        event_bus: EventBus,
    ): ...

    async def ingest_alpr(
        self, detection: AlprDetection, redis: Redis
    ) -> VmsEvent | None:
        # 1. Filtra confiança
        # 2. Checa dedup no Redis
        # 3. Persiste via repositório
        # 4. Publica no event bus
        # 5. Retorna evento ou None se dedup
```

---

## 5. Normalizer / Strategy Pattern

### Onde está
`api/src/vms/events/normalizers/` — normalização de payloads ALPR.

### Como funciona
```python
# Registry de normalizers por fabricante
normalizers: dict[str, ALPRNormalizer] = {
    "hikvision": HikvisionNormalizer(),
    "intelbras": IntelbrasNormalizer(),
    "generic":   GenericNormalizer(),
}

def normalize(manufacturer: str, raw_payload: bytes | dict) -> AlprDetection:
    normalizer = normalizers.get(manufacturer, normalizers["generic"])
    return normalizer.normalize(raw_payload)
```

Cada normalizer implementa a mesma interface mas com lógica específica:
- **Hikvision**: parse XML ISAPI
- **Intelbras ITSCAM**: parse binário JPEG Dahua ITC (extrai placa do header binário)
- **Generic**: parse JSON normalizado

### Por que Strategy e não if/elif
- Adicionar novo fabricante = criar arquivo novo, sem alterar código existente (Open/Closed)
- Testável de forma isolada por fabricante

---

## 6. Plugin Pattern (Analytics)

### Onde está
`analytics_service/plugins/` — cada plugin é um módulo independente.

### Interface base
```python
class AnalyticsPlugin(ABC):
    name: str
    version: str

    @abstractmethod
    async def initialize(self, config: dict) -> None: ...

    @abstractmethod
    async def process_frame(
        self, frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig]
    ) -> list[AnalyticsResult]: ...

    async def process_shared_frame(
        self, detections: list[dict], ...
    ) -> list[AnalyticsResult]:
        # Default: chama process_frame (plugins podem sobrescrever para otimizar)
```

### Shared Inference Engine
Plugins que usam o mesmo modelo base (YOLOv8n) compartilham uma única inferência por frame:

```
Frame
  │
  ▼ (1x por frame)
SharedInferenceEngine.run() → detections[]
  │
  ├──▶ IntrusiónPlugin.process_shared_frame(detections)
  ├──▶ PeopleCountPlugin.process_shared_frame(detections)
  └──▶ VehicleCountPlugin.process_shared_frame(detections)
```

Isso evita rodar YOLOv8 3 vezes para o mesmo frame.

---

## 7. Event-Driven Architecture (EDA)

### Onde está
`api/src/vms/infrastructure/messaging/event_bus.py`

### Fluxo
```
Service publica evento
    │
    ▼
EventBus.publish("alpr.detected", payload, tenant_id)
    │
    ▼
Redis PUBLISH domain_events
    │
    ├──▶ SSE Bridge → canal sse:{tenant_id} → Frontend recebe em tempo real
    └──▶ Event Handlers registrados:
             handle_alpr_detected → enqueue ARQ task_dispatch_notification
             handle_camera_online → atualiza status no cache
             handle_clip_ready    → notifica via SSE
```

### Garantias
- **Fire-and-forget**: não bloqueia o request HTTP
- **Eventual consistency**: frontend e notificações recebem assincronamente
- **DLQ**: eventos com handler falhando vão para Dead Letter Queue (Redis sorted set)

---

## 8. CQRS (Command Query Responsibility Segregation) — Parcial

O projeto não implementa CQRS completo, mas aplica o princípio:

| Operação | Responsável | Descrição |
|----------|------------|-----------|
| **Commands** | `service.py` | Mutações com validação + side-effects (publicar evento, enqueue task) |
| **Queries** | `repository.py` | Reads otimizados com índices, sem side-effects |

Exemplo:
```python
# Command: tem side-effects (Redis dedup, event bus, ARQ)
await event_service.ingest_alpr(detection, redis)

# Query: só lê, sem side-effects
await event_repo.list_by_tenant(tenant_id, plate="ABC1234", limit=50)
```

---

## 9. Dependency Injection (DI)

### Onde está
FastAPI `Depends()` + construtor de services.

```python
# Dependency providers (shared)
async def get_camera_service(
    session: AsyncSession = Depends(get_db),
    event_bus: EventBus = Depends(get_event_bus),
) -> CameraService:
    return CameraService(
        camera_repo=CameraRepository(session),
        agent_repo=AgentRepository(session),
        mediamtx=MediaMTXClient(settings.mediamtx_api_url),
        event_bus=event_bus,
    )

# Router usa o provider
@router.post("/cameras")
async def create_camera(
    body: CreateCameraRequest,
    service: CameraService = Depends(get_camera_service),
    current_user: User = Depends(get_current_user),
):
    return await service.create_camera(...)
```

---

## 10. Outbox Pattern — Não implementado

> Nota arquitetural: o projeto usa Redis pubsub diretamente nos services. Se o processo cair após o INSERT mas antes do PUBLISH, o evento se perde. Para produção crítica, implementar Outbox Table (persistir evento no DB na mesma transaction, worker publica assincronamente).

---

## 11. Idempotency / Deduplication Pattern

### Onde está
`api/src/vms/events/service.py` + Redis

### Implementação
```python
# Dupla janela de deduplicação ALPR
async def _is_duplicate(plate, camera_id, redis) -> bool:
    # Janela exata: bucket de timestamp (previne replay exato)
    exact_key = f"alpr:dedup:exact:{camera_id}:{plate}:{ts_bucket}"
    if await redis.set(exact_key, 1, ex=86400, nx=True) is None:
        return True  # já existe

    # Janela deslizante: previne flood dentro do TTL
    window_key = f"alpr:dedup:{camera_id}:{plate}"
    if await redis.set(window_key, 1, ex=ALPR_DEDUP_TTL_SECONDS, nx=True) is None:
        return True

    return False
```

### Por que dois níveis
- Janela exata (24h): previne replay de eventos com exato mesmo timestamp (câmera com bug)
- Janela deslizante (60s): previne flood de mesma placa na mesma câmera em sequência rápida

---

## 12. Chain of Custody (Append-Only Log)

### Onde está
`api/src/vms/recordings/` — campo `custody_chain: JSONB` em `recording_segments`

### Implementação
```python
# Nunca sobrescrever — sempre append
async def append_custody_entry(self, segment_id, entry: dict) -> None:
    # entry = {action, timestamp, actor, user_email, optional: file_path, hmac}
    await self.repo.append_custody(segment_id, entry)
    # Traduz para: UPDATE SET custody_chain = custody_chain || '[{...}]'::jsonb
```

Ações registradas:
- `indexed` — ao criar o segmento (system)
- `integrity_verified` — ao verificar SHA-256 (user)
- `downloaded` — ao gerar URL de download (user)
- `exported_forensic` — ao exportar ZIP forense (user)

---

## 13. Facade Pattern

### Onde está
`MediaMTXClient` em `api/src/vms/cameras/mediamtx.py`

Simplifica a API HTTP do MediaMTX v3 expondo apenas o necessário:

```python
class MediaMTXClient:
    async def add_path(self, path: str, source: str) -> None: ...
    async def remove_path(self, path: str) -> None: ...
    async def get_path(self, path: str) -> dict: ...
    async def list_paths(self) -> list[dict]: ...
    async def add_hls_path(self, path: str, source_path: str) -> None: ...
```

Internamente usa `httpx` para chamar `/v3/config/paths/add/{name}`, etc.

---

## 14. Retry Pattern

### Onde está
`api/src/vms/notifications/tasks.py`

```python
async def task_dispatch_notification(ctx, rule_id, event_type, event_id, payload):
    attempt = ctx.get("job_try", 1)
    try:
        await service.dispatch_webhook(rule_id, payload)
        await log_repo.mark_success(log_id)
    except httpx.HTTPError:
        await log_repo.mark_failed(log_id, attempt=attempt)
        if attempt < 3:
            raise  # ARQ re-enqueues automatically on exception
```

ARQ re-enfileira automaticamente em caso de exceção, até `max_retries`.

---

## 15. Glob Pattern Matching

### Onde está
`api/src/vms/notifications/service.py`

```python
import fnmatch

def matches_pattern(pattern: str, event_type: str) -> bool:
    return fnmatch.fnmatch(event_type, pattern)

# Exemplo:
# pattern="alpr.*"    + event_type="alpr.detected"  → True
# pattern="recording.*" + event_type="alpr.detected" → False
# pattern="*"         + event_type="anything"        → True
```

Permite regras de notificação flexíveis sem necessidade de regex.

---

## Resumo dos Padrões

| Padrão | Onde é aplicado | Benefício principal |
|--------|----------------|---------------------|
| DDD (Bounded Contexts) | Estrutura de pastas inteira | Coesão, independência entre domínios |
| Ports & Adapters | Repositories + external clients | Testabilidade, substituição de implementação |
| Repository | `{ctx}/repository.py` | Abstração de persistência, multi-tenancy enforced |
| Service Layer | `{ctx}/service.py` | Lógica de negócio isolada, fora da view |
| Strategy (Normalizers) | `events/normalizers/` | Open/Closed para novos fabricantes |
| Plugin | `analytics_service/plugins/` | Adicionar analítico sem mudar core |
| Event-Driven | `infrastructure/messaging/` | Desacoplamento, real-time SSE |
| CQRS (parcial) | Service + Repository separados | Queries otimizadas sem side-effects |
| Dependency Injection | FastAPI `Depends()` | Testabilidade, composição flexível |
| Deduplication (Redis) | `events/service.py` | Idempotência de ALPR events |
| Chain of Custody | `recordings/` | Auditoria imutável de gravações |
| Facade | `MediaMTXClient` | API simplificada para sistema externo |
| Retry | `notifications/tasks.py` | Resiliência de webhooks saída |
| Glob Matching | `notifications/service.py` | Regras de roteamento flexíveis |
