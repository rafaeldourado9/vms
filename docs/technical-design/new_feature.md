# Contexto do Projeto — Branch VMS Inteligente com IA, Tracking e Reconhecimento Facial

## 1. Visão Geral

A ideia do projeto é evoluir uma VMS já existente para uma versão inteligente, focada em monitoramento em tempo real com visão computacional.

A VMS atual já trabalha com câmeras/streams, mas esta branch será criada especificamente para implementar uma camada de inteligência artificial sobre o vídeo ao vivo, aproximando o sistema de uma solução profissional de vigilância, investigação e reconhecimento visual.

O objetivo principal é criar uma experiência parecida com sistemas de segurança avançados, onde o operador consegue ver múltiplas câmeras ao vivo, acompanhar pessoas em movimento, visualizar bounding boxes, identificar pessoas cadastradas e receber eventos em tempo real.

Esta branch não deve substituir imediatamente a VMS atual. Ela deve funcionar como uma branch experimental/evolutiva para transformar a VMS em uma plataforma de análise inteligente de vídeo.

---

## 2. Nome sugerido da branch

```bash
git checkout -b feature/ai-tracking-dashboard
```

Outros nomes possíveis:

```bash
feature/smart-vms-ai
feature/realtime-ai-vms
feature/vision-tracking-dashboard
feature/face-recognition-vms
```

---

## 3. Objetivo da Branch

Criar uma versão da VMS com:

- Visualização de câmeras em tempo real;
- Grid multi-câmeras;
- Overlay com bounding boxes;
- Tracking de pessoas ao vivo;
- Identificação facial de pessoas cadastradas;
- Busca vetorial por embeddings faciais;
- Eventos em tempo real via WebSocket;
- Painel lateral investigativo;
- Timeline de eventos;
- Armazenamento de snapshots e evidências;
- Estrutura escalável para múltiplas câmeras.

O foco inicial não é criar uma IA perfeita, mas montar uma base arquitetural correta para evoluir o sistema.

---

## 4. Conceito Principal

A arquitetura deve separar o vídeo dos metadados.

O vídeo ao vivo não deve ser enviado frame a frame pelo FastAPI. O vídeo deve ser servido por uma camada própria de streaming, como MediaMTX, enquanto os dados de IA devem ser enviados em paralelo via WebSocket.

Fluxo ideal:

```text
Vídeo:
Câmera RTSP → MediaMTX → Frontend

Metadados:
Worker IA → Redis/RabbitMQ → FastAPI WebSocket → Frontend
```

O frontend exibe o vídeo normalmente e desenha por cima os dados recebidos da IA.

---

## 5. Arquitetura Geral

```text
Câmera RTSP
   ↓
MediaMTX
   ↓
Worker de Vídeo
OpenCV + YOLO + Tracker
   ↓
Reconhecimento Facial
InsightFace / DeepFace
   ↓
Banco Vetorial
Qdrant / FAISS
   ↓
Eventos
Redis Streams / RabbitMQ
   ↓
Backend
FastAPI + WebSocket
   ↓
Frontend
React + Canvas Overlay
   ↓
Operador
Dashboard VMS Inteligente
```

---

## 6. Stack Tecnológica

### Backend

- FastAPI
- Python
- PostgreSQL
- Redis
- RabbitMQ
- Docker
- Docker Compose
- MinIO/S3
- Qdrant
- MediaMTX

### Visão Computacional

- OpenCV
- YOLOv8, YOLOv11 ou equivalente
- ByteTrack
- BoT-SORT
- DeepSORT
- InsightFace
- DeepFace, opcional
- FAISS, opcional
- Qdrant, recomendado para produção

### Frontend

- React
- TypeScript
- TailwindCSS
- WebSocket
- Canvas API
- SVG Overlay, opcional
- WebRTC ou HLS para vídeo
- MediaMTX como servidor de stream

---

## 7. Ideia Visual do Dashboard

O dashboard deve seguir uma estética de VMS profissional, parecida com sistemas corporativos de CFTV.

Layout esperado:

