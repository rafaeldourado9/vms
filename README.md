# CluebaseVMS - Engenharia Reversa - Resumo Completo

## 📋 Visão Geral

**CluebaseVMS** (também conhecido como **vCloud.ai VMS**) é um **Video Management System** enterprise desenvolvido pela **vCloud AI Org**. É uma aplicação full-stack para gestão de videovigilância com suporte a IA, streaming WebRTC, e controle de acesso.

---

## 🏗️ Arquitetura

### Stack Tecnológico
- **Backend API**: Node.js + Express + Sequelize ORM (MySQL)
- **Frontend**: React (compilado/minificado) servido via Nginx
- **Streaming RTSP→WebRTC**: Go (baseado em deepch/RTSPtoWebRTC)
- **Banco de Dados**: MySQL 8.0.32
- **Proxy Reverso**: Nginx
- **Orquestração**: Docker Compose

### Containers Docker
| Container | Imagem | Descrição |
|-----------|--------|-----------|
| `backend` | vcloudaiorg/vcloudai-vms-back-end-public:test--scan | API Node.js principal |
| `frontend` | vcloudaiorg/vcloudai-vms-front-end-public:test--scan | React app via Nginx |
| `database` | mysql:8.0.32 | Banco MySQL |
| `ai` | vcloudaiorg/vcloudai-vms-ai:latest | Serviços de IA customizada |
| `va` | vcloudaiorg/vcloudai-vms-motion:latest | Detecção de movimento |
| `livestream-server` | vcloudaiorg/vcloudai-vms-stream:latest | Streaming ao vivo |
| `rtsp-server` | aler9/rtsp-simple-server:v0.20.3 | Servidor RTSP |
| `proxy` | nginx:latest | Proxy reverso |
| `migration` | (mesma imagem do backend) | Migrações do banco |

---

## 📂 Estrutura do Código Fonte

### Backend (`/backend/src/`)

#### Configuração
- **`config/config.js`**: Configuração central - porta, DB, URLs, toggles de features AI
- **`config/sequelize.js`**: Configuração do ORM Sequelize com MySQL (pool: 0-300 conexões)

#### Constantes (`constants/index.js` - 12.800 linhas)
Define:
- **50+ objetos detectáveis**: person, car, bicycle, airplane, animals, frutas, utensílios
- **Tipos de eventos**: LPR, Face, Motion, Sabotage, PPE, Crowd, Smoke/Fire, Traffic, etc.
- **Tipos de analíticas**: Object in Zone, Visual Assistant, Smart Tracking, Edge AI
- **Integrações AI**: YOLO, VCA (Incoresoft), Luna, Roadar, Ntech, Ollama/LLaVA
- **Controle de acesso**: Sigur, Bolid, Infinity Electronics
- **Caminhos de diretórios**, paleta de cores, cenários de sabotagem

#### Modelos Sequelize (51 modelos)
| Modelo | Descrição |
|--------|-----------|
| **User** | Usuários com auth (bcrypt, JWT), filtros de eventos, Telegram, LDAP |
| **Account** | Conta/tenant (multi-tenant) |
| **Camera** | Câmeras com UUID, tipo (CREATED/SHARED), status livestream/archive |
| **CameraInfo** | Informações técnicas (RTSP URL, etc.) |
| **CameraConf** | Configurações por câmera |
| **Event** | Eventos de detecção (motion, face, LPR, PPE) com metadata JSON |
| **Socket/Layout/Screen** | Visualização em grade de câmeras |
| **Analytics** | Serviços de analítica (serviceName, apiKey) |
| **Storage** | Armazenamento (local, Huawei, Amazon, Google, NAS) |
| **Face** | Reconhecimento facial |
| **LicensePlate** | Reconhecimento de placas (LPR) |
| **List** | Listas (watchlists para face/LPR) |
| **DetectionRule** | Regras de detecção |
| **Device** | Dispositivos (speakers) |
| **Organization** | Organizações (hierarquia) |
| **AccessController/Level/Department/Visitor** | Controle de acesso |
| **CustomAnalytics/CustomModel** | IA customizada |
| **VideoGuard/VideoguardEvent** | Eventos VideoGuard |
| **Map/FloorPlan/MapDoor/MapSensor** | Mapas e plantas baixas |
| **RecordingSchedule** | Agendamentos de gravação |
| **FailoverServer** | Servidores de failover |
| **Role** | Papéis/permissões |
| **Log** | Logs do sistema |

