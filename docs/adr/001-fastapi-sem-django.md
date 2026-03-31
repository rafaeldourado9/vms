# ADR 001 — FastAPI sem Django

**Data:** 2026-03-30
**Status:** Aceito

## Contexto
O projeto legado usa Django + DRF para a API principal. Django traz ORM próprio,
admin, signals, middleware stack pesado. Para um VMS async-first com até 200
câmeras simultâneas, precisamos de performance e simplicidade.

## Decisão
Usar **FastAPI + SQLAlchemy 2.0 async** em vez de Django.

## Consequências

### Positivo
- I/O completamente async (sem thread pool overhead)
- SQLAlchemy 2.0 async é mais explícito que Django ORM
- OpenAPI / Swagger gerado automaticamente
- Stack menor: sem Django admin, sem signals, sem ORM próprio
- Alembic para migrations (mais poderoso que Django migrations)
- Testabilidade: `httpx.AsyncClient` com `app` direto

### Negativo
- Sem admin pronto (implementar um básico se necessário)
- Migrations manuais com Alembic (mais verboso que `makemigrations`)
- Menos "batteries included" — escrever mais boilerplate

## Alternativas consideradas
- Django + async views: ORM síncrono por padrão, overhead de signals
- FastAPI + Tortoise ORM: menos maduro que SQLAlchemy