```text
┌─────────────────────────────────────────────────────────────┐
│ Topbar: sistema, status, usuário, alertas                   │
├───────────────┬─────────────────────────────────────────────┤
│ Sidebar       │ Grid de Câmeras                              │
│               │                                             │
│ Perfil        │ ┌──────────────┐ ┌──────────────┐            │
│ Pessoa        │ │ Camera 01    │ │ Camera 02    │            │
│ reconhecida   │ │ vídeo + box  │ │ vídeo + box  │            │
│               │ └──────────────┘ └──────────────┘            │
│ Eventos       │ ┌──────────────┐ ┌──────────────┐            │
│ Timeline      │ │ Camera 03    │ │ Camera 04    │            │
│ Lista câmeras │ │ vídeo + box  │ │ vídeo + box  │            │
│               │ └──────────────┘ └──────────────┘            │
├───────────────┴─────────────────────────────────────────────┤
│ Timeline inferior / logs / sessão                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Componentes do Frontend

### 8.1 CameraGrid

Responsável por exibir múltiplas câmeras em formato de grid.

Cada câmera deve ter:

- Nome da câmera;
- Status: online/offline;
- Indicador LIVE;
- FPS;
- Latência;
- Resolução;
- Vídeo ao vivo;
- Overlay de detecção;
- Alertas visuais.

### 8.2 CameraPlayer

Componente responsável por renderizar o stream da câmera.

Pode usar:

- WebRTC via MediaMTX;
- HLS;
- MSE;
- MJPEG apenas para testes, não recomendado para produção.

### 8.3 CanvasOverlay

Camada transparente sobre o vídeo.

Responsável por desenhar:

- Bounding boxes;
- Track IDs;
- Nome da pessoa;
- Score de confiança;
- Cor diferente para pessoa conhecida/desconhecida;
- Indicadores de alerta;
- Linhas ou efeitos visuais opcionais.

Estrutura visual:

```text
<div class="camera-card">
  <video class="video-layer"></video>
  <canvas class="overlay-layer"></canvas>
