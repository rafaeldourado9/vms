# ADR 003 — ARQ em vez de Celery

**Data:** 2026-03-30
**Status:** Aceito

## Contexto
Precisamos de background tasks para:
- Indexar segmentos de gravação
- Disparar webhooks de notificação
- Cleanup de segments expirados

## Decisão
Usar **ARQ** (Async Redis Queue) em vez de Celery.

## Consequências

### Positivo
- Async-native: tasks são coroutines, sem `asyncio.run()` wrapper
- Usa Redis já existente (sem RabbitMQ dedicado para tasks)
- API simples: `await arq.enqueue_job("task_name", arg1, arg2)`
- Sem problemas de pickling (Celery com objetos complexos)
- Dashboard simples para dev

### Negativo
- Menos maduro que Celery
- Sem `beat` nativo — usar `asyncio` scheduled tasks ou APScheduler
- Sem canvas/chains complexos (não precisamos para MVP)

## Alternativas consideradas
- Celery + Redis: síncrono, requer `asyncio.run()` ou `gevent`
- Celery + RabbitMQ: overhead de configuração, mesmo problema async
- Dramatiq: bom mas menos usado no ecossistema FastAPI
