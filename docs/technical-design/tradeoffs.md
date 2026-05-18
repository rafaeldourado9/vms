# Tradeoffs Arquiteturais

> Cada decisão técnica tem um custo. Este documento registra o que foi escolhido, o que foi descartado, e o que ficou como dívida técnica conhecida.
>
> Plano de execução das melhorias derivadas dessas dívidas: [`roadmap.md`](./roadmap.md).

---

## 1. Multi-Tenancy: Shared Schema vs. Database-per-Tenant

### Decisão: Shared database, shared schema (tenant_id por coluna)

| Vantagem | Desvantagem |
|---------|------------|
| Uma migration aplica para todos os tenants | Qualquer bug de query pode vazar dados cross-tenant |
| Pool de conexões compartilhado (eficiente) | Sem isolamento a nível de banco (sem RLS ainda) |
| Simples de operar (1 banco) | Tenant "ruidoso" pode impactar queries de outros |
| Escalável para centenas de tenants | Não atende clientes que exigem "banco próprio" por compliance |

**O que ficou de fora:**
- Row Level Security (RLS) do PostgreSQL — eliminaria vazamento mesmo com bug de query
- Schema-per-tenant — inviável para migrations e pool
- Database-per-tenant — inviável para operação em escala

**Dívida técnica:** Implementar RLS quando um tenant enterprise exigir isolamento garantido a nível de banco.

---

## 2. Event Bus: Redis Pub/Sub vs. RabbitMQ

### Decisão: Redis pub/sub para eventos de domínio (fire-and-forget)

| Redis Pub/Sub | RabbitMQ |
|--------------|---------|
| Sem mensagem persistida (se consumidor cair, perde) | Mensagens duráveis em disco |
| Latência sub-milissegundo | Latência de rede (~1ms) |
| Já está no stack (ARQ usa Redis) | Serviço adicional para operar |
| Simples (PUBLISH/SUBSCRIBE) | Exchange, Queue, Binding, DLQ built-in |
| Sem replay de mensagens antigas | Replay possível via message history |

**Contexto da decisão:**
- SSE ao frontend é transiente por natureza — se browser desconectar, evento perdeu relevância
- `alpr.detected` para notificação entra imediatamente na fila ARQ (Redis) — durável
- RabbitMQ está no stack mas é usado como exchange para routing futuro, não como bus primário

**Risco real:** Se o processo API cair entre o INSERT no banco e o PUBLISH no Redis, a notificação não é enviada. O evento está no banco mas a regra de notificação não dispara.

**Mitigação futura:** Outbox Pattern — persistir evento pendente na mesma transaction, worker publica e deleta.

---

## 3. Task Queue: ARQ (asyncio) vs. Celery

### Decisão: ARQ

| ARQ | Celery |
|-----|--------|
| Nativo asyncio — sem bloqueio de thread | Sync por padrão (Celery 5 tem suporte async parcial) |
| Simples: 1 arquivo `worker.py` | Configuração mais extensa |
| Redis como broker (já no stack) | Redis ou RabbitMQ como broker |
| Menor footprint de memória | Mais maduro, mais features (canvas, chord, etc.) |
| Menos documentação/comunidade | Ecossistema enorme, plugins abundantes |
| Sem suporte a retry decorators nativos | `@task(max_retries=3)` built-in |

**Limitação atual:** Retry em ARQ depende de re-raise de exception — não há `exponential backoff` automático. Implementado manualmente em `task_dispatch_notification`.

---

## 4. Streaming: MediaMTX vs. Servidor Próprio

### Decisão: MediaMTX como componente externo

| MediaMTX | Implementação própria |
|---------|----------------------|
| RTSP, RTMP, HLS, WebRTC out-of-the-box | Meses de desenvolvimento |
| Gravação automática em segmentos configuráveis | Controle total |
| API REST para gerenciar paths dinamicamente | — |
| Webhooks para eventos de stream | — |
| Suporte a transcoding (não usado — -c copy) | — |
| Black box — bugs são difíceis de debugar | Código próprio |
| Reinício limpa paths não persistidos | Persistência controlável |

**Quirks descobertos:**
- MediaMTX precisa de ~2s de warmup após startup
- API v3 usa `/v3/config/paths/add/{name}` (não confundir com `/v3/paths/`)
- Path `tenant-{id}/cam-{id}` é convenção nossa — MediaMTX não sabe de tenants

