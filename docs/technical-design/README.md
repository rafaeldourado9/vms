# Technical Design — VMS

Documentação técnica estruturada do VMS white-label. Leia na ordem abaixo para construir o entendimento de dentro para fora.

---

## Documentos

| Arquivo | O que contém |
|---------|-------------|
| [DER.md](DER.md) | Diagrama Entidade-Relacionamento completo (Mermaid), cardinalidades, bounded contexts × tabelas |
| [database-modeling.md](database-modeling.md) | Estratégias de modelagem: multi-tenancy, UUID, JSONB, particionamento, índices, Alembic |
| [component-architecture.md](component-architecture.md) | Organização interna por camadas (presentation → application → domain → infrastructure), responsabilidades de cada módulo |
| [system-design.md](system-design.md) | Topologia de serviços, fluxos de dados críticos (ALPR, analytics, gravação, auth), infraestrutura Docker |
| [patterns.md](patterns.md) | Catálogo de padrões usados: DDD, Ports & Adapters, Repository, Service Layer, Plugin, EDA, CQRS parcial, Deduplication, etc. |
| [tradeoffs.md](tradeoffs.md) | Decisões técnicas com prós/contras documentados e dívida técnica conhecida |

---

## Resumo da Stack

```
FastAPI (async)   PostgreSQL 16   Redis 7      RabbitMQ 3
SQLAlchemy 2.0    ARQ (tasks)     MediaMTX     YOLOv8 (analytics)
Alembic           Fernet (crypto) JWT + API Key  Docker Compose
```

## Bounded Contexts

```
IAM · Cameras & Agents · Events · Recordings · Streaming
Analytics · Notifications · Audit · Billing · Reports · LGPD
```

## Fluxos Principais

- **Fluxo A** — ALPR event-based: câmera inteligente → webhook → normalizer → dedup Redis → persist → SSE → notification
- **Fluxo B** — Analytics server-side: câmera bullet → RTSP pull → YOLOv8 plugin → POST /analytics/events
- **Gravação** — MediaMTX segment_ready webhook → ARQ task → SHA-256 → DB index → custody chain
