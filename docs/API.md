# VMS MVP — Contratos de API

> Base URL: `https://{domain}/api/v1`
> Versao: 2.0 · Data: 2026-04-12
> Autenticacao: JWT Bearer ou `Authorization: ApiKey vms_{key}`

---

## Autenticacao

### POST /api/v1/auth/token
Obtem access + refresh token. Rate limit: **5/min**.

```json
// Request
{ "email": "admin@tenant.com", "password": "senha123" }

// Response 200
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```
Errors: 401 credenciais invalidas, 429 rate limit

### POST /api/v1/auth/refresh
Renova tokens. Rate limit: **10/min**.

```json
// Request
{ "refresh_token": "eyJ..." }

// Response 200
{ "access_token": "eyJ...", "refresh_token": "eyJ...", "token_type": "bearer", "expires_in": 900 }
```

---

## Usuarios

### GET /api/v1/users/me
Perfil do usuario autenticado.

### GET /api/v1/users
Lista usuarios do tenant. Admin ve todos, outros veem proprio tenant.

### POST /api/v1/users
Cria usuario. **Admin only**.

```json
{ "email": "op@tenant.com", "password": "...", "full_name": "Operador", "role": "operator" }
```
Roles: `admin`, `operator`, `viewer`

### POST /api/v1/tenants
Cria tenant. **Admin only**.

---

## Cameras

### GET /api/v1/cameras
Lista cameras do tenant.
Query params: `is_online` (bool)

### POST /api/v1/cameras
Cria camera + registra path no MediaMTX.

```json
{
  "name": "Entrada Principal",
  "location": "Portaria",
  "stream_protocol": "rtsp_pull",
  "rtsp_url": "rtsp://user:pass@192.168.1.100:554/stream",
  "manufacturer": "hikvision",
  "retention_days": 7,
  "agent_id": "uuid-do-agent"
}
```
Protocolos: `rtsp_pull`, `rtmp_push`, `onvif`

### GET /api/v1/cameras/{id}
Detalhes da camera.

### PATCH /api/v1/cameras/{id}
Atualiza campos da camera.

### DELETE /api/v1/cameras/{id}
Deleta camera (cleanup MediaMTX best-effort).

### GET /api/v1/cameras/{id}/stream-urls
URLs de streaming com viewer token.

```json
// Response
{
  "hls_url": "/hls/tenant-X/cam-Y/index.m3u8?token=eyJ...",
  "webrtc_url": "/webrtc/tenant-X/cam-Y/whep?token=eyJ...",
  "rtsp_url": null,
  "token": "eyJ...",
  "expires_at": "2026-04-12T17:00:00Z"
}
```

### GET /api/v1/cameras/{id}/snapshot
URL de snapshot (ONVIF ou ffmpeg frame).

```json
{ "snapshot_url": "/streaming/snapshot/tenant-X/cam-Y" }
```

### GET /api/v1/cameras/{id}/thumbnail
JPEG thumbnail via ffmpeg. Auth via query param `token`.

### POST /api/v1/cameras/onvif-probe
Testa conexao ONVIF e retorna capabilities.

```json
{ "url": "http://192.168.1.100:80/onvif/device_service", "username": "admin", "password": "..." }
```

### POST /api/v1/cameras/discover
Auto-discovery ONVIF na subnet.

### GET /api/v1/cameras/{id}/rtmp-config
Config RTMP push para camera.

```json
{ "rtmp_url": "rtmp://vms.host:1935/tenant-X/cam-Y", "stream_key": "abc123" }
```

---

## PTZ (Pan-Tilt-Zoom)

Requer camera com `ptz_supported: true` e protocolo ONVIF.

### POST /api/v1/cameras/{id}/ptz/move
Movimento continuo.

```json
{ "pan": 0.5, "tilt": 0.3, "zoom": 0.0 }
```

### POST /api/v1/cameras/{id}/ptz/stop
Para movimento.

### GET /api/v1/cameras/{id}/ptz/presets
Lista presets salvos.

### POST /api/v1/cameras/{id}/ptz/presets/{token}/goto
Move para preset.