---

## 5. Analytics: analytics_service Separado vs. Celery Worker

### Decisão: Serviço Python separado (inversão de dependência)

| Serviço Separado | Celery Worker analytics |
|-----------------|------------------------|
| Zero acoplamento com Django/FastAPI core | Importa diretamente o código do core |
| Dockerfile separado com deps pesadas (ultralytics 500MB) | Deps pesadas entrariam no worker padrão |
| Adicionar plugin = criar arquivo, sem modificar VMS | Modificar VMS core para registrar task |
| Comunicação via HTTP (explícita, observável) | Comunicação via importação Python (implícita) |
| Falha no analytics não afeta o VMS core | Crash do analytics pode afetar worker padrão |
| Deploy independente (GPU vs CPU) | Deploy acoplado |
| Latência HTTP extra (~1ms) | Sem overhead de rede |

**Tradeoff aceito:** 1ms de latência HTTP por frame é irrelevante para análise em 1 FPS.

---

## 6. OCR de Placas: PaddleOCR vs. EasyOCR vs. Tesseract

### Decisão: PaddleOCR (plugin lpr)

| PaddleOCR | EasyOCR | Tesseract |
|-----------|---------|-----------|
| Mais leve em CPU | Maior consumo de memória | Muito lento para real-time |
| Latência menor (< 100ms por frame em CPU) | ~200ms por frame | 500ms+ por frame |
| Boa precisão para placas Mercosul | Boa precisão geral | Requer pré-processamento extenso |
| Documentação em chinês (parcialmente) | Documentação em inglês | Amplamente documentado |
| Mantido pelo Baidu | Mantido por comunidade | Mantido pelo Google |

---

## 7. Autenticação de Agents: API Key vs. JWT vs. mTLS

### Decisão: API Key custom (hash no banco)

| API Key | JWT | mTLS |
|---------|-----|------|
| Simples de implementar e testar | Stateless, sem lookup no banco | Mais seguro (certificado por device) |
| Revogação imediata (marcar `is_active=False`) | Revogação complexa (blacklist) | Complexo para provisionar certificados |
| Prefixo visível facilita debug | Sem prefixo — difícil de identificar | — |
| Hash no banco — seguro se banco comprometido | Seguro sem banco | — |
| Não exige PKI | Não exige PKI | Exige PKI |

**Header usado:** `Authorization: Agent <api_key>` — namespace separado de JWT para evitar ambiguidade.

---

## 8. ALPR Deduplication: Redis SET NX vs. Bloom Filter vs. DB UNIQUE

### Decisão: Redis SET com NX e TTL

| Redis SET NX + TTL | Bloom Filter | DB UNIQUE constraint |
|-------------------|-------------|---------------------|
| Expiração automática (sem cleanup) | Expiração requer reinicialização | Sem expiração (cresce infinitamente) |
| Falsos negativos: zero | Falsos positivos: < 1% (trade aceito) | Sem falsos positivos |
| Stateful — requer Redis disponível | Pode ser in-memory | Requer round-trip ao banco |
| TTL configurável por tenant (futuro) | TTL complexo | — |
| Atômico com SET NX | Operações não atômicas | Requer `ON CONFLICT` |

**Dois níveis implementados:**
1. `alpr:dedup:exact:{cam}:{plate}:{ts_bucket}` — previne replay exato (TTL 24h)
2. `alpr:dedup:{cam}:{plate}` — sliding window (TTL 60s configurável)

---

## 9. Custody Chain: JSONB Array vs. Tabela Separada

### Decisão: JSONB array em `recording_segments.custody_chain`

| JSONB no mesmo registro | Tabela separada |
|------------------------|----------------|
| Read simples: 1 query | Read: JOIN ou query separada |
| Append via `||` operator | INSERT simples |
| Não requer JOIN | Paginação de entries |
| Limite prático: ~100 entries/segmento | Crescimento ilimitado |
| Ordenação implícita por append order | Requer `ORDER BY created_at` |

**Quando migrar:** Se algum segmento acumular > 50 entries (improvável — segmentos têm vida curta pós-retenção).

---

## 10. Armazenamento de Vídeo: Volume Local vs. Object Storage (S3)

### Decisão atual: Volume local Docker (`/recordings`)