#### RTSP-to-WebRTC (`rtsp-to-webrtc/` - 50 arquivos)
Serviço **Go** para conversão RTSP → WebRTC:
- **`main.go`**: Entry point, recebe 7 argumentos CLI
- **`config.go`**: Structs ConfigST, ServerST, StreamST
- **`stream.go`**: RTSP worker loop, conecta RTSP, lê packets, faz cast para viewers
- **`http.go`**: API HTTP com Gin framework
  - `POST /stream/start` - Inicia stream
  - `POST /stream/stop` - Para stream
  - `POST /stream/receiver/:uuid` - Receiver
  - `GET /stream/codec/:uuid` - Codec info

**Dependências Go**:
- `github.com/deepch/vdk` - Parsing de vídeo (H264, PCM alaw/mulaw, OPUS)
- `github.com/gin-gonic/gin` - Framework HTTP
- `github.com/pion/webrtc/v3` - WebRTC
- `github.com/joho/godotenv` - Loading de .env

**Codecs suportados**:
- Vídeo: **H264** apenas
- Áudio: **PCM alaw, PCM mulaw, OPUS**

#### Migrações (`db/migrations/` - 250+ arquivos)
De **Dez 2020 a Abr 2025**, cobrindo:
- 2020-12: User, Account, Camera, Group, Layout, Socket
- 2021: Geolocation, Provider, Role, Storage, Analytics
- 2022: GeneralSettings, RecordingSchedule, Livestream, Event
- 2023: Log, Report, Readers, Access Controller, Failover
- 2024: Organization, Face Recognition, Lists, AI Tags, Detection Rules, Devices, Access Control
- 2025: Shared Layouts, Roadar Analytics, License Plates, LDAP, Defocus/Sabotage

### Frontend (`/frontend/usr/share/nginx/html/`)
React compilado (minificado):
- `main.73c31e224e3d9a419713.js` - Bundle principal
- `vendors~main.73c31e224e3d9a419713.js` - Vendors
- `main.73c31e22.css` / `1.73c31e22.css` - Styles
- `manifest.json` - Asset manifest
- `index.html` - Entry point com Google Maps API key

### Arquivos de Configuração Externa
- **`.env`**: Variáveis de ambiente (MySQL creds, hosts, portas, toggles)
- **`nginx.conf`**: Configuração do proxy Nginx
- **`docker-compose-ai.yml`**: Orquestração completa dos containers
- **`rtsp-simple-server.yml`**: Configuração do servidor RTSP

---

## 🔐 Credenciais e Segurança

### MySQL (do .env)
```
MYSQL_USER=root
MYSQL_DB=vcloud
MYSQL_PASSWORD=DGkj^dg_DF++334-343-__3453^5EFg_ESF_D3++4111^WF_SFs+gb-dg
SECRET_WORD=verysecret
```

### Google Maps API Key
```
AIzaSyCdpQdtnvNz8zO0OL-lk2TkR1YvJTVH7c
```

### RTSP Auth Interna
```
INTERNAL_RTSP_AUTH=vms_internal
```

### Autenticação de Usuário
- **bcrypt** para hash de senhas
- **JWT** para tokens de sessão
- **LDAP** support (opcional)
- **Telegram** para notificações

---

## 🤖 Integrações de IA

### Serviços habilitáveis/desabilitáveis via .env
| Variável | Serviço |
|----------|---------|
| `DISABLE_YOLO_OPT` | YOLO (detecção de objetos) |
| `DISABLE_VCA_OPT` | VCA - Incoresoft |
| `DISABLE_LUNA_OPT` | Luna AI |
| `DISABLE_LLAVA_OPT` | Ollama/LLaVA |
| `DISABLE_ROADAR_OPT` | Roadar Analytics |
| `DISABLE_NTECH_OPT` | Ntech |
| `DISABLE_BLD_OPT` | Bolid |
| `DISABLE_SGR_OPT` | Sigur |
| `DISABLE_INF_OPT` | Infinity Electronics |
| `DISABLE_ONLINE_LICENSE_OPT` | License server online |

