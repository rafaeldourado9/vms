# 📋 Índice - Engenharia Reversa CluebaseVMS

## 📁 Documentos Disponíveis

| Documento | Descrição |
|-----------|-----------|
| **[README.md](./README.md)** | Visão geral completa do sistema: arquitetura, containers, credenciais, endpoints |
| **[IA_ANALYTICS.md](./IA_ANALYTICS.md)** | Sistema completo de IA e Analytics: tipos, configurações, modelos, integrações |
| **ESTE ARQUIVO** | Índice e mapa do codebase |

---

## 🗂️ Localização dos Arquivos Extraídos

### Código Fonte Extraído
```
C:\Users\Rafael Dourado\Desktop\cluebase-src\
├── README.md                    ← Visão geral do sistema
├── IA_ANALYTICS.md             ← Documentação completa de IA/Analytics
├── INDICE.md                   ← Este arquivo
│
├── backend\                     ← Backend Node.js (container)
│   ├── src\
│   │   ├── config\              (2 arquivos)
│   │   │   ├── config.js        ← Config central da aplicação
│   │   │   └── sequelize.js     ← Config ORM Sequelize
│   │   │
│   │   ├── constants\           (1 arquivo)
│   │   │   └── index.js         ← 12.800 linhas de constantes
│   │   │
│   │   ├── db\
│   │   │   ├── config\          (1 arquivo)
│   │   │   │   └── config.js    ← Config Sequelize CLI
│   │   │   └── migrations\      (250+ arquivos)
│   │   │       └── *.js         ← Migrações Dez 2020 - Abr 2025
│   │   │
│   │   ├── models\              (51 arquivos)
│   │   │   ├── index.js         ← Auto-load de modelos
│   │   │   ├── user.js          ← Modelo Usuário
│   │   │   ├── camera.js        ← Modelo Câmera
│   │   │   ├── event.js         ← Modelo Evento
│   │   │   ├── analytics.js     ← Modelo Analytics
│   │   │   ├── customAnalytics.js ← Analytics Customizado
│   │   │   ├── customModel.js   ← Modelos IA Customizados
│   │   │   ├── face.js          ← Reconhecimento Facial
│   │   │   ├── licensePlate.js  ← Reconhecimento de Placas
│   │   │   ├── list.js          ← Watchlists
│   │   │   ├── detectionRule.js ← Regras de Detecção
│   │   │   └── ...              (41 outros modelos)
│   │   │
│   │   ├── rtsp-to-webrtc\      (50 arquivos)
│   │   │   ├── main.go          ← Entry point (Go)
│   │   │   ├── config.go        ← Configuração (Go)
│   │   │   ├── stream.go        ← RTSP Workers (Go)
│   │   │   ├── http.go          ← API HTTP (Go)
│   │   │   ├── webrtc-config.json ← Config WebRTC
│   │   │   ├── .env             ← Variáveis ambiente
│   │   │   ├── Dockerfile
│   │   │   └── web\             ← UI simples
│   │   │
│   │   ├── migration\           (12 diretórios)
│   │   │   └── ...              ← Scripts de migração de dados
│   │   │
│   │   └── videos\              (5 arquivos)
│   │       └── *.mp4, *.ts      ← Vídeos de demonstração
│   │
│   ├── node_modules\
│   ├── .sequelizerc
│   └── [diretórios Linux: bin, dev, etc, lib, usr, var...]
│
├── frontend\                    ← Frontend Nginx/Alpine (container)
│   ├── usr\share\nginx\html\
│   │   ├── index.html           ← Entry point React
│   │   ├── manifest.json        ← Manifest de assets
│   │   ├── main.*.js            ← Bundle principal (minificado)
│   │   ├── vendors~main.*.js    ← Vendors (minificado)
│   │   ├── main.*.css           ← Styles principal
│   │   ├── 1.*.css              ← Styles vendors
│   │   └── images\              ← Imagens estáticas
│   │
│   ├── etc\nginx\               ← Config Nginx
│   ├── docker-entrypoint.sh
│   └── [estrutura Alpine Linux]
│
└── frontend-js\                 ← JS/CSS frontend (cópia)
    ├── main.73c31e224e3d9a419713.js
    ├── vendors~main.73c31e224e3d9a419713.js
    ├── main.73c31e22.css
    └── 1.73c31e22.css
```