| Volume Local | Object Storage (S3/MinIO) |
|-------------|--------------------------|
| Latência zero (local I/O) | Latência de rede (ms a segundos) |
| Custo zero (incluso na infra) | Custo por GB/mês + transferência |
| Sem escalabilidade além do disco | Escalabilidade infinita |
| Falha do disco = perda de dados | Redundância built-in (S3 11 noves) |
| Self-hosted = dado na infra do cliente | Dado no cloud (pode ser problema de compliance) |
| ffmpeg acessa direto sem download | ffmpeg precisa de download ou streaming adapter |

**Posicionamento:** Self-hosted é um diferencial competitivo. Dados de vídeo ficam na infra do integrador — compliance e LGPD por design.

**Caminho futuro:** Suporte a MinIO (S3-compatible) para tenants que preferem object storage mantendo self-hosted.

---

## 11. Polling vs. WebSocket para Agent Config

### Decisão: Polling HTTP (30s) com WebSocket opcional

| Polling HTTP | WebSocket |
|-------------|-----------|
| NAT traversal trivial (outbound HTTP) | Exige conexão persistente (firewall pode bloquear) |
| Stateless no servidor | Stateful no servidor (websocket sessions) |
| 30s de lag na propagação de config | Config atualiza instantaneamente |
| Sem re-conexão para implementar | Reconexão em caso de falha (exponential backoff) |
| Load balancer trivial | Sticky sessions necessário |

**Decisão híbrida:** Polling como primary, WebSocket como optimization (push imediato quando disponível). Agent funciona sem WebSocket.

---

## 12. Face Recognition: Opt-in por Tenant vs. Feature Flag Global

### Decisão: Campo `facial_recognition_enabled` por Tenant + consent registrado

| Por tenant (current) | Feature flag global |
|---------------------|---------------------|
| Granularidade: habilitar só para quem consentiu | Todos habilitados ou nenhum |
| Auditável: `facial_recognition_consent_at` | Sem rastreabilidade de consent |
| Exige operação deliberada por admin | Pode ser habilitado por acidente |
| Atende LGPD (base legal por tenant) | Não atende LGPD |

**Regra:** Nunca `default=True`. Nunca habilitar sem `facial_recognition_consent_at` preenchido no banco.

---

## 13. Relatório PDF: WeasyPrint vs. ReportLab vs. Puppeteer

### Decisão: WeasyPrint (HTML → PDF via template Jinja2)

| WeasyPrint | ReportLab | Puppeteer (Chrome headless) |
|-----------|-----------|---------------------------|
| HTML/CSS templates — front-end conhece | API Python low-level | HTML completo, melhor fidelidade |
| Sem dependência de browser | Sem dependência externa | Headless Chrome (~150MB) |
| CSS limitations (vs. Chrome) | Curva de aprendizado alta | Mais pesado para deploy |
| Bom para relatórios textuais | Bom para layouts complexos | Melhor para dashboards visuais |

---

## 14. Gravações: Estratégia de Playback (HLS-VOD)

### Decisão: Playlist `.m3u8` montado pela API a partir dos fMP4 já em disco

A API serve `GET /api/v1/cameras/{id}/recordings/day-hls.m3u8?date=&token=` retornando texto `application/vnd.apple.mpegurl`. Cada `#EXTINF` aponta direto pros segmentos `/recordings/.../HH-MM-SS.mp4` que o nginx serve com `Accept-Ranges` e `Cache-Control: private, no-cache`. Discontinuidades temporais > 1.5s viram `#EXT-X-DISCONTINUITY`.

| Abordagem | Por que sim / por que não |
|---|---|
| **Playlist na API** (atual) | ✅ Sem reencoding, sem path dinâmico no MediaMTX, controla auth via JWT no `?token=`, gera gaps corretos. ⚠️ Cada fMP4 é self-contained (ftyp+moov próprios) — hls.js precisa do `progressive: true` pra demuxar; transição entre segmentos pode ter glitch de < 100ms. |
| **MediaMTX `/playback/get`** (rejeitada) | ❌ Retorna fMP4 binário concatenado, não HLS. Causou `manifestParsingError` na sprint anterior. |
| **MediaMTX HLS server com `source: file://`** (rejeitada) | ❌ MediaMTX 1.17 não permite criar paths com source de arquivo via API dinâmica. Só estaticamente no `mediamtx.yml`. |
| **ffmpeg remux server-side** (rejeitada pra default) | ❌ ~10-20% CPU por câmera só pra remuxar. Inviável em 16+ câmeras simultâneas. ✅ Ainda viável sob demanda pra `clips` (recurso pontual). |
| **`<video src=mp4>` direto** (rejeitada) | ❌ Browser baixa o MP4 inteiro do dia (gigabytes). Sem chunks, sem seek inteligente. |