### Tipos de Analytics
- **Object in Zone**: Detecção de objetos em zonas definidas
- **Motion**: Detecção de movimento
- **Face**: Reconhecimento facial
- **LPR/ALPR**: Reconhecimento de placas
- **PPE**: Equipamentos de proteção (capacete, colete)
- **Crowd**: Densidade de multidão
- **Smoke/Fire**: Detecção de fumaça e fogo
- **Traffic**: Contagem de tráfego
- **Smart Tracking**: Rastreamento inteligente
- **Edge AI**: Detecções na borda (camera-side)
- **Sabotage**: Defocus, flash, smear, scene change

---

## 🌐 Endpoints e Portas

| Serviço | Porta | Descrição |
|---------|-------|-----------|
| Nginx (Frontend) | 80 | Interface web |
| Backend API | 3000 | API REST + Socket.io |
| MySQL | 3307 (externa) | Banco de dados |
| RTSP Server | 8565 | Servidor RTSP |
| Livestream | 4001 | Streaming ao vivo |
| AI Service | 9001 | IA customizada |
| Roadar Analytics | 8095 | Analytics Roadar |
| VA (Motion) | 4646 | Detecção de movimento |
| WebRTC (Go) | 4002 | Streaming WebRTC |

---

## 📡 APIs RTSP-to-WebRTC

```
POST /stream/start    - Iniciar stream RTSP
POST /stream/stop     - Parar stream
POST /stream/receiver/:uuid - Configurar receiver
GET  /stream/codec/:uuid    - Obter info do codec
```

---

## 🗂️ Diretórios Principais (no container backend)

```
/static/
├── cloudTemp/        # Temp para archives
├── demo/             # Vídeos de demonstração
├── faces/            # Fotos para reconhecimento facial
├── visitors/         # Fotos de visitantes
├── maps/             # Mapas e plantas baixas
├── licenses/         # Licenças
├── logs/             # Logs da aplicação
├── dbLogs/           # Logs do banco
├── models/           # Modelos AI customizados
├── logo/             # Logos da aplicação
└── customAIModels/   # Modelos AI do usuário

/temp/
├── snapshots/        # Snapshots temporários
├── tempVideoGuardFiles/
└── uploadedConfiguration/

/branding/
└── icons/, fonts/, config.json
```

---

## 🎯 Funcionalidades Principais

1. **Visualização ao vivo**: Grade de câmeras via WebRTC
2. **Gravação/Archive**: Gravação contínua ou por agendamento
3. **Analytics AI**: Detecção inteligente com múltiplos providers
4. **Reconhecimento Facial**: Face recognition com watchlists
5. **LPR**: Reconhecimento de placas de veículos
6. **Controle de Acesso**: Integration com controladores
7. **Mapas/Plantas Baixas**: Visualização em mapa
8. **Eventos/Alertas**: Sistema completo de eventos com comentários
9. **Relatórios**: Relatórios diários/semanais/mensais
10. **Multi-tenant**: Suporte a múltiplas contas/organizações
11. **Failover**: Servidores de failover para redundância
12. **Livestream**: Streaming ao vivo (RTSP broadcast)
13. **Tunnel**: Servidor tunnel para acesso remoto
14. **Branding**: Customização da marca (logo, cores, fonts)

---

## 📅 Cronologia do Desenvolvimento

- **Início**: Dezembro 2020
- **Última migração**: Abril 2025
- **Versão atual**: Produção (test--scan)

---

## 🔍 Observações Importantes

1. **Código legível**: Modelos Sequelize, config, constants estão em código fonte aberto
2. **Frontend minificado**: Bundle React compilado (webpack) - requer desofuscacao para leitura completa
3. **Dist bundle**: O `/dist/index.js` do backend também é minificado (webpack)
4. **Imagens Docker**: As imagens completas estão em `all_images.tar`
5. **MySQL**: Banco completo com 250+ migrações
6. **Sistema multi-tenant**: Suporte a múltiplas contas/organizações
7. **Docker mode**: Usa `win32_virt` / `darwin_virt` para Docker no Windows/Mac

---

## 📦 Arquivos Extraídos

- **Backend**: `C:\Users\Rafael Dourado\Desktop\cluebase-src\backend\`
- **Frontend**: `C:\Users\Rafael Dourado\Desktop\cluebase-src\frontend\`
- **Frontend JS/CSS**: `C:\Users\Rafael Dourado\Desktop\cluebase-src\frontend-js\`

---

*Documento gerado em 11 de Abril de 2026*