### POST /api/v1/cameras/{id}/ptz/presets/{token}/save
Salva posicao atual como preset.

---

## Agents (Edge)

### GET /api/v1/agents
Lista agents do tenant.

### POST /api/v1/agents
Cria agent + gera API key.

```json
{ "name": "Agent Filial SP" }
// Response inclui api_key (mostrada uma unica vez)
```

### GET /api/v1/agents/{id}
Detalhes do agent.

### DELETE /api/v1/agents/{id}
Deleta agent + revoga API key.

### GET /api/v1/agents/me/config
**Auth: ApiKey**. Config de cameras para o agent autenticado.

### POST /api/v1/agents/me/heartbeat
**Auth: ApiKey**. Registra heartbeat + status.

```json
{ "version": "1.2.0", "streams_running": 5, "streams_failed": 0 }
```

### WS /api/v1/agents/me/ws
**Auth: ApiKey (query)**. WebSocket para push de config em tempo real.

---

## Eventos

### GET /api/v1/events
Lista eventos do tenant.
Query params: `event_type`, `plate`, `camera_id`, `occurred_after`, `occurred_before`, `limit`, `offset`

### Webhooks de Cameras (sem auth)

| Endpoint | Rate Limit | Fabricante |
|----------|-----------|------------|
| POST /webhooks/alpr | 500/min | Generico |
| POST /webhooks/alpr/{manufacturer} | 500/min | Hikvision, Intelbras |
| POST /hik_pro_connect | 120/min | Hikvision Pro Connect |
| POST /intelbras_events | 120/min | Intelbras |
| POST /camera_events | 120/min | Generico |

### Webhooks MediaMTX (internos)

| Endpoint | Trigger |
|----------|---------|
| POST /webhooks/mediamtx/on_ready | Camera online |
| POST /webhooks/mediamtx/on_not_ready | Camera offline |
| POST /webhooks/mediamtx/segment_ready | Segmento gravado (60s) |

---

## Gravacoes

### GET /api/v1/recordings
Lista segmentos. Query params: `camera_id`, `started_after`, `started_before`, `limit`, `offset`

### GET /api/v1/cameras/{id}/timeline
Timeline por hora (cobertura %).

```json
[
  { "hour": 14, "coverage_pct": 100, "segment_count": 60 },
  { "hour": 15, "coverage_pct": 83, "segment_count": 50 }
]
```

### POST /api/v1/recordings/clips
Cria clip a partir de range de segmentos.

```json
{ "camera_id": "...", "starts_at": "2026-04-12T14:00:00Z", "ends_at": "2026-04-12T14:05:00Z" }
```

### GET /api/v1/recordings/clips
Lista clips. Query params: `camera_id`, `limit`, `offset`

### GET /api/v1/recordings/clips/{id}
Status do clip (polling para conclusao).

### GET /api/v1/recordings/{id}/download
URL de download do segmento.

---

## Notificacoes

### GET /api/v1/notifications/rules
Lista regras de notificacao do tenant.

### POST /api/v1/notifications/rules
Cria regra.

```json
{
  "name": "ALPR para Central",
  "event_type_pattern": "alpr.*",
  "destination_url": "https://central.example.com/webhook",
  "webhook_secret": "minha-chave-secreta"
}
```
Webhooks saem com header `X-VMS-Signature: hmac-sha256=...`

### GET /api/v1/notifications/rules/{id}
Detalhes da regra.

### DELETE /api/v1/notifications/rules/{id}
Deleta regra.

### GET /api/v1/notifications/logs
Logs de envio. Query params: `rule_id`, `status`

---

## SSE (Server-Sent Events)

### GET /api/v1/sse?token={jwt}
Stream de eventos em tempo real via Redis pub/sub.
Max 30 conexoes simultaneas. Heartbeat 15s.

Eventos: `camera.online`, `camera.offline`, `alpr.detected`, `analytics.*`

---

## Analytics

### GET /api/v1/analytics/catalog
Catalogo de plugins disponiveis (sem auth).