### Storage: fMP4 segmentado vs MP4 único por sessão

| | Segmentos fMP4 60s (atual) | MP4 contínuo |
|---|---|---|
| Seek por hora | O(1) — pula pro arquivo | O(N) — lê moov gigante |
| Retenção parcial | Apaga dia inteiro = `rm dia/` | Não dá pra apagar 1 dia sem reencodar |
| Custódia (SHA-256) | Hash por segmento, granular | Hash do arquivo todo, ataque difícil mas verificação cara |
| Upload de clipe | Copia 1-2 arquivos | Reencoding ou ffmpeg trim |
| Falha de stream | Perde apenas 1 segmento | Perde a sessão inteira (moov não foi escrito) |

**Decisão:** fMP4 60s. `recordSegmentDuration: 60s` no `mediamtx.yml`. Custo: ~1440 arquivos/câmera/dia, mas filesystem moderno (xfs/ext4) lida com isso sem dor.

### Real-time live HLS

| Setting (`mediamtx.yml`) | Valor | Tradeoff |
|---|---|---|
| `hlsVariant: fmp4` | low-latency HLS | ~3s glass-to-glass vs 10s do TS |
| `hlsSegmentCount: 3` | 3 segmentos no manifesto | Buffer baixo, exposição a stalls; aumentar pra 5 se rede instável |
| `hlsSegmentDuration: 2s` | 2s por segmento | Latência menor, mais HTTP requests |
| `hlsPartDuration: 200ms` | LL-HLS parts | Sub-segundo de latência se browser suportar; chrome/safari ok |

**Não fazemos:** WebRTC como primário. Tradeoff `hls vs webrtc` na seção 8 — WebRTC tem latência sub-segundo mas exige TURN em NAT corporativo.

### Retenção e custo

- **Default:** `retention_days: 30` por câmera (campo no DB).
- **Cleanup:** ARQ cron `task_cleanup_old_segments` 03:00 UTC diário, deleta arquivos + DB rows.
- **Storage estimado** (1080p H.264 @ 4Mbps): ~43GB/câmera/dia. 16 câmeras × 30 dias ≈ **20TB**. Cliente self-hosted bancando seu próprio disco, ou managed cobrando R$50/cam/mês (cobre ~50GB/dia em S3 Glacier-like).

### Dívidas e limitações

- **Demuxer reset no boundary entre fMP4** — se hls.js apresentar glitches em produção, alternativas: (a) `#EXT-X-DISCONTINUITY` entre TODO segmento (forçar reset), (b) pré-processar concatenação a cada N minutos via ffmpeg em background, (c) servir `mp4` direto pra clips < 5min e HLS só pra dia inteiro.
- **Sem cache do playlist** — hoje toda request reabre query no DB. OK pra ≤ 100 viewers/min, virar problema em 1k+. Solução: cache Redis com TTL 30s key `day-hls:{tenant}:{cam}:{date}`.
- **Sem suporte a `live/{stream_key}` no watchdog de câmeras** — paths RTMP push usando stream key não são reconciliados pelo watchdog (seção 16). Webhook `runOnNotReady` ainda é a única fonte. Aceitável pelo MVP; resolver quando primeiro cliente RTMP push reportar bug.

---

## 15. AI Server-Side: 16 Câmeras Simultâneas em CPU

### Cenário

Cliente típico tem máquina dedicada com Intel i5/Ryzen 5 (4-8 cores físicos) **sem GPU**. Quer rodar `intrusion_detection`, `people_count`, `vehicle_count` em 16 câmeras simultaneamente — câmeras burras (sem IA no firmware) cuja inteligência vem do server-side.

**Métrica-alvo:** detecção em <2s do frame ao evento publicado, sem dropar frames críticos, sem dominar CPU a ponto de afetar streaming.

### Orçamento de CPU

