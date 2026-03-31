# ADR 002 — Arquitetura Hexagonal com Bounded Contexts

**Data:** 2026-03-30
**Status:** Aceito

## Contexto
Precisamos de uma arquitetura que:
- Seja testável (services isolados de frameworks)
- Permita trocar banco/cache sem impacto no negócio
- Comunique intenção claramente para novos devs
- Suporte crescimento sem acoplamento excessivo

## Decisão
Adotar **arquitetura hexagonal (Ports & Adapters)** com separação em
**bounded contexts** por domínio.

Estrutura por bounded context:
```
{context}/
├── domain.py      # Entidades puras (dataclasses Python)
├── ports.py       # Interfaces (Protocol/ABC) — sem implementação
├── service.py     # Casos de uso (orquestra domain + ports)
├── models.py      # SQLAlchemy ORM (adapter de persistência)
├── repository.py  # Implementação dos ports para SQLAlchemy
├── schemas.py     # Pydantic v2 (adapter HTTP)
└── router.py      # FastAPI routes (adapter HTTP)
```

## Consequências

### Positivo
- Services são testáveis com repositórios mockados (sem banco)
- Domain não tem dependências externas — lógica pura
- Cada contexto é coeso e independente
- Fácil de adicionar novo contexto (ex: billing) sem tocar outros

### Negativo
- Mais arquivos por feature
- Requer disciplina para não vazar lógica de negócio para adapters
- Pequeno overhead de abstração para CRUDs simples

## Alternativas consideradas
- MVC simples (models + views): acoplamento alto, difícil testar services
- CQRS completo: overhead desnecessário para MVP
