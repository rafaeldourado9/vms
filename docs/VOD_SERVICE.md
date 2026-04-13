# Serviço VOD (Video on Demand)

## Visão Geral

O serviço VOD converte segmentos de gravação MP4 em streams HLS dinâmicos, permitindo streaming eficiente de vídeo na timeline ao invés de servir arquivos MP4 diretamente no navegador.

## Arquitetura

```
Segmentos MP4 (MediaMTX)
         ↓
  VODService.generate_hls_playlist()
         ↓ (ffmpeg)
  Playlist HLS (.m3u8) + Segmentos TS (.ts)
         ↓
  Nginx serve /vod-streams/
         ↓
  Frontend consome via hls.js
```

## Componentes

### Backend (Python/FastAPI)

#### Estrutura de Arquivos
```
api/src/vms/vod/
├── __init__.py
├── domain.py          # Entidade VODStream
├── models.py          # Modelo SQLAlchemy
├── repository.py      # Repositório SQLAlchemy
├── router.py          # Endpoints HTTP
├── schemas.py         # Schemas Pydantic
└── service.py         # Lógica de negócio (ffmpeg, HLS)
```

#### Endpoints

```http
POST /api/v1/vod/streams
```
Cria stream VOD a partir de segmentos de gravação.

**Request:**
```json
{
  "camera_id": "cam-123",
  "segment_ids": ["seg-1", "seg-2", "seg-3"],
  "starts_at": "2026-04-12T10:00:00Z",
  "ends_at": "2026-04-12T10:03:00Z"
}
```

**Response:**
```json
{
  "id": "vod-stream-id",
  "status": "pending",
  "tenant_id": "tenant-1",
  "camera_id": "cam-123",
  "started_at": "2026-04-12T10:00:00Z",
  "ended_at": "2026-04-12T10:03:00Z",
  "created_at": "2026-04-12T10:05:00Z"
}
```

---

```http
GET /api/v1/vod/streams/{stream_id}
```
Status do stream VOD (para polling).

**Response:**
```json
{
  "id": "vod-stream-id",
  "status": "ready",
  "playlist_path": "/tmp/vod/tenant-1/cam-123/vod-stream-id/playlist.m3u8"
}
```

---

```http
GET /api/v1/vod/streams/{stream_id}/playlist
```
Obtém URL da playlist HLS para streaming.

**Response:**
```json
{
  "playlist_url": "/vod-streams/tenant-1/cam-123/vod-stream-id/playlist.m3u8",
  "status": "ready",
  "stream_id": "vod-stream-id"
}
```

---

```http
GET /api/v1/vod/playlists/{tenant_id}/{camera_id}/{stream_id}/{filename}
```
Serve arquivos HLS (.m3u8 ou .ts).

---

```http
GET /api/v1/vod/streams
```
Lista streams VOD do tenant.

**Query Params:**
- `camera_id` (opcional): Filtra por câmera
- `status_filter` (opcional): pending | generating | ready | failed

---

```http
DELETE /api/v1/vod/streams/{stream_id}
```
Remove stream VOD e arquivos associados.

### Frontend (TypeScript/React)

#### Estrutura de Arquivos
```
frontend/src/
├── services/
│   └── vod.ts              # Serviço TypeScript
└── components/
    └── camera/
        └── RecordingPlayer.tsx  # Componente de player VOD
```

#### Uso do Serviço

```typescript
import { vodService } from '@/services/vod'

// Cria stream VOD
const stream = await vodService.createStream({
  camera_id: 'cam-123',
  segment_ids: ['seg-1', 'seg-2', 'seg-3'],
  starts_at: '2026-04-12T10:00:00Z',
  ends_at: '2026-04-12T10:03:00Z',
})

// Aguarda ficar pronto (polling)
const playlistUrl = await vodService.waitForReady(stream.id, 30000)

// playlistUrl: /vod-streams/tenant-1/cam-123/stream-id/playlist.m3u8
```

#### Uso do Componente

```tsx
import { RecordingPlayer } from '@/components/camera/RecordingPlayer'

<RecordingPlayer
  segmentIds={['seg-1', 'seg-2', 'seg-3']}
  cameraId="cam-123"
  startsAt="2026-04-12T10:00:00Z"
  endsAt="2026-04-12T10:03:00Z"
  className="w-full h-full"
  onReady={() => console.log('Stream pronto!')}
  onError={(err) => console.error('Erro:', err)}
/>
```

## Configuração

### Database Migration

```bash
cd api
alembic upgrade head
```

Isso cria a tabela `vod_streams`:

```sql
CREATE TABLE vod_streams (
  id VARCHAR PRIMARY KEY,
  tenant_id VARCHAR NOT NULL,
  camera_id VARCHAR NOT NULL,
  segments TEXT[] NOT NULL,
  started_at TIMESTAMP WITH TIME ZONE NOT NULL,
  ended_at TIMESTAMP WITH TIME ZONE NOT NULL,
  playlist_path TEXT DEFAULT '',
  status VARCHAR DEFAULT 'pending',
  error TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX ix_vod_streams_tenant_id ON vod_streams(tenant_id);
CREATE INDEX ix_vod_streams_camera_id ON vod_streams(camera_id);
CREATE INDEX ix_vod_streams_status ON vod_streams(status);
```