YOLOv8n via ONNX Runtime CPU com input 640×640:
- Intel i5-12400 (6 cores): **~80ms/inferência**
- Ryzen 5 5600 (6 cores): **~70ms/inferência**

| Sampling rate | Inferências/s (16 cams) | CPU necessária | Viável? |
|---|---|---|---|
| 1 fps | 16/s × 80ms = 1280ms/s | ~1.5 cores 100% | ✅ Sobra 5+ cores pra resto |
| 2 fps | 32/s × 80ms = 2560ms/s | ~2.5 cores 100% | ✅ Confortável |
| 5 fps | 80/s × 80ms = 6400ms/s | ~6.5 cores 100% | ⚠️ Beira do limite, sem folga |
| 30 fps (real-time) | 480/s × 80ms = 38400ms/s | ~40 cores | ❌ Inviável sem GPU |

**Decisão:** Default **2 fps** por câmera. Configurável por tenant/plugin. Suficiente pra detectar intrusão (pessoa não atravessa zona em < 500ms).

### Modelo: YOLOv8n vs Alternativas

| Modelo | mAP@50 | Latência CPU | Tamanho | Decisão |
|---|---|---|---|---|
| YOLOv8n | 37.3 | 80ms | 6MB | ✅ Default |
| YOLOv8s | 44.9 | 220ms | 22MB | Reservado pra `weapon_detection` (precisão crítica) |
| YOLOv8m | 50.2 | 600ms | 50MB | ❌ Inviável em CPU pra real-time |
| MobileNet-SSD | 22.0 | 30ms | 4MB | ❌ Precisão muito baixa pra produção |
| YOLO-NAS-S | 47.5 | 180ms | 19MB | Considerar se mAP virar bloqueante |

### Runtime: ONNX Runtime CPU vs PyTorch Native

| | ONNX Runtime | PyTorch + ultralytics | OpenVINO |
|---|---|---|---|
| Latência YOLOv8n CPU | 80ms | 130ms | 55ms (Intel-only) |
| Memória residente | 200MB | 1.2GB (carrega torch) | 250MB |
| Setup | `onnxruntime` pip | `pip install ultralytics` (pesado) | exige toolkit Intel |
| Portabilidade | Roda em ARM, x86, qualquer OS | Idem mas pesado | Intel x86 só |

**Decisão:** ONNX Runtime CPU como default. Worker exporta o `.pt` da Ultralytics pra `.onnx` no startup; depois só usa onnxruntime. Quando cliente tem CPU Intel, opção de OpenVINO via env flag `ANALYTICS_RUNTIME=openvino` (~30% mais rápido).

### Concorrência: 1 Worker por Câmera vs Pool Compartilhado

| Estratégia | Pros | Contras |
|---|---|---|
| **1 processo por câmera** (rejeitada) | Isolamento total, falha de uma não afeta outras | 16 × 200MB = 3.2GB de RAM só pra carregar modelo. Inviável. |
| **Pool de N workers, fila de frames** (atual) | Modelo carregado 1×, frames distribuídos round-robin | Backpressure: se 1 frame trava, fila acumula |
| **Async com semáforo (single-process)** | Mínimo overhead, ideal pro asyncio do FastAPI | GIL: não paraleliza inferência. Sem ganho. |

**Decisão:** Pool de **2-4 workers** ARQ na queue `analytics`, cada um com modelo ONNX carregado em memória. Frames vêm da queue Redis. Backpressure controlado por queue length: se > 50 frames pendentes, drop mais antigo (frame velho não vale evento).

### Inversão de Dependência: `analytics_service` Independente

Já implementado (seção 7 do CLAUDE.md). Razão:

| Arquitetura monolito (rejeitada) | Microservice analytics (atual) |
|---|---|
| Plugin novo = mexer no core | Plugin novo = drop em `analytics_service/plugins/` |
| Worker analytics derruba VMS principal se OOM | Container separado, OOM kill localizado |
| Imagem do core fica gigante (~2GB com torch) | Core continua leve (~600MB), analytics_service tem todo o peso |
| Deploy acoplado | Deploy independente; analytics offline ≠ VMS offline |

**Tradeoff aceito:** comunicação via HTTP (overhead ~5ms/call). Aceitável pra 1-2 fps. Se virar gargalo (>30 fps por câmera), considerar UDS (Unix Domain Sockets) ou gRPC.