</div>
```

### 8.4 PersonProfilePanel

Painel lateral com informações da pessoa reconhecida.

Campos esperados:

- Foto cadastrada;
- Nome;
- ID interno;
- Score do reconhecimento;
- Última câmera onde apareceu;
- Horário da última detecção;
- Status;
- Histórico recente.

### 8.5 EventTimeline

Linha do tempo com eventos importantes:

```text
03:10:12 — Pessoa detectada na Camera 01
03:10:15 — Face capturada
03:10:16 — Match com João Silva, score 0.89
03:10:20 — Pessoa saiu da região monitorada
03:11:05 — Pessoa reapareceu na Camera 03
```

### 8.6 CameraList

Lista lateral com todas as câmeras cadastradas.

Deve mostrar:

- Nome;
- Ambiente;
- Status;
- FPS;
- Quantidade de pessoas detectadas;
- Alertas ativos.

---

## 9. Como o Frontend Exibe o Tracking

O frontend não recebe vídeo processado com as caixas já desenhadas.

Ele recebe:

1. O vídeo ao vivo;
2. Os metadados da IA.

Exemplo de mensagem via WebSocket:

```json
{
  "type": "detections",
  "camera_id": "cam_01",
  "timestamp": "2026-05-17T21:30:00Z",
  "detections": [
    {
      "track_id": 17,
      "label": "person",
      "name": "Pessoa cadastrada",
      "confidence": 0.91,
      "recognition_status": "recognized",
      "bbox": {
        "x": 320,
        "y": 120,
        "w": 90,
        "h": 180
      }
    },
    {
      "track_id": 18,
      "label": "person",
      "name": "Desconhecido",
      "confidence": 0.74,
      "recognition_status": "unknown",
      "bbox": {
        "x": 720,
        "y": 140,
        "w": 110,
        "h": 210
      }
    }
  ]
}
```

O canvas desenha os boxes na posição correta sobre o vídeo.

---

## 10. Pipeline de IA

### 10.1 Leitura do Stream

O worker conecta no stream vindo do MediaMTX:

```text
rtsp://mediamtx:8554/camera_01
```

O worker usa OpenCV para ler os frames.

### 10.2 Detecção

YOLO detecta:

- Pessoa;
- Rosto;
- Veículo, em fases futuras;
- Placa, em fases futuras;
- Objetos suspeitos, em fases futuras.

Inicialmente, o foco deve ser apenas pessoa e rosto.

### 10.3 Tracking

O tracker mantém um ID temporário para cada pessoa.

Exemplo:

```text
Pessoa entra no frame → track_id 17
Pessoa anda pelo corredor → continua track_id 17
Pessoa vira de lado → continua track_id 17
Pessoa sai do frame → track_id 17 encerrado
```

Ferramentas recomendadas:

- ByteTrack;
- BoT-SORT;
- DeepSORT.

### 10.4 Reconhecimento Facial

Quando o sistema encontra um rosto com qualidade suficiente:

1. Recorta o rosto;
2. Normaliza a imagem;
3. Gera embedding facial;
4. Busca no Qdrant;
5. Retorna a pessoa mais parecida;
6. Associa o resultado ao track_id.

Exemplo:

```text
track_id 17
↓
face embedding
↓
Qdrant
↓
match: João Silva
score: 0.89
↓
track_id 17 = João Silva
```

### 10.5 Busca Vetorial

O Qdrant deve armazenar embeddings faciais das pessoas cadastradas.

Cada registro pode ter:

```json
{
  "person_id": "uuid",
  "name": "João Silva",
  "embedding": [0.123, 0.552, 0.901],
  "metadata": {
    "status": "authorized",
    "created_at": "2026-05-17T21:30:00Z"
  }
}
```

### 10.6 Publicação de Eventos

O worker publica eventos no Redis ou RabbitMQ.

Eventos possíveis:

- Pessoa detectada;
- Pessoa reconhecida;
- Pessoa desconhecida;
- Pessoa perdida;
- Face capturada;
- Alerta disparado;
- Snapshot salvo;
- Entrada em região proibida, futuro;
- Cruzamento de linha, futuro.

---

## 11. Backend FastAPI

O FastAPI deve ser responsável por:

- Autenticação;
- Cadastro de câmeras;
- Cadastro de pessoas;
- Upload de imagens faciais;
- Registro de eventos;
- Consulta de histórico;
- WebSocket para tempo real;
- API para dashboard;
- API para snapshots;
- API para timeline;
- Controle de permissões.

O FastAPI não deve processar vídeo diretamente em produção.

Ele deve orquestrar, armazenar e distribuir os dados.

---

## 12. Serviços da Arquitetura

### 12.1 MediaMTX

Responsável por receber e redistribuir streams.

Funções:

- Receber RTSP das câmeras;
- Redistribuir para workers;
- Servir WebRTC/HLS para o frontend;
- Reduzir conexões diretas nas câmeras.

### 12.2 Worker IA

Responsável pelo processamento pesado.

Funções:

- Ler frame;
- Rodar YOLO;
- Rodar tracker;
- Recortar rosto;
- Gerar embedding;
- Consultar Qdrant;
- Publicar eventos.

### 12.3 PostgreSQL

Responsável por dados estruturados.

Tabelas principais:

- users;
- cameras;
- persons;
- face_images;
- recognition_events;
- tracking_events;
- alerts;
- audit_logs.

### 12.4 Redis

Responsável por dados temporários e baixa latência.

Usos:

- Estado atual dos tracks;
- Cache de resultados;
- Pub/Sub;
- Rate limiting;
- Sessões;
- Últimos eventos por câmera.

### 12.5 RabbitMQ

Responsável por filas assíncronas.

Usos:

- Processamento de snapshots;
- Eventos de alerta;
- Tarefas pesadas;
- Envio de notificações;
- Persistência de eventos em lote.

### 12.6 MinIO/S3

Responsável por armazenar arquivos.

Armazena:

- Snapshots;
- Imagens faciais cadastradas;
- Recortes de rosto;
- Clipes curtos;
- Evidências de eventos.

### 12.7 Qdrant

Responsável pela busca vetorial.

Armazena:

- Embeddings faciais;
- Metadados de pessoas;
- Vetores para busca de similaridade.

---

## 13. Modelo de Dados Inicial

### cameras

```text
id
name
rtsp_url
mediamtx_path
location
status
created_at
updated_at
```

### persons

```text
id
name
document_optional
status
notes
created_at
updated_at
```

### face_images

```text
id
person_id
image_url
embedding_id
quality_score
created_at
```

### recognition_events

```text
id
camera_id
person_id
track_id
confidence
snapshot_url
bbox
timestamp
event_type
```

### tracking_events

```text
id
camera_id
track_id
bbox
label
confidence
timestamp
status
```

### alerts

```text
id
camera_id
person_id
event_id
alert_type
severity
message
created_at
acknowledged_at
```

---

## 14. Fases de Desenvolvimento

## Fase 1 — Base de Streaming

Objetivo:

- Integrar câmera RTSP;
- Passar stream pelo MediaMTX;
- Exibir vídeo no frontend.

Entrega:

```text
Câmera RTSP → MediaMTX → React Player
```

Sem IA ainda.

---

## Fase 2 — Detecção de Pessoa

Objetivo:

- Criar worker Python;
- Ler stream do MediaMTX;
- Rodar YOLO;
- Detectar pessoas;
- Publicar bounding boxes.

Entrega:

```text
Pessoa aparece na câmera → YOLO detecta → frontend desenha box
```

---

## Fase 3 — Tracking

Objetivo:

- Integrar ByteTrack ou BoT-SORT;
- Manter track_id por pessoa;
- Enviar track_id via WebSocket.

Entrega:

```text
Pessoa andando no vídeo mantém o mesmo ID visual
```

---

## Fase 4 — Reconhecimento Facial

Objetivo:

- Detectar rosto;
- Gerar embeddings;
- Comparar com Qdrant;
- Associar pessoa ao track.

Entrega:

```text
Pessoa detectada → rosto reconhecido → nome aparece no dashboard
```

---

## Fase 5 — Eventos e Timeline

Objetivo:

- Salvar eventos no PostgreSQL;
- Salvar snapshots no MinIO;
- Exibir timeline no frontend.

Entrega:

```text
Histórico visual dos eventos de reconhecimento
```

---

## Fase 6 — Multi-Câmera

Objetivo:

- Exibir múltiplas câmeras;
- Rodar múltiplos workers;
- Manter eventos por câmera;
- Preparar estrutura para múltiplas GPUs ou múltiplos containers.

Entrega:

```text
Grid com várias câmeras e tracking em tempo real
```

---

## Fase 7 — ReID / Rastreamento entre Câmeras

Objetivo futuro:

- Tentar identificar a mesma pessoa em câmeras diferentes;
- Usar aparência corporal, roupa, cor e embeddings de pessoa;
- Criar um ID global.

Entrega futura:

```text
Pessoa sai da Camera 01 e reaparece na Camera 03 mantendo associação provável
```

---

## 15. MVP Realista

O MVP inicial da branch deve ser:

```text
Uma VMS que exibe uma câmera ao vivo, detecta pessoas em tempo real, mantém um ID de tracking e desenha o overlay no frontend.
```

Critério de sucesso:

- Vídeo ao vivo carregando no frontend;
- Bounding box seguindo pessoa;
- Track ID persistente por alguns segundos;
- WebSocket funcionando;
- Latência aceitável;
- Código separado da VMS principal.

---

## 16. MVP Intermediário

Depois do MVP básico:

```text
Sistema reconhece uma pessoa cadastrada e mostra o nome dela em cima do vídeo.
```

Critério de sucesso:

- Cadastro de pessoa;
- Upload de imagem;
- Geração de embedding;
- Salvamento no Qdrant;
- Reconhecimento facial no stream;
- Nome aparecendo no overlay;
- Evento salvo no banco.

---

## 17. MVP Avançado

Versão mais próxima de uma VMS profissional:

```text
Grid multi-câmeras com tracking, reconhecimento facial, eventos, snapshots e painel investigativo.
```

Critério de sucesso:

- 4 câmeras simultâneas;
- Dashboard em grid;
- Painel lateral com perfil;
- Timeline de eventos;
- Snapshots no MinIO;
- Busca por histórico;
- Alertas visuais.

---

## 18. Pontos Técnicos Importantes

### 18.1 Não enviar frames pelo WebSocket

Errado:

```text
Worker envia imagem/frame pelo WebSocket para o frontend
```

Correto:

```text
MediaMTX envia vídeo
FastAPI envia apenas metadados
Frontend junta os dois visualmente
```

### 18.2 Coordenadas precisam ser normalizadas

O worker pode enviar bounding boxes em coordenadas normalizadas:

```json
{
  "x": 0.25,
  "y": 0.30,
  "w": 0.10,
  "h": 0.40
}
```

Assim o frontend adapta para qualquer resolução de tela.

### 18.3 Controlar FPS de inferência

Nem sempre precisa processar 30 FPS.

Pode processar:

```text
5 FPS para reconhecimento facial
10-15 FPS para tracking
30 FPS apenas no vídeo original
```

### 18.4 Evitar reconhecimento em todo frame

Reconhecimento facial deve ser controlado por qualidade e intervalo.

Exemplo:

```text
Só reconhecer o mesmo track a cada 1 ou 2 segundos
```

### 18.5 Separar detector e tracker

O detector encontra objetos.

O tracker mantém continuidade.

Não confundir os dois.

---

## 19. Desafios Esperados

- Latência;
- Consumo de GPU;
- Câmeras com baixa qualidade;
- Rostos pequenos;
- Pessoas de lado;
- Oclusão;
- Multidão;
- Troca de track_id;
- Falsos positivos;
- Sincronização entre vídeo e overlay;
- Escalabilidade com várias câmeras;
- Organização dos eventos;
- Segurança e LGPD.

---

## 20. Cuidados com LGPD e Uso Ético

Como o sistema envolve reconhecimento facial, deve haver cuidado com privacidade e proteção de dados.

Recomendações:

- Usar somente em ambientes autorizados;
- Cadastrar pessoas com consentimento quando aplicável;
- Registrar logs de acesso;
- Proteger imagens e embeddings;
- Usar autenticação forte;
- Controlar permissões por usuário;
- Permitir exclusão de dados;
- Evitar uso indevido para vigilância não autorizada.

---

## 21. Estrutura de Pastas Sugerida

```text
project/
  backend/
    app/
      api/
        routes/
          cameras.py
          persons.py
          events.py
          auth.py
          websocket.py
      core/
        config.py
        security.py
      database/
        models/
        migrations/
      services/
        camera_service.py
        person_service.py
        event_service.py
        qdrant_service.py
        minio_service.py
      main.py

  ai_worker/
    app/
      capture/
        rtsp_reader.py
      detection/
        yolo_detector.py
      tracking/
        tracker.py
      recognition/
        face_encoder.py
        face_matcher.py
      publishers/
        redis_publisher.py
        rabbitmq_publisher.py
      storage/
        snapshot_storage.py
      main.py

  frontend/
    src/
      components/
        CameraGrid/
        CameraPlayer/
        CanvasOverlay/
        PersonProfilePanel/
        EventTimeline/
        CameraList/
      hooks/
        useCameraStream.ts
        useDetectionsSocket.ts
      pages/
        Dashboard.tsx
        Cameras.tsx
        Persons.tsx
        Events.tsx
      services/
        api.ts
        websocket.ts

  infrastructure/
    docker-compose.yml
    mediamtx.yml
    nginx.conf

  docs/
    architecture.md
    api.md
    ai-pipeline.md
