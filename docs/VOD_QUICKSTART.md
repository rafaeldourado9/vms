# Guia Rápido - Serviço VOD

## 🚀 Deploy Rápido

```bash
# 1. Executa migração
docker compose run --rm api alembic upgrade head

# 2. Reconstrói e sobe
docker compose up -d --build api nginx

# 3. Verifica se está funcionando
curl http://localhost/health
```

## 📺 Uso no Frontend

1. Acesse: `http://localhost`
2. Vá para: **Gravações**
3. Selecione câmera e data
4. Toggle **VOD** na toolbar (azul = VOD)
5. Clique em um segmento
6. Aguarde stream HLS (~5-10s)
7. ✅ Vídeo com streaming eficiente!

## 🔧 Endpoints Principais

### Criar Stream VOD
```bash
POST /api/v1/vod/streams
Content-Type: application/json
Authorization: Bearer <token>

{
  "camera_id": "cam-123",
  "segment_ids": ["seg-1", "seg-2"],
  "starts_at": "2026-04-12T10:00:00Z",
  "ends_at": "2026-04-12T10:02:00Z"
}
```

### Verificar Status
```bash
GET /api/v1/vod/streams/{stream_id}
Authorization: Bearer <token>

# Response: {"status": "ready" | "generating" | "pending" | "failed"}
```

### Obter URL de Streaming
```bash
GET /api/v1/vod/streams/{stream_id}/playlist
Authorization: Bearer <token>

# Response: {"playlist_url": "/vod-streams/.../playlist.m3u8"}
```

## 🐛 Troubleshooting

### Stream não sai de "pending"
```bash
# Verifica logs
docker compose logs api | grep vod

# Verifica ffmpeg
docker compose exec api which ffmpeg
```

### Erro 404 em playlist
```bash
# Verifica volume
docker compose exec nginx ls -la /tmp/vod/

# Reload nginx
docker compose exec nginx nginx -s reload
```

### Testa API diretamente
```bash
# Lista streams
curl http://localhost/api/v1/vod/streams \
  -H "Authorization: Bearer <token>"
```

## 📊 Arquitetura em 1 Minuto

```
MP4 Segments → VODService → ffmpeg → HLS (.m3u8 + .ts)
                                      ↓
                              Nginx /vod-streams/
                                      ↓
                              Frontend (hls.js)
```

## ⚡ Performance

| Métrica | MP4 Direto | VOD HLS |
|---------|-----------|---------|
| Seek | 2-5s | < 500ms |
| Buffer | Alto | Otimizado |
| UX | Ruim | YouTube-like |

## 📚 Documentação Completa

- **Detalhes**: `docs/VOD_SERVICE.md`
- **Implementação**: `VOD_IMPLEMENTACAO.md`
- **Mudanças**: `CHANGELOG.md`

## 🧪 Testes

```bash
# Backend
cd api && pytest tests/unit/vod/ -v

# Setup automático
./scripts/vod_setup.sh
```

---

**Para mais detalhes, veja a documentação completa!**
