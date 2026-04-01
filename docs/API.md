# VMS MVP — Contratos de API

> Base URL: `https://vms.{tenant}.local`
> Versão: v1
> Autenticação: JWT Bearer ou `Authorization: ApiKey vms_{prefix}_{secret}`

---

## Autenticação

### POST /api/v1/auth/token
Obtém access + refresh token.

**Request:**
```json
{ "email": "admin@tenant.com", "password": "senha123" }
```
**Response 200:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```
**Errors:** 401 credenciais inválidas, 429 rate limit (5/min)

---

### POST /api/v1/auth/refresh
Renova access token.

**Request:**
```json
{ "refresh_token": "eyJ..." }
```
**Response 200:** mesmo formato de `/token`

---

## Tenants

### POST /api/v1/tenants *(superadmin only)*
```json
{ "name": "Integrador SP", "slug": "integrador-sp" }
```
**Response 201:**
```json
{
  "id": "uuid",
  "name": "Integrador SP",
  "slug": "integrador-sp",
  "is_active": true,
  "created_at": "2026-03-30T00:00:00Z"
}
```

---

## Usuários

### GET /api/v1/users/me
Retorna perfil do usuário autenticado.

### POST /api/v1/users *(admin only)*
```json
{
  "email": "operador@empresa.com",
  "password": "senha123",
  "full_name": "João Silva",
  "role": "operator"
}
```

---

## Câmeras

### GET /api/v1/cameras
Lista câmeras do tenant. Filtros: `is_online`, `agent_id`.

**Response 200:**
```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

### POST /api/v1/cameras
```json
{
  "name": "Entrada Principal",
  "location": "Portaria Norte",
  "rtsp_url": "rtsp://192.168.1.100/stream",
  "manufacturer": "hikvision",
  "retention_days": 7,
  "agent_id": "uuid"
}
```

**Response 201:**
```json
{
  "id": "uuid",
  "name": "...",
  "ptz_supported": false,
  "retention_days": 7,
  "retention_days_pending": null,
  "retention_pending_from": null,
  "...": "demais campos"
}
```

### GET /api/v1/cameras/{id}
### PATCH /api/v1/cameras/{id}
### DELETE /api/v1/cameras/{id}

### GET /api/v1/cameras/{id}/stream-urls
Retorna URLs HLS/WebRTC assinadas para viewer ao vivo.

**Response 200:**
```json
{
  "hls_url": "http://mediamtx:8888/tenant-X/cam-Y/index.m3u8?token=jwt",
  "webrtc_url": "http://mediamtx:8889/tenant-X/cam-Y/whep?token=jwt",
  "rtsp_url": "rtsp://mediamtx:8554/tenant-X/cam-Y?token=jwt",
  "token": "eyJ...",
  "expires_at": "2026-04-01T15:15:00Z"
}
```

### GET /api/v1/cameras/{id}/vod *(novo — Sprint 3.5)*
Retorna URL HLS VOD para playback de gravações via timeline.

**Query params:** `from=2026-04-01T14:00:00Z` `to=2026-04-01T15:00:00Z`

**Response 200:**
```json
{
  "hls_url": "http://mediamtx:8888/recording/tenant-X/cam-Y/index.m3u8?...",
  "token": "eyJ...",
  "expires_at": "2026-04-01T15:15:00Z",
  "segments_count": 60,
  "has_gaps": false
}
```

### GET /api/v1/cameras/{id}/timeline *(atualizado — Sprint 3.5)*
Heat map de horas com gravação disponível.

**Query params:** `date=2026-04-01` (YYYY-MM-DD, obrigatório)

**Response 200:**
```json
{
  "date": "2026-04-01",
  "camera_id": "uuid",
  "hours": {
    "0": 60, "1": 60, "2": 60,
    "14": 58, "15": 60,
    "23": 43
  },
  "total_minutes": 1380
}
```
*Valores: minutos gravados na hora (0-60). Horas ausentes = sem gravação.*

---

## Agents