### Arquivos Originais (Fonte)
```
C:\Users\Rafael Dourado\Downloads\CluebaseVMS-windows-offline\CluebaseVMS-windows\CluebaseVMS-windows\
├── all_images.tar               ← Imagem Docker completa (tarball)
├── .env                         ← Variáveis de ambiente
├── nginx.conf                   ← Config proxy Nginx
├── rtsp-simple-server.yml       ← Config servidor RTSP
├── docker-confs\
│   └── docker-compose-ai.yml    ← Docker Compose completo
├── branding\                    ← Customização de marca
├── certs\                       ← Certificados SSL
├── mysql-conf\                  ← Config MySQL
├── logo\                        ← Logos
├── static\                      ← Assets estáticos
└── *.ps1                        ← Scripts PowerShell
    ├── install_docker.ps1
    ├── install_vms.ps1
    ├── install_wsl.ps1
    ├── start.ps1
    ├── stop.ps1
    ├── restart.ps1
    ├── uninstall.ps1
    ├── update.ps1
    ├── newDisks.ps1
    ├── newIP.ps1
    └── newTZ.ps1
```

---

## 🔐 Credenciais Encontradas

### MySQL
```
Host: 127.0.0.1:3307
Database: vcloud
User: root
Password: DGkj^dg_DF++334-343-__3453^5EFg_ESF_D3++4111^WF_SFs+gb-dg
```

### Secrets
```
SECRET_WORD: verysecret
INTERNAL_RTSP_AUTH: vms_internal
```

### Google Maps API
```
AIzaSyCdpQdtnvNz8zO0OL-lk2TkR1YvJTVH7c
```

### Serviços IA
```
GPT Proxy Access Key: efg-GPT-6245gsl_$@flk
GPT Proxy Address: https://link.vcloud.ai:4040
DataBerry Token: fcf3c117-b041-4f44-b724-fc351d1b0659
```

---

## 📊 Resumo por Camada

### 1. Camada de Banco de Dados (MySQL 8.0.32)
- **250+ migrações** (Dez 2020 - Abr 2025)
- **51 modelos Sequelize**
- Multi-tenant (Accounts, Organizations)
- Full-text search em eventos (JSON metadata)

### 2. Camada Backend API (Node.js)
- **Express.js** com Socket.io
- **Sequelize ORM** com MySQL
- **JWT** para autenticação
- **bcrypt** para hash de senhas
- Pool de conexões: 0-300
- Logging de queries lentas (>1000ms)

### 3. Camada de Streaming (Go)
- **RTSP-to-WebRTC** baseado em deepch/RTSPtoWebRTC
- Codecs: H264 (vídeo), PCM alaw/mulaw/OPUS (áudio)
- STUN servers: Google (stun.l.google.com:19302)
- API HTTP com Gin framework
- WebRTC com Pion

### 4. Camada de IA/Analytics
- **Serviço AI** (porta 9001)
- **Serviço VA** (motion detection, porta 4646)
- **Ollama/LLaVA** (porta 11434, local)
- **Roadar Analytics** (porta 8095)
- **VCA Incoresoft** (cloud API)
- Modelos: YOLO, TensorFlow, Custom

### 5. Camada Frontend (React + Nginx)
- React compilado (webpack bundle)
- Google Maps integrado
- Nginx como proxy reverso
- SSL (certificados em /certs)

### 6. Camada de Proxy (Nginx)
- Proxy reverso para frontend e backend
- WebSocket support (Socket.io)
- HTTP/2 ready
- SSL/TLS (opcional)
- Client max body: unlimited

---

## 🎯 Funcionalidades Principais

### Vídeo
- [x] Visualização ao vivo (WebRTC)
- [x] Gravação contínua (Archive)
- [x] Gravação por agendamento
- [x] Gravação por alarme
- [x] Livestream (RTSP broadcast)
- [x] Layouts customizáveis (grids)
- [x] Shared layouts (compartilhados)

### Analytics IA
- [x] Object in Zone (50+ objetos)
- [x] Face Recognition com watchlists
- [x] LPR (reconhecimento de placas)
- [x] Crowd detection
- [x] Smoke & Fire detection
- [x] PPE detection (EPIs)
- [x] Traffic counting
- [x] Smart tracking
- [x] Motion detection
- [x] Sabotage detection (defocus, flash, etc)
- [x] Custom models (YOLO/TensorFlow)
- [x] Edge AI (processamento na câmera)
- [x] LLM integration (Ollama, OpenAI)

### Controle de Acesso
- [x] Integration com Bolid
- [x] Integration com Sigur
- [x] Integration com Infinity Electronics
- [x] Access levels
- [x] Access departments
- [x] Access visitors
- [x] Access positions

