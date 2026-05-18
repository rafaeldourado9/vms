# Roadmap de Melhorias Arquiteturais

> Plano de sprints derivado de [`tradeoffs.md`](./tradeoffs.md). Cada sprint
> vira uma branch + PR. Dependências explícitas; nada de paralelizar o que
> bloqueia o próximo.

Status atual: **Fase 1-7 concluídas** (CLAUDE.md §7). Esse roadmap é
**Fase 9+** — endurece a arquitetura pra escala (16 → 100 câmeras) e fecha
as dívidas técnicas catalogadas.

---

## Visão de Prioridade (4 sprints, ~6 semanas)

| Sprint | Foco | Por quê agora | Bloqueia |
|---|---|---|---|
| **α — Hardening de Produção** | Bugs latentes que sangram em prod | Sintomas já observados (manifestParsingError, câmera ghost online) | Tudo abaixo |
| **β — Analytics Headroom** | 16 câmeras CPU sem sufocar | Sem isso o cliente típico (i5, 8GB RAM) trava com 4-5 câmeras IA | Vendas |
| **γ — Confiabilidade & Escala** | Outbox, circuit breaker, particionamento | Quando cliente passa de 8 câmeras é onde quebra | Sprint δ |
| **δ — Compliance & Operação** | RLS, zero-downtime migrations, partitioning | Cliente enterprise / LGPD audit-ready | — |

Sprints ε+ (opcionais): GPU migration path, OpenVINO, UUID v7, WebRTC primário.

---

## Sprint α — Hardening de Produção (1-2 semanas)

**Objetivo:** zerar os bugs visíveis em produção depois das correções
imediatas (watchdog + day-HLS playlist) que acabaram de entrar.

### α.1 — Validação em produção do day-HLS playlist  *(2 dias)*
- Deploy em ambiente com gravações reais > 4h.
- Validar com hls.js (Chrome/Firefox/Edge) + Safari nativo.
- Métrica: stutter no boundary entre segmentos < 100ms; nenhum
  `manifestParsingError` em 1h de playback.
- **Decisão crítica:** se houver glitch perceptível, ativar
  `#EXT-X-DISCONTINUITY` por segmento (commit 2 linhas em
  `recordings/service.py:build_day_playlist`).

### α.2 — Cache Redis do day-HLS  *(1 dia)*
- Key: `day-hls:{tenant}:{cam}:{date}`. TTL 30s (gravações são append-only,
  só muda na borda do dia).
- Invalidar key quando segmento novo é indexado pra `date == today`.
- Carga estimada: cache hit > 95% em viewers concorrentes.

### α.3 — Watchdog: cobrir paths `live/{stream_key}`  *(1 dia)*
- Em `cameras/tasks.py:task_camera_watchdog`, juntar lookup por
  `stream_key` quando path do MediaMTX não bate com formato
  `tenant-{id}/cam-{id}`.
- Cobre RTMP push cameras.

### α.4 — Healthcheck do API container  *(0.5 dia)*
- `docker-compose.yml`: `test: curl -f http://localhost:8000/api/v1/health`
  (hoje ele pinga `/health` e marca unhealthy permanente).
- Bug pré-existente, está mascarando outras falhas reais.

### α.5 — E2E: gravação → playback chain  *(1.5 dia)*
- Test com pytest-bdd: provisiona câmera, publica RTMP por 3min, força
  segmento ready, requisita day-hls.m3u8, valida formato + hls.js parse.
- Roda no CI sem rede externa (RTMP fake via ffmpeg → MediaMTX local).

**Aceite:** nenhum bug aberto sobre streaming/gravação. Cobertura E2E
do pipeline > 80%. Healthcheck verde.

---

## Sprint β — Analytics Headroom (2 semanas)

**Objetivo:** colocar 16 câmeras com 3 plugins ativos rodando em CPU
i5/Ryzen 5 sem ultrapassar 70% de uso médio. Decisão fundamental: analytics
deixa de ser experimental e vira produto vendável.

### β.1 — Motion-skip pre-filter  *(2 dias)*
- Antes de invocar YOLO, comparar frame com baseline via `cv2.absdiff` +
  threshold (cheap, ~3ms).
- Se < 0.5% de pixels mudaram → drop frame, sem inferência.
- Configurável por câmera (`motion_threshold_pct`).
- **Impacto esperado:** câmera de portaria à noite → 90%+ de frames
  pulados → CPU médio cai 5-10×.