### GET /api/v1/agents
### POST /api/v1/agents
```json
{ "name": "Agent SP-01" }
```
**Response 201:**
```json
{
  "id": "uuid",
  "name": "Agent SP-01",
  "api_key": "vms_abc12345_secretxxxxxxx",  ← mostrado UMA vez
  "status": "pending"
}
```

### GET /api/v1/agents/me/config *(Agent auth)*
Retorna configuração de câmeras para o agent.

**Response 200:**
```json
{
  "agent_id": "uuid",
  "cameras": [
    {
      "id": "uuid",
      "name": "Câmera 01",
      "rtsp_url": "rtsp://192.168.1.100/stream",
      "rtmp_push_url": "rtmp://mediamtx:1935/tenant-1/cam-1",
      "enabled": true
    }
  ]
}
```

### POST /api/v1/agents/me/heartbeat *(Agent auth)*
```json
{
  "version": "1.0.0",
  "streams_running": 5,
  "streams_failed": 0,
  "uptime_seconds": 3600
}
```

### DELETE /api/v1/agents/{id}
Revoga API key do agent (irreversível).

---

## PTZ — Pan-Tilt-Zoom

> Disponível somente para câmeras com `stream_protocol=onvif` e `ptz_supported=true`.
> Habilitar via `PATCH /cameras/{id}` com `{ "ptz_supported": true }`.

### POST /api/v1/cameras/{id}/ptz/move
Move câmera (contínuo). Para com `/ptz/stop` ou após `timeout_seconds`.

```json
{ "pan": 0.5, "tilt": 0.0, "zoom": 0.0, "timeout_seconds": 5 }
```
*Valores: pan/tilt -1.0 a 1.0, zoom 0.0 a 1.0.*

**Response 200:** `{ "ok": true, "message": "Movimento iniciado" }`

### POST /api/v1/cameras/{id}/ptz/stop
Para qualquer movimento PTZ em curso.

**Response 200:** `{ "ok": true, "message": "Movimento parado" }`

### GET /api/v1/cameras/{id}/ptz/presets
Lista presets PTZ salvos na câmera.

**Response 200:**
```json
{
  "presets": [
    { "token": "1", "name": "Entrada" },
    { "token": "2", "name": "Pátio" }
  ]
}
```

### POST /api/v1/cameras/{id}/ptz/presets/{token}/goto
Move câmera para o preset.

**Response 200:** `{ "ok": true, "message": "Movendo para preset '1'" }`

### POST /api/v1/cameras/{id}/ptz/presets/{token}/save
Salva posição atual como preset. Use `"new"` como token para criar.

```json
{ "name": "Portaria Frente" }
```

**Response 200:** `{ "token": "3", "name": "Portaria Frente" }`

---

## Gravações

### GET /api/v1/recordings
Lista segmentos. Filtros: `camera_id`, `started_after`, `started_before`.

```json
{
  "items": [
    {
      "id": "uuid",
      "camera_id": "uuid",
      "file_path": "/recordings/tenant-1/cam-1/2026-03-30T12:00:00.mp4",
      "started_at": "2026-03-30T12:00:00Z",
      "ended_at": "2026-03-30T12:01:00Z",
      "duration_seconds": 60.0,
      "size_bytes": 15728640
    }
  ]
}
```

### GET /api/v1/recordings/clips
### POST /api/v1/recordings/clips
```json
{
  "camera_id": "uuid",
  "starts_at": "2026-03-30T12:00:00Z",
  "ends_at": "2026-03-30T12:05:00Z",
  "vms_event_id": "uuid"
}
```

### GET /api/v1/recordings/{id}/download
Redirect 302 para URL assinada do arquivo .mp4.

### GET /api/v1/recordings/clips/{id}
Status do clip (polling para UI saber quando ficou pronto).
```json
{ "id": "uuid", "status": "ready", "file_path": "/clips/..." }
```

---

## Eventos

### GET /api/v1/events
Filtros: `event_type`, `plate`, `camera_id`, `occurred_after`, `occurred_before`.