### Docker Volumes

O volume `vod_streams` é montado em:
- API: `/tmp/vod`
- Nginx: `/tmp/vod` (read-only)

### Nginx Configuration

```nginx
location /vod-streams/ {
    alias      /tmp/vod/;
    autoindex  off;

    add_header Access-Control-Allow-Origin "*" always;
    add_header Cache-Control      "public, max-age=3600";
    add_header Accept-Ranges      bytes always;

    types {
        application/vnd.apple.mpegurl m3u8;
        video/MP2T ts;
    }
}
```

## Fluxo de Funcionamento

### 1. Criação do Stream

```typescript
// Frontend chama API
const stream = await vodService.createStream({
  camera_id: 'cam-123',
  segment_ids: ['seg-1', 'seg-2'],
  starts_at: '2026-04-12T10:00:00Z',
  ends_at: '2026-04-12T10:02:00Z',
})
// → status: "pending"
```

### 2. Geração do HLS (Background)

```python
# Backend gera playlist HLS
await vod_service.generate_hls_playlist(vod)

# ffmpeg command (single segment):
ffmpeg -i segment.mp4 \
  -c copy \
  -f hls \
  -hls_time 10 \
  -hls_playlist_type vod \
  -hls_segment_filename playlist_%03d.ts \
  -y playlist.m3u8

# ffmpeg command (multiple segments):
# 1. Cria concat.txt
# 2. ffmpeg -f concat -i concat.txt ... → playlist.m3u8
```

### 3. Polling até Ficar Pronto

```typescript
// Frontend aguarda (polling 1s)
const playlistUrl = await vodService.waitForReady(stream.id, 30000)
// → "/vod-streams/tenant-1/cam-123/stream-id/playlist.m3u8"
```

### 4. Playback HLS

```typescript
// hls.js carrega playlist
const hls = new Hls()
hls.loadSource(playlistUrl)
hls.attachMedia(videoElement)
// → Streaming adaptativo com seeks eficientes
```

## Vantagens sobre MP4 Direto

| Aspecto | MP4 Direto | VOD HLS |
|---------|-----------|---------|
| **Seek Time** | Lento (byte-range) | Rápido (segmentos TS) |
| **Buffer** | Arquivo inteiro | Apenas segmentos necessários |
| **Seeking** | Download parcial | Pula segmentos diretamente |
| **Múltiplos Segmentos** | Não suporta | Concatena automaticamente |
| **Bandwidth** | Alto (baixa eficiência) | Otimizado (hls.js) |
| **Experiência** | Similar a download | Similar a YouTube/Netflix |

## Troubleshooting

### Stream fica "pending" eternamente

**Causa:** ffmpeg não está instalado ou falhou.

**Solução:**
```bash
# Verifica logs da API
docker compose logs api | grep -i vod

# Verifica se ffmpeg está disponível
docker compose exec api which ffmpeg
```

### Erro "Segmento não encontrado"

**Causa:** Path do segmento está incorreto ou arquivo foi removido.

**Solução:**
```sql
-- Verifica segmentos no banco
SELECT id, file_path, started_at 
FROM recording_segments 
WHERE camera_id = 'cam-123' 
ORDER BY started_at DESC 
LIMIT 10;
```

### Erro de CORS no browser

**Causa:** Nginx não está configurado corretamente.

**Solução:**
```bash
# Verifica config do nginx
docker compose exec nginx nginx -t

# Reload nginx
docker compose exec nginx nginx -s reload
```

## Performance

### Otimizações de Transcoding

- **Codec Copy**: Sem re-encoding, apenas remuxing (muito rápido)
- **Segment Duration**: 10s (balanceia seek precision vs overhead)
- **HLS Type**: VOD (playlist fixa, sem updates)

### Cache

- Playlists: 1 hora (Cache-Control: max-age=3600)
- Segmentos TS: 1 hora
- Nginx: Sem buffering, streaming direto

### Limpeza Automática

Streams VOD são removidos automaticamente via:
- Cleanup manual: `cleanup_old_streams(tenant_id, before_date)`
- Futuro: Job ARQ diário (similar a `task_cleanup_old_segments`)

## Próximos Passos

- [ ] Adicionar job ARQ para limpeza automática
- [ ] Suporte a múltiplas qualidades (adaptive bitrate)
- [ ] Thumbnail generation para segmentos
- [ ] Clip export com VOD
- [ ] Métricas de uso (streams criados, tempo médio de geração)

## Testes

```bash
# Backend
cd api
pytest tests/unit/vod/ -v

# Frontend
cd frontend
npm test -- --testPathPattern=vod
```