### β.2 — ROI / Zonas virtuais por câmera  *(4 dias)*
- DB model `IntrusionZone` (já no CLAUDE.md §4.3 mas não criado).
- UI: editor de polígono em canvas no `CameraDetailPage`.
- Plugin `intrusion_detection`: aplica máscara antes de passar pro modelo,
  reduz input pra bounding box do ROI.
- Latência cai de 80ms → 30-40ms quando ROI é < 30% do frame.

### β.3 — Quantização INT8 do ONNX  *(2 dias)*
- Worker analytics, no startup: se modelo `.onnx` não está quantizado,
  rodar `onnxruntime.quantization.quantize_dynamic`.
- Cache `model_int8.onnx` em volume.
- Validar mAP@50: tolerar drop até 2 pontos. Reverter se cair > 3.
- **Impacto:** −40% latência. YOLOv8n vai pra ~50ms.

### β.4 — Pool de workers + backpressure  *(3 dias)*
- ARQ queue `analytics` com `max_jobs=4` (workers concurrent).
- Drop de frames antigos: se queue Redis tem > 50 items, oldest-first.
- Métrica: `analytics_queue_depth` exposta em Prometheus / `/metrics`.

### β.5 — Dashboard de saúde de analytics  *(3 dias)*
- Página `/analytics/health` (admin only): por câmera, fps efetivo,
  latência p95, queue depth, error rate.
- Serve pra cliente justificar upgrade pra GPU vs aceitar 1 fps.

**Aceite:** benchmark documentado: 16 câmeras × 3 plugins × 2 fps em
i5-12400 com CPU médio < 70%. Plano de β.6+ se algum cliente pedir > 32
câmeras.

---

## Sprint γ — Confiabilidade & Escala (2 semanas)

**Objetivo:** sistema parar de perder dados em falha parcial. Aguenta
crescimento natural (16 → 50 câmeras) sem refactor emergencial.

### γ.1 — Outbox Pattern pra eventos críticos  *(4 dias)*
- Tabela `outbox_events(id, occurred_at, event_type, payload, published_at)`.
- INSERT no outbox dentro da MESMA transação do INSERT do evento de domínio.
- Worker ARQ `task_publish_outbox` (cron 1s): polla `published_at IS NULL`,
  publica em RabbitMQ/Redis, marca published.
- Aplicar a `alpr.detected`, `camera.online`, `camera.offline`, `recording.segment_ready`.
- Resolve: evento perdido se API cai entre INSERT no DB e PUBLISH no Redis
  (tradeoffs.md §2).

### γ.2 — Circuit breaker MediaMTXClient  *(2 dias)*
- `tenacity` decorator: 5 falhas em 30s → abre circuit por 60s, retorna
  cached state.
- Aplicar em `add_path`, `remove_path`, `list_paths`.
- Sem isso: cascade failure quando MediaMTX restarta — API derruba também.

### γ.3 — Priority queue do analytics  *(3 dias)*
- Redis ZADD com score = prioridade (1=critical, 10=normal).
- `Camera.priority` campo no DB (default 5).
- Worker analytics consome em ordem de score.
- Use case: câmera "perímetro" sempre processa antes de "garagem".

### γ.4 — Retry com exponential backoff em ARQ  *(1 dia)*
- Custom retry handler usa `ctx.score` pra calcular delay (exp backoff).
- Hoje retry é imediato → 5 tentativas em < 1s pra webhook caído.

### γ.5 — Particionamento `vms_events` por mês  *(4 dias)*
- Migration: converte tabela em PARTITIONED BY RANGE (occurred_at).
- Cron mensal: cria próxima partição, drop > 90 dias (LGPD).
- Performance: queries por período viram index-only scan numa partição.
- Critério pra rodar: tabela passa de 10M rows.

**Aceite:** outbox cobrindo 4 eventos críticos com chaos test (mata API
mid-transaction, evento ainda chega ao consumidor). Circuit breaker
testado com MediaMTX down 30s — nenhum 500 propagado.

---

## Sprint δ — Compliance & Operação (2 semanas)

**Objetivo:** cliente enterprise (LGPD audit, isolamento garantido)
consegue contratar. Operação não trava em migration de tabela grande.