```json
{
  "items": [
    {
      "id": "uuid",
      "event_type": "alpr.detected",
      "plate": "ABC1D23",
      "confidence": 0.95,
      "camera_id": "uuid",
      "payload": { "bbox": [0.1, 0.2, 0.3, 0.4] },
      "occurred_at": "2026-03-30T12:34:56Z"
    }
  ]
}
```

---

## Webhooks de entrada (câmeras → VMS)

### POST /webhooks/alpr *(pré-normalizado)*
```json
{
  "camera_id": "uuid",
  "plate": "ABC1D23",
  "confidence": 0.95,
  "timestamp": "2026-03-30T12:34:56Z",
  "image_b64": "base64..."
}
```

### POST /webhooks/alpr/hikvision
Payload bruto Hikvision ANPR.

### POST /webhooks/alpr/intelbras
Payload bruto Intelbras ITSCAM.

### POST /webhooks/mediamtx/on_ready
### POST /webhooks/mediamtx/on_not_ready
### POST /webhooks/mediamtx/on_read
### POST /webhooks/mediamtx/on_unread
### POST /webhooks/mediamtx/segment_ready

---

## Notificações

### GET /api/v1/notifications/rules
### POST /api/v1/notifications/rules
```json
{
  "name": "Alertas ALPR",
  "event_type_pattern": "alpr.*",
  "destination_url": "https://central.monitoramento.com.br/vms-hook",
  "webhook_secret": "minha-chave-hmac",
  "is_active": true
}
```

### GET /api/v1/notifications/logs
Filtros: `rule_id`, `status`, `dispatched_after`.

---

## Analytics — ROIs

### GET /api/v1/analytics/rois
### POST /api/v1/analytics/rois
```json
{
  "camera_id": "uuid",
  "name": "Zona de Estacionamento A",
  "ia_type": "vehicle_dwell",
  "polygon_points": [[0.1, 0.2], [0.8, 0.2], [0.8, 0.9], [0.1, 0.9]],
  "config": { "min_dwell_seconds": 60, "max_dwell_seconds": 3600 },
  "is_active": true
}
```

---

## Analytics Interno *(API Key auth — analytics_service only)*

### POST /internal/analytics/ingest/
```json
{
  "plugin": "people_count",
  "camera_id": "uuid",
  "roi_id": "uuid",
  "event_type": "analytics.people.count",
  "payload": { "count": 3, "detections": [...] },
  "occurred_at": "2026-03-30T12:34:56Z"
}
```

### GET /internal/cameras/{id}/rois/
Retorna ROIs ativas para o analytics_service.

---

## Health

### GET /health
```json
{
  "status": "healthy",
  "services": {
    "database": "ok",
    "redis": "ok",
    "rabbitmq": "ok"
  },
  "version": "1.0.0",
  "cameras_online": 42
}
```

---

## SSE — Server-Sent Events

### GET /sse/events *(JWT auth)*
Stream de eventos em tempo real para o tenant autenticado.

**Formato:**
```
data: {"event_type": "alpr.detected", "plate": "ABC1D23", "camera_id": "uuid", ...}

data: {"event_type": "camera.online", "camera_id": "uuid", ...}
```

---

## Streaming Auth *(MediaMTX)*

### POST /streaming/publish-auth
MediaMTX chama antes de aceitar publisher.

**Request (MediaMTX):**
```json
{ "action": "publish", "path": "tenant-1/cam-42", "query": "token=xxxx" }
```
**Response 200** → publicação permitida
**Response 401** → publicação negada

---

## Códigos de Erro Padrão

| Código | Significado |
|--------|-------------|
| 400 | Payload inválido (detalhes em `detail`) |
| 401 | Não autenticado |
| 403 | Sem permissão para recurso |
| 404 | Recurso não encontrado |
| 409 | Conflito (slug/email duplicado) |
| 422 | Validação Pydantic falhou |
| 429 | Rate limit excedido |
| 503 | Serviço dependente indisponível |

**Formato de erro:**
```json
{
  "error": "not_found",
  "message": "Câmera uuid não encontrada",
  "detail": null
}
```
