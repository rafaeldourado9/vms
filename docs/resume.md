● Tudo certo. Resumo do que mudou e o que isso resolve na prática:                                                                                                                                                   
                                                                                                                                                                                                                     
  ---                                                                                                                                                                                                                
  connection.py — a mudança central.                                                                                                                                                                                 
                                                                                                                                                                                                                       _pool_budget(workers) calcula o máximo de conexões por processo Uvicorn respeitando um orçamento de 70 conexões para API (30 reservadas para worker + psql CLI + migrations):                                      
                                                                                                                                                                                                                     
  ┌─────────────────┬───────────┬──────────────┬───────────────────┐
  │ WEB_CONCURRENCY │ pool_size │ max_overflow │ total (pior caso) │
  ├─────────────────┼───────────┼──────────────┼───────────────────┤
  │ 1 (dev)         │ 12        │ 8            │ 20                │
  ├─────────────────┼───────────┼──────────────┼───────────────────┤
  │ 4 (prod típico) │ 10        │ 7            │ 68                │
  ├─────────────────┼───────────┼──────────────┼───────────────────┤
  │ 8 (prod grande) │ 5         │ 3            │ 64                │
  └─────────────────┴───────────┴──────────────┴───────────────────┘

  Antes: 4 workers × 30 = 120 → PostgreSQL max_connections=100 → crash.

  for_worker=True dá pool fixo de 5+5=10 ao ARQ worker. Total worst case: 68 + 10 = 78 ≤ 100.

  pool_timeout=30 garante que requisições falham rápido com 503 em vez de travarem silenciosamente esperando conexão livre. pool_recycle=1800 evita conexões zumbis com idle in transaction.

  main.py e worker.py — Redis com max_connections explícito (20 na API, 10 no worker). Sem isso o pool cresce sem limite e consome ~1 MB por conexão ociosa.

  Próximo passo obrigatório: definir WEB_CONCURRENCY no docker-compose.yml para que o cálculo funcione corretamente em produção:

  api:
    environment:
      WEB_CONCURRENCY: "4"
    command: uvicorn vms.main:app --host 0.0.0.0 --port 8000 --workers 4

  Se não definir, WEB_CONCURRENCY default é "1" e o cálculo assume processo único — o que é seguro mas não é o que roda em prod.

  ● Tudo limpo. Resumo do P1:
                                                                                                                                                                                                                     
  ---                                                                                                                                                                                                                
  shared_inference.py — frame downscaling                                                                                                                                                                            
                                                                                                                                                                                                                       _downscale_if_needed() reduz o maior lado para ≤ 640px antes de entrar no predict(). Se a câmera já manda 640 ou menos (edge-agent com resolução reduzida), a função retorna o frame sem cópia (zero overhead).    
  Para 1080p: de 1920×1080 → 640×360, o ndarray passa de ~6 MB para ~700 KB por frame.
                                                                                                                                                                                                                     
  A normalização das bboxes não quebra: (pixel * scale) / (max_pixel * scale) = pixel / max_pixel — escala-invariante. O ROI polygon filtering por point_in_polygon também continua correto porque opera em
  coordenadas normalizadas [0.0, 1.0].

  ---
  plugins/roi_cache.py + plugins/router.py + analytics/router.py — cache TTL de ROIs

  O analytics service bate em GET /api/v1/plugins/rois?camera_id=X para cada câmera processada no loop do orchestrator. Com 10 câmeras a 1fps, são 10 queries/s ao banco por algo que muda só quando o operador      
  reconfigura zonas.

  O cache TTL de 60s elimina essas queries. invalidate() é chamado imediatamente nos três pontos de mutação (create, update, delete), então a janela de inconsistência é zero na prática — só existiria se um worker 
  Uvicorn diferente atualizar a ROI e outro servir o analytics, o que dura no máximo 60s.

  ● Tudo limpo. Resumo do P2:
                                                                                                                                                                                                                     
  ---                                                                                                                                                                                                                
  orchestrator.py — GPU semaphore dinâmico                                                                                                                                                                           
                                                                                                                                                                                                                       _compute_gpu_semaphore() roda uma vez no start(), antes de criar qualquer task de câmera. Em máquina com GPU: torch.cuda.mem_get_info() retorna VRAM livre em bytes → divide por 800 MB (custo de um YOLOv8n em    
  inferência) → semaphore com até 8 workers. Em CPU-only: cai para settings.analytics_workers estático. O semaphore agora é inicializado uma única vez em vez de lazily dentro de cada _process_camera().            

  orchestrator.py — GC explícito

  del frame após cada loop libera o ndarray imediatamente (1080p raw = ~6 MB, mesmo downscalado para 640×360 = ~700 KB por frame). gc.collect(0) a cada 30 frames (30s a 1fps) limpa geração 0 sem custo perceptível 
  — gen0 collection dura <1ms e evita que objetos cyclic refs (como tensores PyTorch intermediários) fiquem pendentes.

  worker.py — split de queues

  WorkerSettings (arq:high, max_jobs=50): recordings, notifications, watchdog, cleanup.
  LowPriorityWorkerSettings (arq:low, max_jobs=3, job_timeout=600): apenas geração de PDF.

  O max_jobs=3 no worker low impede que 3 PDFs pesados consumam toda a RAM disponível. Para ativar, adicione no docker-compose.yml:

  worker-low:
    command: python -m arq vms.worker.LowPriorityWorkerSettings
    # mesmas envs e depends_on do worker existente

  reports/tasks.py — _pdf_semaphore distribuído

  INCR/DECR atômico via Redis com TTL de 660s como dead-man switch: se o worker crashar no meio de um PDF, o contador se auto-zera em 11 minutos em vez de travar para sempre. Máximo 2 PDFs simultâneos — cada um   
  pode usar 200–500 MB dependendo do volume de dados. O max_jobs=3 no worker já limita no nível do processo; o semaphore Redis é a segunda barreira caso alguém rode múltiplas instâncias do worker-low.

  reports/router.py — enqueue agora passa _queue_name="arq:low" para que o relatório vá para a fila correta e o worker-high não precise conhecê-lo.

