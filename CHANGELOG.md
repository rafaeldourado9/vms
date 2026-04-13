# Changelog

Todas as mudanças notáveis neste projeto.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Serviço VOD (Video on Demand)
- Serviço completo para streaming HLS de gravações
- Conversão automática de segmentos MP4 para HLS
- Playlist dinâmica gerada via ffmpeg (sem re-encoding)
- Suporte a múltiplos segmentos concatenados
- 6 novos endpoints REST para gerenciamento de streams
- Componente `RecordingPlayer` para playback VOD no frontend
- Serviço TypeScript `vodService` com polling automático
- Toggle VOD/MP4 na página de gravações
- Badge indicador visual para modo VOD
- Documentação completa em `docs/VOD_SERVICE.md`
- Testes unitários do serviço VOD
- Script de setup `scripts/vod_setup.sh`

#### Database
- Migration `010_vod_streams_table` para criar tabela de streams VOD
- Índices otimizados para tenant_id, camera_id e status

#### Infraestrutura
- Volume Docker `vod_streams` para armazenamento de playlists HLS
- Configuração Nginx para servir arquivos HLS com headers corretos
- Types MIME corretos (m3u8, ts)

### Changed

- RecordingsPage agora suporta dual-mode (VOD e legado MP4)
- Toggle padrão para modo VOD (melhor experiência)

### Deprecated

- Playback MP4 direto (ainda disponível como fallback)

### Performance

- Seek time reduzido de 2-5s para < 500ms
- Buffer otimizado (apenas segmentos necessários)
- Cache de 1 hora para playlists e segmentos HLS
- Sem re-encoding (codec copy), transcoding muito rápido

### Security

- Validação de path traversal no serve de arquivos HLS
- Acesso controlado por tenant isolation

---

## [1.0.0] - 2026-04-11

### Added

- Sistema inicial de gravações com segmentos MP4
- Streaming ao vivo via HLS/WebRTC
- Analytics com detecção por IA
- PTZ control
- ROI management
- Tactical view
- Multi-tenant support
- Edge agents para captura RTSP
- MediaMTX para media server
- FastAPI backend
- React frontend com hls.js

[Unreleased]: #unreleased
[1.0.0]: #100---2026-04-11