### δ.1 — Row Level Security (RLS) multi-tenant  *(5 dias)*
- Habilitar RLS em todas as tabelas com `tenant_id`.
- Policy: `USING (tenant_id = current_setting('app.tenant_id')::uuid)`.
- Middleware FastAPI seta `SET LOCAL app.tenant_id = '{tenant_id}'` em
  cada request autenticada.
- Rodar suite de testes existente — RLS pega bug de query que esquece
  `WHERE tenant_id = ...`.
- **Risco:** quebra queries que esqueceram filtro hoje (vão começar a
  retornar 0 rows). Considerar feature flag `RLS_ENFORCE_MODE=warn|enforce`.

### δ.2 — Zero-downtime migrations com pg_repack  *(3 dias)*
- Documentar template de migration "non-blocking":
  `ADD COLUMN ... NULL` (não locka), backfill em batch, `ALTER ... NOT NULL`.
- Pra rebuild de index: `CREATE INDEX CONCURRENTLY` sempre.
- Pra rebuild de tabela: `pg_repack` em produção.

### δ.3 — UUID v7 em tabelas de alto volume  *(3 dias)*
- Migrar default de `id` em `vms_events`, `recording_segments`,
  `analytics_events` pra UUID v7 (time-ordered).
- Reduz fragmentação B-tree em > 50M rows; INSERT 30% mais rápido.
- Não migra IDs existentes — só novos. Backfill opcional.

### δ.4 — Backup verificável  *(2 dias)*
- Cron diário: `pg_dump` → S3-compatible (Backblaze B2 / Wasabi
  como default barato).
- Cron semanal: restore em `postgres_test` container, roda smoke test,
  alerta se falhar.
- Hoje tem `infra/scripts/backup_db.sh` mas sem verificação de restore.

### δ.5 — LGPD: rotina de purge automática  *(2 dias)*
- Cron mensal: identifica `recording_segments` > retention_days, +
  embeddings de `FaceProfile` sem evento nos últimos N dias.
- Gera relatório PDF assinado (HMAC) com IDs purgados.
- Atende DPO em audit.

**Aceite:** RLS habilitada em modo `enforce` em produção sem regressão.
Restore semanal verde. UUID v7 em produção em pelo menos `vms_events`.

---

## Sprints ε+ (Opcionais — Avaliar Demanda)

Não fazer sem trigger claro. Cada um tem ~1 sprint de tamanho.

| Tema | Trigger pra começar |
|---|---|
| **ε.1 OpenVINO opt-in** | Cliente Intel-only com 24+ câmeras; benchmark mostra >25% ganho |
| **ε.2 GPU migration path (T4/L4)** | Cliente pede `weapon_detection` ou `face_recognition` em produção |
| **ε.3 WebRTC primário** | Cliente exige latência sub-segundo (live monitoring crítico) |
| **ε.4 Schema-per-tenant** | Cliente enterprise exige isolamento de banco por compliance |
| **ε.5 Federated multi-region** | Cliente operando > 1 datacenter (LATAM + EU) |
| **ε.6 Edge inference (RPi/Jetson)** | Cliente quer inferência na borda com sync eventual |

---

## Métricas de Sucesso (revisar a cada sprint)

| Métrica | Hoje | Após α | Após β | Após γ | Após δ |
|---|---|---|---|---|---|
| Câmeras 1080p simultâneas (live) | ~8 | 16 | 32 | 50 | 100 |
| Câmeras com IA real-time (CPU) | ~4 | 6 | **16** | 24 | 32 |
| Latência day-HLS playlist (p95) | n/a | < 200ms | < 100ms | < 50ms | < 50ms |
| Eventos perdidos / 1M | desconhecido | medido | < 100 | **0** | 0 |
| Latência inferência YOLOv8n | 80ms | 80ms | **45ms** | 45ms | 45ms |
| Tempo de migration em produção | minutos+lock | idem | idem | idem | **0 downtime** |

---

## Convenções

- **1 sprint = 1 branch + 1 PR**. Não misturar α.1 com α.4 em PR único.
- Cada sprint termina com:
  1. Testes unitários + integração novos
  2. Atualização de `tradeoffs.md` (nova decisão / dívida resolvida)
  3. Atualização de `CLAUDE.md` §6 (estado do codebase)
  4. Commit atômico com escopo do sprint
- Métricas: instrumentar antes (baseline), commitar dashboard, validar
  delta no fim do sprint.
- Sem feature creep: se aparecer mais bug durante α.1, abre issue,
  não adiciona ao mesmo PR.
