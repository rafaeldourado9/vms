       VMS MVP Implementation Summary

       Based on my exploration of the codebase, here's the detailed implementation architecture:

       ---
       1. ANALYTICS SERVICE: Frame Capture, Inference Engine, Plugins

       Frame Capture (frame_source.py):
       - OpenCV-based RTSP reader with automatic reconnection
       - FPS control: skips frames via grab() to maintain target FPS (default 1 fps)
       - Reconnection backoff: 30-second interval between reconnect attempts
       - Throttled logging to prevent flood during stream failures

       Shared Inference Engine (shared_inference.py):
       - Single YOLO model loaded once, results distributed to multiple plugins
       - Plugin class mapping: PLUGIN_CLASSES dict defines which COCO classes each plugin uses
         - Intrusion, people_count, vehicle_count, LPR: person + vehicles (classes 0, 2-3, 5-7)
         - PPE, fire_smoke, biker_detection: own models (non-shared)
       - Detection filtering by polygon (ray-casting algorithm)
       - Returns normalized bbox [0.0-1.0], class_id, class_name, confidence

       Orchestrator (orchestrator.py):
       - Multi-camera concurrent processing: each camera has async task via asyncio.create_task()
       - GPU semaphore: asyncio.Semaphore(max(1, settings.analytics_workers)) controls concurrent inference
         - Default: 4 concurrent workers
       - Detection-based frame cache: skips empty frame sequences (>30 frames), processes detections and transitions
       - Flow:
         a. Discover cameras via VMS API GET /api/v1/plugins/cameras
         b. Get RTSP token per camera: GET /api/v1/plugins/stream-token
         c. Build MediaMTX direct RTSP URL: rtsp://mediamtx:8554/tenant-{id}/cam-{id}
         d. Load shared engines for plugins with common models
         e. Separate shared plugins (use YOLO) from standalone (own models)
         f. For each frame: run 1 shared inference → filter detections per plugin → plugin.process_shared_frame()
         g. Emit events: POST /api/v1/plugins/events

       Plugin Base Interface (plugin_base.py):
       - process_frame(): standalone inference (plugins with own models)
       - process_shared_frame(): receive pre-filtered detections from shared engine
       - Input: detections list [{class_id, class_name, confidence, bbox}, ...]
       - Output: AnalyticsResult with plugin name, event_type, payload, roi_id, confidence, timestamp

       Example Plugin: Intrusion Detection (intrusion/plugin.py):
       - Tracks intrusion state per ROI: started → ongoing (every 30s) → cleared (after 10 grace frames)
       - Filters detections by ROI polygon using centroid test
       - Emits events: analytics.intrusion.started/ongoing/cleared

       Detection Cache (detection_cache.py):
       - Smart caching: frame has detections → process; empty+prev-empty → skip; empty+prev-detections → process (transition)
       - Hit rate tracking; auto-reset after 30 empty frames
       - Prevents GPU waste on empty/static scenes while catching intrusion transitions

       Metrics Collector (metrics.py):
       - Tracks: inference time (ms), detection counts, event counts per plugin
       - Logs consolidation every 60 seconds with averages

       ---
       2. API SERVICE: FastAPI App, Database, Redis, Startup

       Main App (main.py):
       - Lifespan context: create_app() factory with async startup/shutdown
       - Startup sequence:
         a. Logging config via setup_logging()
         b. SQLAlchemy engine: create_async_engine() with pool_size=10, max_overflow=20, pre_ping=True
         c. Redis: aioredis.from_url() with UTF-8 encoding
         d. ARQ pool: create_pool(RedisSettings.from_dsn(redis_url))
         e. Event bus: connect_event_bus() → RabbitMQ pub/sub + event registry
         f. MediaMTX provisioning: _provision_mediamtx_paths() health checks (max 30s), then bulk add paths for all active cameras
       - Middleware stack: CORS, correlation ID, require onboarding
       - Rate limiting: slowapi with exception handler for 429 responses
       - Router registration: 10+ feature modules (cameras, events, recordings, streaming, plugins, analytics, audit, billing, lgpd, reports)

       Settings (settings.py):
       - Pydantic BaseSettings with env file support (.env)
       - Key configs:
         - database_url: PostgreSQL async URL (default: postgresql+asyncpg://vms:vmsdev@localhost:5432/vms)
         - redis_url: Redis connection (default: redis://localhost:6379/0)
         - rabbitmq_url: RabbitMQ (default: amqp://vms:vmsdev@localhost:5672/)
         - mediamtx_api_url: Control API (default: http://localhost:9997)
         - mediamtx_rtmp_url: RTMP endpoint
         - mediamtx_hls_url: HLS capture for thumbnails
         - analytics_api_key: Shared key for analytics service auth

       Database Connection (infrastructure/database/connection.py):
       - SQLAlchemy async engine factory with pool_size=10, max_overflow=20
       - async_sessionmaker for session creation
       - expire_on_commit=False to avoid detached state issues
       - Global _session_factory singleton initialized in lifespan

       Redis Integration (main.py lines 118-128):
       - aioredis.from_url() for cache/pub-sub
       - ARQ Redis pool: separate connection for job queue (via create_pool())
       - Both stored in app.state for dependency injection

       ---
       3. ARQ/CELERY WORKER CONFIG

       Worker Settings (worker.py):
       - Functions registered: 6 tasks
         - task_index_segment: Index recording segments
         - task_segment_to_hls: Convert segment to HLS format
         - task_cleanup_old_segments: Retention policy cleanup
         - task_dispatch_notification: Webhook dispatch for notification rules
         - task_generate_report: On-demand report generation
         - task_auto_monthly_report: Auto monthly reports
         - task_camera_watchdog: Reconcile camera online status with MediaMTX
       - Cron jobs:
         - task_cleanup_old_segments @ 03:00 UTC daily
         - task_auto_monthly_report @ 06:00 UTC on day 1
         - task_camera_watchdog @ :00 and :30 seconds (every 30s)
       - Concurrency: max_jobs=50, job_timeout=300s (5 min)
       - Startup/Shutdown:
         - Startup: Initialize DB engine, init session factory, connect Redis
         - Shutdown: Close Redis, close DB

       Task Pattern (notifications/tasks.py):
       - Args: ctx (worker context), task-specific params
       - Access DB via get_session_factory() → session creation
       - Access Redis via ctx["redis"]
       - Error handling: rollback on exception, record failure to DLQ via record_failure()

       Batch Processing Task (analytics/tasks.py):
       - GPU availability check before processing (requeue if busy)
       - File-based frame source for offline segment processing
       - Shared inference engine per segment
       - 10-minute job timeout for large segments

       ---
       4. MEDIAMTX CONFIG

       File: infra/mediamtx/mediamtx.yml

       Key Settings:
       # Global
       logLevel: info
       readTimeout: 120s
       writeTimeout: 120s
       writeQueueSize: 524288 (512 KiB)
       udpMaxPayloadSize: 1472

       # Auth
       authMethod: http
       authHTTPAddress: http://api:8000/streaming/publish-auth
       authHTTPExclude: [api, metrics, pprof, playback, read]  # Excluded actions

       # Control API
       api: yes
       apiAddress: :9997
       metricsAddress: :9998

       # Protocols
       rtsp: yes
       rtspAddress: :8554
       rtspTransports: [tcp, udp]

       rtmp: yes
       rtmpAddress: :1935

       hls: yes
       hlsAddress: :8888
       hlsVariant: fmp4  # Low-latency fragments
       hlsSegmentCount: 3
       hlsSegmentDuration: 2s
       hlsPartDuration: 200ms

       webrtc: yes
       webrtcAddress: :8889
       webrtcSTUNGatherTimeout: 5s
       webrtcICEServers2:
         - url: stun:stun.l.google.com:19302

       # Playback (VOD)
       playback: yes
       playbackAddress: :9996

       Recording:
       - record: yes
       - recordPath: /recordings/%path/%Y/%m/%d/%H-%M-%S-%f (microsecond uniqueness)
       - recordFormat: fmp4
       - recordPartDuration: 10s
       - recordSegmentDuration: 60s
       - recordDeleteAfter: 0s (VMS controls retention)

       Webhooks (runOn* hooks):
       - runOnReady: camera online → POST /api/v1/webhooks/mediamtx/on_ready
       - runOnNotReady: camera offline → POST /api/v1/webhooks/mediamtx/on_not_ready
       - runOnRecordSegmentComplete: segment ready (60s) → POST /api/v1/webhooks/mediamtx/segment_ready

       Path Defaults:
       - maxReaders: 100 (concurrent viewers per path)
       - source: publisher (paths created by API, not hardcoded)

       ---
       5. DOCKER-COMPOSE.YML SERVICE CONFIG

       Service Dependencies & Ports:

       postgres:
         - Port: 5432
         - Health: pg_isready
         - Volume: pgdata

       redis:
         - Port: 6379
         - Memory limit: 256 MB
         - Policy: allkeys-lru
         - Health: redis-cli ping

       rabbitmq:
         - Ports: 5672 (amqp), 15672 (management UI)
         - Health: rabbitmq-diagnostics ping

       mediamtx:
         - Ports: 8554 (RTSP), 1935 (RTMP), 8888 (HLS), 8889 (WebRTC), 9997 (API), 9998 (metrics)
         - Health: curl http://localhost:9997/v3/config/global/get
         - Volume: /recordings (shared)

       api:
         - Port: 8000
         - Env: DATABASE_URL, REDIS_URL, MEDIAMTX_API_URL
         - Depends on: postgres, redis, rabbitmq (healthy)
         - Health: curl http://localhost:8000/api/v1/health/
         - Volumes: /recordings, /tmp/vod (VOD), /tunnel (Cloudflare)

       worker (ARQ):
         - Command: python -m arq vms.worker.WorkerSettings
         - Env: same as API
         - Depends on: postgres, redis (healthy)
         - Health: Redis ping check

       analytics:
         - Port: 8001 (implicit)
         - Env: VMS_API_URL, VMS_API_KEY, MEDIAMTX_HOST, REDIS_URL (db/1), ANALYTICS_FPS, YOLO_*
         - Target: ${ANALYTICS_TARGET:-cpu} (cpu or gpu in Dockerfile)
         - Depends on: api, mediamtx, redis
         - Volume: /models (read-only)
         - Health: curl http://localhost:8001/health

       frontend:
         - Node/Next.js app (port implicit)

       edge-agent:
         - Optional (profile: agent)
         - Captures RTSP → sends RTMP to MediaMTX

       nginx:
         - Ports: 80, 443
         - Reverse proxy for api + frontend
         - Serves /recordings read-only

       cloudflared:
         - Optional (profile: dev)
         - Exposes via Cloudflare tunnel for webhooks

       backup-scheduler:
         - Runs pg_dump daily @ 3 AM
         - Retention: 7 days (configurable)

       Environment Variables:
       - DATABASE_URL: PostgreSQL async connection string
       - REDIS_URL: Redis for app cache + ARQ queue
       - RABBITMQ_URL: RabbitMQ for event bus
       - SECRET_KEY: JWT signing key
       - MEDIAMTX_API_URL: Control plane (internal)
       - MEDIAMTX_RTMP_URL: RTMP endpoint for pushers
       - RECORDINGS_PATH: Mounted volume for MediaMTX
       - VMS_API_KEY: Shared secret for analytics service auth
       - LOG_LEVEL: INFO (configurable)
       - ENVIRONMENT: production/staging/development
       - ANALYTICS_TARGET: cpu or gpu

       Volumes:
       - pgdata: PostgreSQL data
       - recordings: 24/7 MP4 segments from all cameras
       - vod_streams: HLS VOD fragments
       - backups: Daily pg_dump archives
       - tunnel_data: Cloudflare tunnel credentials
       - edge_agent_data: Edge agent configuration

       Networks:
       - Single bridge network: vms

       ---
       KEY ARCHITECTURAL PATTERNS

          self.key = f"sem:{key}"                                                                                                   
          self.limit_key = f"sem:{key}:count"                                                             
          self.limit = limit                                                                                    
          self.timeout = timeout                                                           
                                                                            
      async def __aenter__(self):                                                 
          for _ in range(30):  # tenta por 30s                                                          
              count = await self.redis.incr(self.limit_key)                           
              await self.redis.expire(self.limit_key, self.timeout)
              if count <= self.limit:
                  return self  
              await self.redis.decr(self.limit_key)     
              await asyncio.sleep(1)                   
          raise TimeoutError(f"Semáforo {self.key} esgotado após 30s")
                                                        
      async def __aexit__(self, *_):                           
          await self.redis.decr(self.limit_key)
                                                
  # Uso em task pesada:
  async def task_generate_report(ctx, report_id: int):                                                                                                                                                               
      redis: Redis = ctx["redis"]                                                                                                                                                                                    
      async with RedisSemaphore(redis, "reports", limit=2):   # máx 2 PDFs simultâneos
          await _do_generate_report(report_id)

  Ganho estimado: Previne spike de RAM quando múltiplos reports PDF são gerados simultaneamente (cada um pode usar 200–500 MB). −60% RAM em burst.
  Risco: Médio. Se o job crashar sem executar __aexit__, o contador fica incrementado. Mitigação: expire no limite garante auto-reset em timeout segundos.

  ---
  3.3 Batch de Notificações por Webhook URL

  # api/src/vms/notifications/tasks.py

  async def task_dispatch_notification_batch(ctx, notification_ids: list[int]):
      """
      Agrupa notificações pendentes para o mesmo webhook URL e envia em bulk.
      Reduz connections HTTP de N para 1 por destino.
      """
      session_factory = get_session_factory()
      async with session_factory() as session:
          notifications = await _fetch_notifications(session, notification_ids)

      # Agrupa por URL destino
      by_url: dict[str, list] = defaultdict(list)
      for notif in notifications:
          by_url[notif.webhook_url].append(notif)

      async with httpx.AsyncClient(timeout=10.0) as client:
          tasks = [
              _send_batch(client, url, notifs)
              for url, notifs in by_url.items()
          ]
          results = await asyncio.gather(*tasks, return_exceptions=True)

      # Log failures sem re-raise (best-effort)
      for url, result in zip(by_url.keys(), results):
          if isinstance(result, Exception):
              logger.warning("Batch webhook falhou para %s: %s", url, result)

  Ganho estimado: Para integradores com muitas câmeras (ex: 50 câmeras, 50 eventos simultâneos para o mesmo SIEM): −98% de conexões HTTP de saída. Latência agregada similar.
  Risco: Baixo se o receptor aceitar arrays. Verifique se os webhooks externos dos clientes aceitam Content-Type: application/json com array — se não, mantém envio individual.

  ---
  4. MEDIAMTX

  4.1 Buffer RTSP — Throughput vs Latência

  Arquivo: infra/mediamtx/mediamtx.yml

  # SITUAÇÃO ATUAL:
  writeQueueSize: 524288   # 512 KiB

  # PARA CÂMERAS RTMP PUSH (edge-agent → mediamtx):
  # Prioridade: baixa latência para o viewer HLS/WebRTC
  writeQueueSize: 524288   # manter — já é adequado para streaming
  hlsPartDuration: 200ms   # já está correto para low-latency HLS

  # PARA CÂMERAS COM STREAMS INSTÁVEIS (perdas de pacote):
  # Aumentar buffer absorve jitter sem disconnect:
  writeQueueSize: 1048576  # 1 MiB — se câmeras dropam frames frequentemente

  # SEPARAR POR PATH se tiver câmeras de diferentes perfis:
  pathDefaults:
    writeQueueSize: 524288   # padrão geral

  paths:
    "tenant-*/cam-*":
      writeQueueSize: 524288
      # lowLatency é controlado pelo hlsVariant: fmp4 já ativo

  Ganho estimado: RAM +256 KB por câmera (se aumentar para 1 MiB). Estabilidade +20% em redes com jitter >50ms. Latência neutra (jitter buffer não afeta latência de steady-state).
  Risco: Baixo. writeQueueSize é por-path em memória. Com 50 câmeras e 1 MiB: +50 MB de RAM total — aceitável.

  ---
  4.2 Segmentos de Gravação — Impacto de Memória vs I/O

  # CONFIGURAÇÃO ATUAL:
  recordSegmentDuration: 60s
  recordPartDuration: 10s
  recordFormat: fmp4

  # TRADEOFFS:
  # 60s é o sweet spot. Menor = mais file handles abertos + mais fsync = I/O spike.
  # Maior = mais dados perdidos em crash + mais RAM de buffer antes de flush.

  # SE o I/O do disco for o gargalo (muitas câmeras, HD spinning):
  recordPartDuration: 30s   # menos fsync intermediários
  # Custo: em crash, perde até 30s do último segmento em vez de 10s.

  # SE a RAM for o gargalo (servidor limitado):
  recordPartDuration: 5s    # flush mais frequente = menos buffer em memória
  # Custo: +I/O, latência de escrita maior.

  # RECOMENDAÇÃO para VMS típico (SSD, 20-50 câmeras):
  recordPartDuration: 10s   # manter o atual — já está otimizado
  recordSegmentDuration: 60s  # manter

  Ganho estimado: Neutro se mantiver atual. A configuração já é adequada para SSD.
  Risco: Mudança em recordPartDuration afeta a granularidade de seek no player HLS VOD. Teste antes.

  ---
  Resumo Executivo

  ┌────────────────────────┬─────────────────┬────────────┬─────────────────────┬────────────┐
  │          Item          │       CPU       │    RAM     │        Risco        │ Prioridade │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ Pool asyncpg correto   │ neutro          │ −50 MB     │ crítico se ignorado │ P0         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ Frame downscaling      │ −20% analytics  │ −30 MB/câm │ baixo               │ P1         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ Redis max_connections  │ neutro          │ −20 MB     │ baixo               │ P1         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ Cache LRU ROIs         │ −5% api         │ neutro     │ baixo               │ P1         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ GC explícito analytics │ neutro          │ −20 MB/câm │ mínimo              │ P2         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
                                                                                              
  # No __init__ do Orchestrator:
  concurrency = _compute_safe_concurrency()                                                   
  self._gpu_semaphore = asyncio.Semaphore(concurrency)
                                                                                              
  Ganho estimado: Em máquinas com 8GB+ VRAM: +2–3× throughput vs semaphore fixo em 4. Em CPU: sem efeito.
  Risco: Baixo. O min(..., 8) evita OOM. Requer torch disponível no ambiente (já está via ultralytics).
  
  ---                                                                                         
  1.4 GC Explícito Após Frame
                                                                                              
  # analytics/src/analytics/core/orchestrator.py — após processar cada frame

  import gc                                                                                             

  async def _process_camera_frame(self, camera_id: int, frame: np.ndarray, ...):
      try:
          results = await self._run_inference(frame)                                                                                                                                                                           await self._dispatch_to_plugins(camera_id, results)
      finally:                                                                                                                                                                                                       
          del frame          # libera o ndarray imediatamente                                                                                                                                                        
          del results
          # GC apenas se o contador de gerações tiver acumulado
          if gc.get_count()[0] > 700:
              gc.collect(0)  # coleta apenas geração 0 (rápido, <1ms)

  Ganho estimado: RAM −10–30 MB por câmera em steady state (evita ndarray de 1080p ficarem pendentes até o próximo ciclo GC). Sem impacto em CPU perceptível com collect(0).
  Risco: Mínimo.

  ---
  2. API SERVICE (FastAPI)

  2.1 Pool Asyncpg — O Problema Crítico Atual

  Este é o bug mais grave: com pool_size=10, max_overflow=20, se você rodar uvicorn --workers 4, cada processo cria seu próprio pool → 4 × 30 = 120 conexões. PostgreSQL default é max_connections=100. Resultado:   
  conexões recusadas em horário de pico.

  Arquivo: api/src/vms/infrastructure/database/connection.py

  import os

  def _pool_size_for_workers() -> tuple[int, int]:
      """
      Distribui conexões pelo número de workers Uvicorn.
      Target: total ≤ 80 (deixa 20 livres para psql, migrations, analytics).
      """
      workers = int(os.getenv("WEB_CONCURRENCY", "1"))
      # 80 conexões / N workers, mínimo 5, máximo 20
      per_worker = max(5, min(20, 80 // workers))
      overflow = max(2, per_worker // 2)
      return per_worker, overflow

  pool_size, max_overflow = _pool_size_for_workers()

  engine = create_async_engine(
      settings.database_url,
      pool_size=pool_size,
      max_overflow=max_overflow,
      pool_pre_ping=True,
      pool_recycle=1800,        # recicla conexões ociosas em 30min
      pool_timeout=30,          # falha rápido se pool esgotado (não trava forever)
      connect_args={
          "server_settings": {
              "application_name": f"vms-api-{os.getpid()}",
              "statement_timeout": "30000",   # 30s por query
          }
      },
  )

  E no docker-compose.yml:
  api:
    environment:
      WEB_CONCURRENCY: "4"    # expõe para o cálculo acima
    command: uvicorn vms.main:app --host 0.0.0.0 --port 8000 --workers 4

  Ganho estimado: Previne crash em produção sob carga. RAM −50 MB (menos conexões abertas). Latência P99 −20% (pool_timeout rápido em vez de hang).
  Risco: Médio se você esquecer de definir WEB_CONCURRENCY. Adicione validação no startup:

  # main.py — no lifespan startup
  if int(os.getenv("WEB_CONCURRENCY", "1")) > 1:
      assert pool_size * int(os.getenv("WEB_CONCURRENCY")) <= 80, \
          "Pool × workers excede 80 — risco de connection exhaustion"

  ---
  2.2 Redis — Limitar Concorrência Explicitamente

  aioredis.from_url() já cria um pool interno, mas sem max_connections ele cresce sem limite.

  # main.py — linha onde cria o Redis

  from redis.asyncio import from_url

  redis = from_url(
      settings.redis_url,
      encoding="utf-8",
      decode_responses=True,
      max_connections=20,       # por processo Uvicorn
      socket_keepalive=True,
      socket_keepalive_options={
          "TCP_KEEPIDLE": 60,
          "TCP_KEEPINTVL": 10,
          "TCP_KEEPCNT": 3,
      },
      retry_on_timeout=True,
  )

  Para o ARQ pool (separado), mesma lógica:
  from arq.connections import RedisSettings, create_pool

  arq_pool = await create_pool(
      RedisSettings.from_dsn(settings.redis_url),
      max_connections=10,    # jobs não precisam de muitas conexões simultâneas
  )

  Ganho estimado: RAM −15–25 MB (Redis connections idle têm ~1 MB cada). Estabilidade melhor sob burst.
  Risco: Baixo. Se max_connections=20 for insuficiente, redis.ConnectionError aparece nos logs — fácil de diagnosticar e aumentar.

  ---
  2.3 Cache LRU para ROIs por Câmera

  ROIs são consultadas a cada frame pelo analytics e também em requests de eventos. São dados quase-estáticos (mudam raramente).

  # api/src/vms/analytics/service.py (ou onde GET /internal/rois/ é servido)

  from functools import lru_cache
  from datetime import datetime, timedelta
  from typing import Any

  _roi_cache: dict[int, tuple[datetime, Any]] = {}
  _ROI_TTL = timedelta(seconds=60)

  async def get_rois_for_camera(camera_id: int, session: AsyncSession) -> list[dict]:
      now = datetime.utcnow()
      cached = _roi_cache.get(camera_id)
      if cached and (now - cached[0]) < _ROI_TTL:
          return cached[1]

      rois = await _fetch_rois_from_db(camera_id, session)
      _roi_cache[camera_id] = (now, rois)
      return rois

  # Invalida ao salvar nova ROI:
  def invalidate_roi_cache(camera_id: int):
      _roi_cache.pop(camera_id, None)

  Por que não @lru_cache: a função é async e recebe session que não é hashable. O dict manual com TTL é mais explícito e correto aqui.

  Ganho estimado: −80% queries para /internal/rois/ (analytics bate esse endpoint a cada frame × câmera). −5 ms de latência média na rota.
  Risco: Baixo. TTL de 60s é adequado — ROIs não mudam em tempo real.

  ---
  2.4 GZip nas Rotas de Listagem

  # api/src/vms/main.py — no create_app(), antes dos routers

  from starlette.middleware.gzip import GZipMiddleware

  app.add_middleware(
      GZipMiddleware,
      minimum_size=1024,   # só comprime respostas > 1KB
      compresslevel=4,     # balanceamento CPU×compressão (1=rápido, 9=máximo)
  )

  Ganho estimado: Bandwidth −60–70% em listagens de eventos/recordings com muitos itens. CPU +2% (custo da compressão). RAM neutro.
  Risco: Mínimo. minimum_size=1024 evita overhead em respostas pequenas (health check, etc).

  ---
  3. ARQ WORKER

  3.1 Separação por Prioridade (sem framework extra)

  ARQ não tem priority queues nativas, mas aceita múltiplos queue names com polling ordenado.

  # api/src/vms/worker.py

  class WorkerSettings:
      # ARQ processa queues na ordem listada: esgota high antes de low
      queue_name = "high"   # queue padrão para este worker

  # Segundo worker (novo serviço no docker-compose):
  class LowPriorityWorkerSettings:
      queue_name = "low"
      max_jobs = 10         # menos concorrência para jobs pesados
      job_timeout = 600     # reports PDF podem demorar

  # Nas tasks:
  async def task_dispatch_notification(ctx, ...):
      ...   # enqueued com queue="high"

  async def task_generate_report(ctx, ...):
      ...   # enqueued com queue="low"

  # Ao enfileirar (no service):
  await arq_pool.enqueue_job("task_dispatch_notification", ..., _queue_name="high")
  await arq_pool.enqueue_job("task_generate_report", ..., _queue_name="low")

  No docker-compose.yml:
  worker-high:
    command: python -m arq vms.worker.WorkerSettings

  worker-low:
    command: python -m arq vms.worker.LowPriorityWorkerSettings
    deploy:
      resources:
        limits:
          cpus: "1.0"    # reports não competem com notificações

  Ganho estimado: Latência de notificações cai de potencialmente >60s (se fila de reports ocupar slots) para <5s. Sem ganho de throughput bruto.
  Risco: Baixo. Requer novo serviço no compose e mudança nos enqueue_job() calls — grep por todos os pontos de enqueue primeiro.

  ---
  3.2 Limite de Concorrência por Tipo de Job via Redis Semaphore

  # api/src/vms/worker.py — decorator reutilizável

  from redis.asyncio import Redis
  import asyncio

  class RedisSemaphore:
      """Semáforo distribuído usando Redis SETNX."""

      def __init__(self, redis: Redis, key: str, limit: int, timeout: int = 300):
          self.redis = redis
          self.key = f"sem:{key}"
          self.limit_key = f"sem:{key}:count"
          self.limit = limit
          self.timeout = timeout

      async def __aenter__(self):
          for _ in range(30):  # tenta por 30s
              count = await self.redis.incr(self.limit_key)
              await self.redis.expire(self.limit_key, self.timeout)
              if count <= self.limit:
                  return self
              await self.redis.decr(self.limit_key)
              await asyncio.sleep(1)
          raise TimeoutError(f"Semáforo {self.key} esgotado após 30s")

      async def __aexit__(self, *_):
          await self.redis.decr(self.limit_key)

  # Uso em task pesada:
  async def task_generate_report(ctx, report_id: int):
      redis: Redis = ctx["redis"]
      async with RedisSemaphore(redis, "reports", limit=2):   # máx 2 PDFs simultâneos
          await _do_generate_report(report_id)

  Ganho estimado: Previne spike de RAM quando múltiplos reports PDF são gerados simultaneamente (cada um pode usar 200–500 MB). −60% RAM em burst.
  Risco: Médio. Se o job crashar sem executar __aexit__, o contador fica incrementado. Mitigação: expire no limite garante auto-reset em timeout segundos.

  ---
  3.3 Batch de Notificações por Webhook URL

  # api/src/vms/notifications/tasks.py

  async def task_dispatch_notification_batch(ctx, notification_ids: list[int]):
      """
      Agrupa notificações pendentes para o mesmo webhook URL e envia em bulk.
      Reduz connections HTTP de N para 1 por destino.
      """
      session_factory = get_session_factory()
      async with session_factory() as session:
          notifications = await _fetch_notifications(session, notification_ids)

      # Agrupa por URL destino
      by_url: dict[str, list] = defaultdict(list)
      for notif in notifications:
          by_url[notif.webhook_url].append(notif)

      async with httpx.AsyncClient(timeout=10.0) as client:
          tasks = [
              _send_batch(client, url, notifs)
              for url, notifs in by_url.items()
          ]
          results = await asyncio.gather(*tasks, return_exceptions=True)

      # Log failures sem re-raise (best-effort)
      for url, result in zip(by_url.keys(), results):
          if isinstance(result, Exception):
              logger.warning("Batch webhook falhou para %s: %s", url, result)

  Ganho estimado: Para integradores com muitas câmeras (ex: 50 câmeras, 50 eventos simultâneos para o mesmo SIEM): −98% de conexões HTTP de saída. Latência agregada similar.
  Risco: Baixo se o receptor aceitar arrays. Verifique se os webhooks externos dos clientes aceitam Content-Type: application/json com array — se não, mantém envio individual.

  ---
  4. MEDIAMTX

  4.1 Buffer RTSP — Throughput vs Latência

  Arquivo: infra/mediamtx/mediamtx.yml

  # SITUAÇÃO ATUAL:
  writeQueueSize: 524288   # 512 KiB

  # PARA CÂMERAS RTMP PUSH (edge-agent → mediamtx):
  # Prioridade: baixa latência para o viewer HLS/WebRTC
  writeQueueSize: 524288   # manter — já é adequado para streaming
  hlsPartDuration: 200ms   # já está correto para low-latency HLS

  # PARA CÂMERAS COM STREAMS INSTÁVEIS (perdas de pacote):
  # Aumentar buffer absorve jitter sem disconnect:
  writeQueueSize: 1048576  # 1 MiB — se câmeras dropam frames frequentemente

  # SEPARAR POR PATH se tiver câmeras de diferentes perfis:
  pathDefaults:
    writeQueueSize: 524288   # padrão geral

  paths:
    "tenant-*/cam-*":
      writeQueueSize: 524288
      # lowLatency é controlado pelo hlsVariant: fmp4 já ativo

  Ganho estimado: RAM +256 KB por câmera (se aumentar para 1 MiB). Estabilidade +20% em redes com jitter >50ms. Latência neutra (jitter buffer não afeta latência de steady-state).
  Risco: Baixo. writeQueueSize é por-path em memória. Com 50 câmeras e 1 MiB: +50 MB de RAM total — aceitável.

  ---
  4.2 Segmentos de Gravação — Impacto de Memória vs I/O

  # CONFIGURAÇÃO ATUAL:
  recordSegmentDuration: 60s
  recordPartDuration: 10s
  recordFormat: fmp4

  # TRADEOFFS:
  # 60s é o sweet spot. Menor = mais file handles abertos + mais fsync = I/O spike.
  # Maior = mais dados perdidos em crash + mais RAM de buffer antes de flush.

  # SE o I/O do disco for o gargalo (muitas câmeras, HD spinning):
  recordPartDuration: 30s   # menos fsync intermediários
  # Custo: em crash, perde até 30s do último segmento em vez de 10s.

  # SE a RAM for o gargalo (servidor limitado):
  recordPartDuration: 5s    # flush mais frequente = menos buffer em memória
  # Custo: +I/O, latência de escrita maior.

  # RECOMENDAÇÃO para VMS típico (SSD, 20-50 câmeras):
  recordPartDuration: 10s   # manter o atual — já está otimizado
  recordSegmentDuration: 60s  # manter

  Ganho estimado: Neutro se mantiver atual. A configuração já é adequada para SSD.
  Risco: Mudança em recordPartDuration afeta a granularidade de seek no player HLS VOD. Teste antes.

  ---
  Resumo Executivo

  ┌────────────────────────┬─────────────────┬────────────┬─────────────────────┬────────────┐
  │          Item          │       CPU       │    RAM     │        Risco        │ Prioridade │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ Pool asyncpg correto   │ neutro          │ −50 MB     │ crítico se ignorado │ P0         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ Frame downscaling      │ −20% analytics  │ −30 MB/câm │ baixo               │ P1         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ Redis max_connections  │ neutro          │ −20 MB     │ baixo               │ P1         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ Cache LRU ROIs         │ −5% api         │ neutro     │ baixo               │ P1         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  recordSegmentDuration: 60s  # manter

  Ganho estimado: Neutro se mantiver atual. A configuração já é adequada para SSD.
  Risco: Mudança em recordPartDuration afeta a granularidade de seek no player HLS VOD. Teste antes.

  ---
  Resumo Executivo

  ┌────────────────────────┬─────────────────┬────────────┬─────────────────────┬────────────┐
  │          Item          │       CPU       │    RAM     │        Risco        │ Prioridade │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ Pool asyncpg correto   │ neutro          │ −50 MB     │ crítico se ignorado │ P0         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ Frame downscaling      │ −20% analytics  │ −30 MB/câm │ baixo               │ P1         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ Redis max_connections  │ neutro          │ −20 MB     │ baixo               │ P1         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ Cache LRU ROIs         │ −5% api         │ neutro     │ baixo               │ P1         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ GC explícito analytics │ neutro          │ −20 MB/câm │ mínimo              │ P2         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ Batch inference        │ −10% gpu        │ neutro     │ médio               │ P2         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ GPU semaphore dinâmico │ +throughput GPU │ neutro     │ baixo               │ P2         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ Queue prioridade ARQ   │ neutro          │ neutro     │ baixo               │ P2         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ Semáforo por job type  │ neutro          │ −60% pico  │ médio               │ P2         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ GZip middleware        │ neutro          │ neutro     │ mínimo              │ P3         │
  ├────────────────────────┼─────────────────┼────────────┼─────────────────────┼────────────┤
  │ Batch notifications    │ neutro          │ neutro     │ baixo               │ P3         │
  └────────────────────────┴─────────────────┴────────────┴─────────────────────┴────────────┘

  Comece pelo P0 (pool sizing) — é o único item que causa falha em produção. O resto são otimizações de performance.



Sprint Plan — VMS MVP Production Fixes                                                                                                                                                                               
  S1 — HLS Auth (1 semana) 🔴 P0                                                                                                                                                                                     
  
  Problema: Segmentos .ts retornam 404 porque nginx serve /recordings/ sem autenticação e as URLs no m3u8 são caminhos absolutos de disco.

  Fix:
  - recordings/router.py — novo GET /api/v1/recordings/segment?token=<jwt>&path=<relpath> que valida JWT e serve o arquivo via FileResponse
  - recordings/service.py — reescrever build_day_playlist() para emitir URLs /api/v1/recordings/segment?token=TOKEN&path=RELPATH
  - nginx.conf — bloquear acesso direto a /recordings/
  - Frontend — passar JWT nas URLs do player HLS

  ---
  S2 — Analytics Snapshots (1 semana) 🔴 P0

  Problema: Eventos de analíticos não têm imagem.

  Fix:
  - Orchestrator _send_result() salva JPEG via cv2.imencode em /snapshots/{camera_id}/{date}/{event_id}.jpg
  - Novo GET /api/v1/analytics/events/{id}/snapshot endpoint
  - Volume /snapshots montado em analytics e api
  - Frontend renderiza thumbnail nos cards de evento                                                                                                                                                                                                                                                                                                                                                                                        ---                                                                                                                                                                                                                  S3 — Webhook Resilience (1 semana) 🟡                                                                                                                                                                                                                                                                                                                                                                                                     Problema: Capacidade para alta demanda.                                                                                                                                                                            

  Fix:
  - nginx: 1200r/min com burst=100
  - slowapi: 2000/min por tenant_id
  - Desacoplar ACK da câmera do processamento DB via ARQ queue

  ---
  S4 — Retenção Cíclica + Disco (1 semana) 🟡

  Problema: Retenção sem limite de seleção, disco pode encher.

  Fix:
  - Schema restrito a Literal[5, 15, 30] dias com validação
  - Migration para atualizar defaults
  - task_cleanup_old_segments com LRU eviction ao atingir 85% de quota
  - UI: seletor com 3 opções fixas (5/15/30 dias)

  ---
  S5 — UI/UX Responsive (1 semana) 🟡

  Problema: Telas com tamanho errado.

  Fix:
  - Padrão min-h-0 overflow-hidden em todos os painéis flex
  - aspect-video forçado no player
  - Grid responsivo com Tailwind para mosaico de câmeras

  ---
  S6 — Wizard + ROI (1.5 semanas) 🟢

  Fix:
  - Wiring POST /api/v1/cameras/discover (OnvifClient já existe)
  - Stream HLS ao vivo atrás do canvas PolygonEditor (depende de S1)
  - Editor ROI inline na página de detalhe da câmera
  - Slider de sensibilidade

  ---
  S7 — Docs Integração (0.5 semana) 🟢

  - docs/HIKVISION_SETUP.md
  - docs/INTELBRAS_SETUP.md

  ---
  Por onde começar? S1 (HLS auth) é o P0 mais impactante — posso implementar agora.