### Relatórios
- [x] People counting
- [x] Vehicle counting
- [x] Age & gender analysis
- [x] Unique visitors
- [x] Daily/Weekly/Monthly reports
- [x] Custom filters

### Gerenciamento de Eventos
- [x] Comentários em eventos
- [x] Event Manager (webhooks)
- [x] Email notifications
- [x] Telegram notifications
- [x] Alarm panel
- [x] Event groups

### Infraestrutura
- [x] Multi-tenant
- [x] Failover servers
- [x] Cloud storage (Huawei, Google, Amazon)
- [x] NAS support
- [x] Disk/NAS config
- [x] Tunnel server (acesso remoto)
- [x] Custom branding
- [x] LDAP integration
- [x] Organization hierarchy
- [x] Role-based permissions

### Mapas
- [x] Google Maps integration
- [x] Floor plans
- [x] Custom maps
- [x] Map doors
- [x] Map sensors
- [x] Map devices

---

## 🔌 Endpoints Principais

### Backend API (Node.js:3000)
```
POST /api/camera/webrtcServerReady
GET  /api/camera/getWebRTCStreamError/:uuid
POST /api/auth/resetPasswordForm
POST /api/auth/resetPasswordComplete
```

### RTSP-to-WebRTC (Go:4002)
```
POST /stream/start          { rtsp_url, uuid }
POST /stream/stop           { uuid }
POST /stream/receiver/:uuid  (WebRTC)
GET  /stream/codec/:uuid     (codec info)
POST /stream                 (WebRTC genérico)
```

### RTSP Server (aler9:8565)
```
RTSP://host:8565/stream_name
```

### Frontend (Nginx:80)
```
GET /              → React app
GET /api/*         → Proxy para backend:3000
GET /api/socket.io → WebSocket proxy
```

---

## 📅 Timeline do Projeto

| Período | Fase | Features |
|---------|------|----------|
| **Dez 2020** | Fundação | User, Account, Camera, Group, Layout, Socket |
| **Jan-Mar 2021** | Core | Geolocation, Provider, CameraInfo, Admin |
| **Abr-Jun 2021** | Permissions | Role, CameraConf, User_CameraConf, VideoConvert |
| **Set-Out 2021** | Storage | Storage, Analytics |
| **Jan-Mar 2022** | Settings | GeneralSettings, RecordingSchedule, Livestream |
| **Jul-Set 2022** | Events | Event, Analytics settings, Camera conf |
| **Out-Dez 2022** | Advanced | Stream configs, Tunnel, Remote servers |
| **Jan-Mar 2023** | Management | Log, Report, Detector schedule, Readers |
| **Mar-Mai 2023** | Access | Access controllers, Object storages, Failover |
| **Jan-Abr 2024** | AI Boom | Custom Analytics, Cloud mode, Organization, Face |
| **Mai-Jul 2024** | AI v2 | Lists, AI tags, OpenAI, Detection rules, Devices |
| **Ago-Dez 2024** | Access v2 | Access control, Sigur/Bolid, Custom models, VideoGuard |
| **Jan-Abr 2025** | Final | Shared layouts, Roadar, License plates, LDAP |

---

## 🔍 Próximos Passos Possíveis

1. **Desofuscar Frontend React**
   - Usar `prettier --write` nos bundles JS
   - Ou usar ferramentas como `deobfuscate.io`
   - Extrair componentes React e rotas

2. **Extrair Schema Completo do MySQL**
   - Ler todas as 250+ migrações
   - Gerar diagrama ER completo
   - Entender relacionamentos entre tabelas

3. **Analisar Container AI**
   - Extrair imagem `vcloudaiorg/vcloudai-vms-ai:latest`
   - Ver código Python do serviço de IA
   - Entender pipelines de detecção

4. **Analisar Container VA**
   - Extrair imagem `vcloudaiorg/vcloudai-vms-motion:latest`
   - Ver lógica de detecção de movimento

5. **Montar Ambiente de Desenvolvimento**
   - Instalar dependências (`npm install`)
   - Configurar MySQL local
   - Rodar migrações (`sequelize db:migrate`)
   - Iniciar backend (`node src/index.js` ou `dist/index.js`)

6. **Recriar Código Frontend**
   - Usar bundles minificados como base
   - Recriar componentes React
   - Reconstruir rotas e estado

---

*Índice gerado em 11 de Abril de 2026*