```

---

## 22. Docker Compose — Serviços Esperados

Serviços principais:

```text
backend
frontend
ai_worker
postgres
redis
rabbitmq
minio
qdrant
mediamtx
```

Fluxo:

```text
camera_rtsp → mediamtx → ai_worker
mediamtx → frontend
ai_worker → redis/rabbitmq
backend → redis/rabbitmq/postgres/qdrant/minio
frontend → backend websocket/api
```

---

## 23. Eventos em Tempo Real

Exemplo de evento de tracking:

```json
{
  "type": "tracking_update",
  "camera_id": "cam_01",
  "track_id": 17,
  "label": "person",
  "bbox": {
    "x": 0.31,
    "y": 0.22,
    "w": 0.11,
    "h": 0.42
  },
  "confidence": 0.88,
  "timestamp": "2026-05-17T21:30:00Z"
}
```

Exemplo de evento de reconhecimento:

```json
{
  "type": "face_recognition",
  "camera_id": "cam_01",
  "track_id": 17,
  "person": {
    "id": "person_uuid",
    "name": "João Silva",
    "status": "authorized"
  },
  "confidence": 0.91,
  "snapshot_url": "s3://snapshots/cam_01/event_123.jpg",
  "timestamp": "2026-05-17T21:30:02Z"
}
```

Exemplo de alerta:

```json
{
  "type": "alert",
  "severity": "high",
  "camera_id": "cam_01",
  "person_id": "person_uuid",
  "message": "Pessoa monitorada detectada na entrada principal",
  "timestamp": "2026-05-17T21:30:03Z"
}
```

---

## 24. O que NÃO fazer no início

Evitar começar com:

- Multi-câmera complexo;
- Reconhecimento facial perfeito;
- ReID entre câmeras;
- Interface extremamente complexa;
- Otimização prematura;
- Microserviços demais antes do MVP;
- Treinamento de modelo próprio;
- Streaming de frames via WebSocket.

Primeiro fazer funcionar:

```text
1 câmera
1 worker
1 detector
1 tracker
1 websocket
1 overlay
```

Depois evoluir.

---

## 25. Roadmap Resumido

```text
1. Criar branch
2. Integrar MediaMTX
3. Exibir câmera no frontend
4. Criar worker OpenCV
5. Rodar YOLO
6. Enviar bbox via WebSocket
7. Desenhar overlay no Canvas
8. Adicionar ByteTrack
9. Adicionar reconhecimento facial
10. Adicionar Qdrant
11. Salvar eventos no PostgreSQL
12. Salvar snapshots no MinIO
13. Criar timeline
14. Criar painel lateral
15. Escalar para múltiplas câmeras
16. Investigar ReID entre câmeras
```

---

## 26. Definição do Produto

O produto final será uma VMS inteligente com visão computacional em tempo real.

Ela deve permitir que o usuário:

- Visualize câmeras ao vivo;
- Veja pessoas sendo rastreadas;
- Identifique pessoas cadastradas;
- Receba alertas em tempo real;
- Consulte eventos passados;
- Veja snapshots dos reconhecimentos;
- Trabalhe com múltiplas câmeras;
- Use uma interface profissional, parecida com VMS corporativa.

---

## 27. Frase de Contexto para IA Codar

Este projeto é uma branch experimental de uma VMS existente. O objetivo é transformar a VMS em uma plataforma inteligente de monitoramento em tempo real, usando MediaMTX para streaming, OpenCV/YOLO para detecção, ByteTrack/BoT-SORT para tracking, InsightFace para reconhecimento facial, Qdrant para busca vetorial, PostgreSQL para dados estruturados, Redis/RabbitMQ para eventos em tempo real, MinIO para snapshots e FastAPI como backend principal. O frontend em React deve exibir o vídeo vindo do MediaMTX e desenhar os metadados de detecção em um canvas sobreposto, criando uma experiência de dashboard profissional com grid multi-câmeras, tracking ao vivo, reconhecimento facial, eventos e timeline investigativa.

---

## 28. Resultado Esperado

Ao final da branch, o sistema deve ser capaz de mostrar algo parecido com uma VMS inteligente profissional:

```text
Câmera ao vivo
+ bounding boxes
+ tracking IDs
+ nome da pessoa reconhecida
+ score de confiança
+ painel lateral com perfil
+ eventos em tempo real
+ snapshots
+ timeline
```

A prioridade é construir a base correta e escalável, começando simples e evoluindo por fases.