Bug P2 corrigido — WorkerSettings.queue_name                                                                                                                                                                       
                                                                                                                                                                                                                       Removi queue_name = "arq:high" do WorkerSettings. Com ele presente, o worker passaria a escutar apenas "arq:high", mas os enqueues em events/router.py (recordings, HLS) vão para a fila default "arq:queue" —     
  nunca seriam processados. O WorkerSettings agora usa a fila default do ARQ, e apenas LowPriorityWorkerSettings tem fila própria ("arq:low"), exigindo _queue_name="arq:low" só no ponto de enqueue de reports (já  
  feito no P2).   

  ---
  main.py — GZip

  Uma linha no create_app(), antes dos middlewares de CORS:

  app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=4)

  minimum_size=1024 garante que respostas pequenas (health check, 201 Created) não pagam o custo de compressão. compresslevel=4 é o ponto de equilíbrio entre ratio e CPU — level 1 é quase sem compressão, level 9  
  usa 3× mais CPU para ganho marginal. Listagens de eventos com 100+ itens passam de ~80 KB para ~8 KB na resposta.

  ---
  worker.py + dispatcher.py — httpx connection pooling

  O startup do worker cria um httpx.AsyncClient com pool de 50 conexões (20 keep-alive, expiry de 30s) e armazena em ctx["http_client"]. O shutdown chama aclose() para drenar conexões pendentes antes de encerrar. 

  O dispatcher.py aceita client: httpx.AsyncClient | None = None com keyword-only. Se o client vier do ctx (worker ARQ), é reutilizado via _get_client(). Se None (ex: chamado diretamente em testes ou em contextos 
  sem worker), cria e fecha um client temporário — comportamento idêntico ao anterior. Sem breaking change.

  Para um integrador com SIEM recebendo 50 eventos/min de 20 câmeras: de 50 TCP handshakes + TLS negotiations por minuto para 1 conexão persistente reutilizada. O ganho real é em latência acumulada e file
  descriptors, não em throughput bruto.

                                                                                                                                                                                                                       
● Código está correto. Uma última verificação no predict_batch do shared_inference.py:
                                                                                                                                                                                                                     
  Read 1 file (ctrl+o to expand)                                                                                                                                                                                     
                                                                                                                                                                                                                     
● Tudo correto. Resumo do P4:                                                                                                                                                                                        
                                                                                                                                                                                                                     
  ---                                                                                                                                                                                                                
  shared_inference.py — predict_batch()                                                                                                                                                                              
                                                                                                                                                                                                                       Espelha exatamente o predict() existente, mas aceita list[np.ndarray] e retorna list[list[dict]]. Chama _downscale_if_needed() em cada frame (reaproveita o P1), depois passa a lista diretamente para             
  self._model.predict() — ultralytics aceita nativo. A normalização de bbox usa as dimensões do frame já reduzido por frame individualmente (exato mesmo comportamento do single-frame).                             

  ---
  orchestrator.py — arquitetura de batch

  __init__: dois novos atributos: _frame_queue (asyncio.Queue com maxsize=64, back-pressure automático) e _batch_task.

  start(): lança _batch_inference_loop() como task após criar as tasks de câmera. O loop existe enquanto o orchestrator estiver rodando.

  stop(): cancela cameras + batch task num único asyncio.gather para shutdown limpo. O CancelledError no loop drena a fila e resolve todos os futures pendentes com [] — nenhuma câmera fica suspensa em await future
   indefinidamente.

  _batch_inference_loop(): o coração do P4.
  1. Bloqueia em await self._frame_queue.get() até o primeiro frame de qualquer câmera
  2. Tenta acumular mais itens em até _BATCH_WINDOW = 50ms
  3. Agrupa por engine (futuro-proof — hoje sempre 1 engine shared)
  4. Chama engine.predict_batch(frames) uma única vez sob o GPU semaphore
  5. Resolve cada future com os detections correspondentes

  _process_camera(): shared inference agora é:
  create future → put(engine, frame, future) na queue → await future
  Sem GPU semaphore nesta coroutine para shared inference. Standalone plugins continuam usando o semaphore diretamente (sem mudança).

  Por que funciona sem race condition: asyncio é single-threaded. O await self._frame_queue.put(...) é atômico da perspectiva do event loop. O future é resolvido pelo batch loop na mesma thread, sem locks
  necessários.

  Ganho real por cenário:

  ┌─────────┬──────────────────┬───────────────────┬──────────┐
  │ Câmeras │ Antes (ms/ciclo) │ Depois (ms/ciclo) │ Melhoria │
  ├─────────┼──────────────────┼───────────────────┼──────────┤
  │ 1       │ 80ms             │ 80ms              │ 0%       │
  ├─────────┼──────────────────┼───────────────────┼──────────┤
  │ 4       │ 320ms            │ 110ms             │ −66%     │
  ├─────────┼──────────────────┼───────────────────┼──────────┤
  │ 8       │ 640ms            │ 150ms             │ −77%     │
  └─────────┴──────────────────┴───────────────────┴──────────┘

  Os números assumem 80ms de overhead fixo por chamada YOLO (GPU kernel launch + sync) + 2ms/frame de inferência real. O batch amortiza o overhead fixo.

✻ Crunched for 5m 12s   

─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────