# VMS MVP - Architecture Diagram

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#1a1a2e', 'primaryTextColor': '#fff', 'primaryBorderColor': '#4a4a6a', 'lineColor': '#6a6a9a', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460' }}}%%

graph TB
    subgraph Client["🖥️ Frontend"]
        React[React App + TypeScript]
        Player[RecordingPlayer Component]
        UI[UI: Toggle VOD/MP4, Badge, PTZ, ROI]
        React --> Player
        React --> UI
    end

    subgraph Gateway["⚡ API Gateway"]
        Nginx[Nginx<br/>• HLS MIME: m3u8, ts<br/>• Cache: 1h<br/>• Tenant routing]
    end

    subgraph Backend["⚙️ Backend Services"]
        FastAPI[FastAPI REST API]
        VODSvc[vodService.ts<br/>Polling + State]
        HLSConv[ffmpeg Converter<br/>-codec copy]
        PlaylistGen[Dynamic Playlist Generator]
        
        FastAPI --> VODSvc
        VODSvc --> HLSConv
        HLSConv --> PlaylistGen
    end

    subgraph Media["📡 Media Layer"]
        MediaMTX[MediaMTX Server<br/>HLS/WebRTC]
        EdgeAgents[Edge Agents<br/>RTSP Capture]
        Cameras[📹 RTSP Cameras]
        
        Cameras --> EdgeAgents
        EdgeAgents --> MediaMTX
    end

    subgraph Storage["💾 Persistence"]
        DockerVol[(vod_streams Volume<br/>*.m3u8 + *.ts)]
        DB[(PostgreSQL<br/>vod_streams table<br/>Indexes: tenant_id, camera_id)]
        
        PlaylistGen --> DockerVol
        FastAPI --> DB
    end

    subgraph Security["🔐 Security"]
        TenantAuth[Tenant Isolation]
        PathGuard[Path Traversal Validation]
        
        TenantAuth --> DB
        PathGuard --> DockerVol
    end

    %% Data Flow
    React --"GET /api/recordings"--> FastAPI
    React --"HLS Request"--> Nginx
    Nginx --"Serve .m3u8/.ts"--> DockerVol
    FastAPI --"Metadata JSON"--> React
    MediaMTX --"Live HLS"--> Nginx
    FastAPI --"Trigger VOD"--> VODSvc
    DB --"Stream Records"--> FastAPI

    classDef layer fill:#16213e,stroke:#4a9eff,stroke-width:2px,color:#fff
    class Client,Gateway,Backend,Media,Storage,Security layer
```

## Sequence: VOD Playback Flow

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant FE as 🖥️ React
    participant API as ⚡ FastAPI
    participant VOD as 🎬 vodService
    participant FS as 📦 vod_streams
    participant NG as 🔄 Nginx

    U->>FE: Open Recordings (VOD mode)
    FE->>API: GET /api/vod/streams
    API->>VOD: Check conversion status
    VOD->>FS: Generate .m3u8 if needed
    FS-->>VOD: Playlist ready
    API-->>FE: { stream_url, metadata }
    FE->>NG: GET /hls/{id}/playlist.m3u8
    NG-->>FE: 200 + Cache-Control: 3600
    FE->>U: 🎥 Playback via hls.js (<500ms seek)
```

## Component Details

| Component | Technology | Responsibility |
|-----------|-----------|----------------|
| **React Frontend** | React 18 + TypeScript + hls.js | UI, VOD/MP4 toggle, player controls |
| **Nginx Gateway** | Nginx | HLS serving, caching, tenant routing, MIME types |
| **FastAPI** | Python 3.11 + FastAPI | REST API, business logic, tenant isolation |
| **vodService** | TypeScript | Polling, state management, conversion orchestration |
| **ffmpeg Converter** | ffmpeg | MP4→HLS conversion with `-codec copy` |
| **MediaMTX** | MediaMTX | Live HLS/WebRTC streaming, RTSP ingestion |
| **Edge Agents** | Go/Python | RTSP capture, segment upload, health checks |
| **PostgreSQL** | PostgreSQL 15 | Metadata storage, optimized indexes |
| **Docker Volume** | Docker | HLS artifact storage (*.m3u8, *.ts) |

## Data Flow Summary

1. 📹 Cameras stream RTSP → Edge Agents
2. 🔄 Edge Agents push segments → MediaMTX (live) / Storage (VOD)
3. ⚡ FastAPI exposes metadata via REST API
4. 🖥️ React fetches metadata + requests HLS via Nginx
5. 🎬 vodService orchestrates MP4→HLS conversion on-demand
6. 🔐 All requests validated for tenant isolation + path safety

---

> 💡 **View this diagram**:  
> - VS Code: Install "Mermaid Preview" extension  
> - Online: Paste at [mermaid.live](https://mermaid.live)  
> - GitHub/GitLab: Renders natively in `.md` files