```json
[
  {
    "id": "intrusion",
    "name": "Intrusion Detection",
    "category": "security",
    "model_size": "3.2 MB",
    "fps_cost": 1,
    "classes": ["person", "car", "truck"],
    "is_available": true
  }
]
```

### GET /api/v1/analytics/catalog/{plugin_id}
Detalhes de um plugin.

### POST /api/v1/analytics/install
Instala plugin em edge agent.

```json
{ "plugin_id": "intrusion", "edge_agent_id": "...", "fps_target": 1 }
```

### GET /api/v1/analytics/installations
Lista instalacoes do tenant.

### DELETE /api/v1/analytics/installations/{id}
Remove instalacao.

### PATCH /api/v1/analytics/installations/{id}/status
Atualiza status (running | stopped | installed | error).

### GET /api/v1/analytics/events
Lista eventos de analytics.
Query params: `camera_id`, `plugin_id`, `severity`, `occurred_after`, `occurred_before`, `limit`

### POST /api/v1/analytics/events
Cria evento de analytics.

### GET /api/v1/analytics/stats?hours=24
Estatisticas do periodo.

```json
{
  "total": 1523,
  "by_severity": { "critical": 12, "warning": 89, "info": 1422 },
  "by_plugin": { "intrusion": 45, "people_count": 800, "fire_smoke": 3 },
  "top_cameras": [{ "camera_id": "...", "count": 234 }],
  "period_hours": 24
}
```

---

## ROIs (Regioes de Interesse)

### GET /api/v1/analytics/rois
Lista ROIs. Query params: `camera_id`, `plugin_id`

```json
[
  {
    "id": "uuid",
    "camera_id": "cam-001",
    "plugin_id": "intrusion",
    "name": "Zona Proibida",
    "polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
    "config": { "min_confidence": 0.5, "cooldown_seconds": 30 },
    "is_active": true,
    "created_at": "2026-04-12T10:00:00Z"
  }
]
```

### POST /api/v1/analytics/rois
Cria ROI.

```json
{
  "camera_id": "cam-001",
  "plugin_id": "intrusion",
  "name": "Entrada",
  "polygon": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
  "config": { "min_confidence": 0.6, "cooldown_seconds": 45 }
}
```

### PUT /api/v1/analytics/rois/{id}
Atualiza ROI.

### DELETE /api/v1/analytics/rois/{id}
Deleta ROI.

---

## Plugin Contract (Machine-to-Machine)

Endpoints usados pelo Analytics Service. Auth: `Authorization: ApiKey {key}`

### GET /api/v1/plugins/cameras
Lista cameras online para processamento.

### GET /api/v1/plugins/stream-token?camera_id={id}
Token RTSP para stream do MediaMTX.

### GET /api/v1/plugins/rois?camera_id={id}
ROIs ativas para o plugin processar.

### POST /api/v1/plugins/events
Ingere evento detectado pelo plugin.

```json
{
  "camera_id": "cam-001",
  "event_type": "analytics.intrusion.detected",
  "confidence": 0.92,
  "occurred_at": "2026-04-12T12:34:56Z",
  "payload": {
    "roi_id": "roi-uuid",
    "detection_count": 2,
    "detections": [{ "class": "person", "confidence": 0.87, "bbox": [0.1, 0.2, 0.3, 0.4] }]
  }
}
```

---

## Streaming Auth (MediaMTX callbacks)

### POST /streaming/publish-auth
Valida publish (agent RTMP push ou camera RTMP). Sem auth.

### POST /streaming/read-auth
Valida viewer (HLS/WebRTC token). Sem auth.

### POST /streaming/analytics-auth
Acesso simplificado para analytics service. Sem auth.

### GET /streaming/auth-check
Nginx auth_request para HLS/WebRTC.

---

## Health & Metrics

### GET /health
Status dos servicos. Sem auth.

```json
{
  "status": "healthy",
  "services": {
    "database": "ok",
    "redis": "ok",
    "rabbitmq": "ok",
    "mediamtx": "ok"
  },
  "cameras": { "online": 45, "total": 50 }
}
```

### GET /metrics
Metricas gerais. Sem auth.

### GET /system/server-address
URL do tunnel Cloudflare (se ativo). Sem auth.