### Otimizações Antes de Sair do CPU

Em ordem de payback:

1. **ROI / Zonas virtuais** — só processar regiões definidas pelo operador no frontend (zona de intrusão). Reduz input do modelo pra 320×320 ou menos. Latência cai pra ~30ms.
2. **Frame skip on motion** — usar `cv2.absdiff` na prévia (cheap) pra pular frames sem movimento. Em câmera de portaria à noite, > 90% dos frames são vazios. CPU cai 10×.
3. **Multi-scale**: rodar modelo em 320×320 quando há motion baixo, 640×640 quando há detecção. ~50% redução média.
4. **Quantização INT8 do ONNX** — ONNX Runtime suporta INT8 com perda de ~2 mAP. Latência −40%. Útil pra YOLOv8n.
5. **OpenVINO** (Intel) ou **TensorRT** (Nvidia, mas estamos em CPU). Já mencionado.

Todas as 4 acumulam: combinadas, **2-3x mais headroom** sobre os números base.

### Quando virar GPU

Cliente cruza algum desses gatilhos:
- 32+ câmeras simultâneas
- `weapon_detection` ou `face_recognition` em produção (modelos maiores)
- Latência alvo < 500ms

Recomendar **NVIDIA T4 ou L4 server-side** (não consumer 4060). T4 = 70W, ~$2k, faz 200+ inferências YOLOv8n/s. Custo justifica >24 câmeras ou recursos avançados.

### Limitações conhecidas

- **Sem tracking entre frames** quando rodando em 1-2 fps. Para `vehicle_count` saber se carro X é o mesmo do frame anterior, precisa ByteTrack — já implementado no plugin `vehicle_dwell` (mantém estado por camera_id pra evitar colisão de track_ids).
- **Cold start** ao adicionar plugin: primeiro frame demora ~3s pra carregar modelo. Aceitável; mitiga com `warmup` no startup do worker.
- **Sem priorização entre câmeras** — todas têm peso igual na fila. Câmera "perímetro crítico" recebe o mesmo throughput de "garagem". Solução futura: 2 filas, queue priority via Redis ZADD com score.

---

## 16. Dívida Técnica Conhecida

| Item | Impacto | Prioridade | Solução sugerida |
|------|---------|-----------|-----------------|
| Sem Row Level Security (RLS) | Segurança: bug de query pode vazar dados cross-tenant | Alta | Implementar RLS por `tenant_id` no PostgreSQL |
| Sem Outbox Pattern | Confiabilidade: evento pode se perder entre INSERT e PUBLISH | Média | Tabela `outbox_events`, worker publica e deleta |
| UUID v4 em tabelas de alto volume | Performance: fragmentação B-tree em > 50M rows | Baixa | Migrar para UUID v7 em `analytics_events` |
| Sem exponential backoff em ARQ retries | Confiabilidade: retry imediato em falha de webhook | Baixa | Implementar backoff manual com `ctx.score` |
| `vms_events` não particionada | Performance em longo prazo (> 50M rows) | Baixa | Particionamento RANGE por `occurred_at` |
| Sem circuit breaker em MediaMTXClient | Resiliência: cascading failure se MediaMTX cair | Baixa | `tenacity` com circuit breaker |
| `face_recognition` stub | Feature: clientes enterprise podem exigir | Depende de dataset | Fine-tuning dataset + LGPD framework completo |
| Alembic sem zero-downtime migrations | Operações: locks em ALTER TABLE em tabelas grandes | Média | `pg_repack` + migrations não-bloqueantes |
| Day-HLS playlist sem cache | Performance: query DB a cada manifest fetch | Baixa | Cache Redis 30s key `day-hls:{tenant}:{cam}:{date}` |
| fMP4 self-contained pode glitch entre segmentos | UX: stutter < 100ms na transição | Baixa | Investigar em produção; fallback `#EXT-X-DISCONTINUITY` por segmento |
| Watchdog não cobre paths `live/{stream_key}` | RTMP push cameras dependem só do webhook | Baixa | Adicionar lookup por stream_key no watchdog |
| Sem priority queue analytics entre câmeras | Câmera crítica concorre igual com garagem | Média | 2 filas Redis ZADD por importância |
| Modelo ONNX não quantizado | Performance: latência 40% maior que poderia | Baixa | Quantização INT8 no startup do worker analytics |
