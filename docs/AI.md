# 🤖 Sistema de Analytics e IA - CluebaseVMS

## Visão Geral

O CluebaseVMS possui um **ecossistema completo de Inteligência Artificial** para análise de vídeo em tempo real, com suporte a múltiplos provedores de analytics, modelos customizados YOLO/TensorFlow, e integrações com serviços externos.

---

## 🧠 Arquitetura de IA

### Serviços de Analytics

```
┌─────────────────────────────────────────────────────────────┐
│                    CLUEBASE VMS                              │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │   Backend    │───▶│  AI Service  │    │  VA Service   │  │
│  │  (Node.js)   │    │  (Port 9001) │    │ (Motion:4646) │  │
│  └──────────────┘    └──────────────┘    └───────────────┘  │
│         │                    │                    │          │
│         ▼                    ▼                    ▼          │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │   MySQL DB   │    │ Custom Models│    │ RTSP Streams  │  │
│  │  (Analytics) │    │ (YOLO/TF)    │    │   (WebRTC)    │  │
│  └──────────────┘    └──────────────┘    └───────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          External AI Providers (Optional)             │   │
│  │  VCA (Incoresoft) | Luna | Roadar | Ntech | Ollama   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Tipos de Analytics Suportados

### 1. **Analytics Embutidos (Built-in)**

| Tipo | Detecção | Descrição |
|------|----------|-----------|
| **Object in Zone** | person, car, bicycle, bus, truck, airplane, boat, case, backpack, handbag, +40 objetos | Detecção de objetos dentro de zonas poligonais definidas |
| **Motion** | motion | Detecção de movimento básica |
| **Face** | face | Reconhecimento facial com watchlists |
| **LPR/ALPR** | lpr | Reconhecimento de placas de veículos |
| **Crowd** | crowd | Densidade de multidão |
| **Smoke & Fire** | smoke, fire | Detecção de fumaça e incêndio |
| **PPE** | hard_hat, no_hard_hat, safety_vest, no_safety_vest | Equipamentos de proteção individual |
| **Traffic** | person, car, motorcycle, bus, truck | Contagem de tráfego |
| **Biker (w/o Helmet)** | w/o_helmet | Detecção de motociclistas sem capacete |
| **Smart Tracking** | smart_tracking | Rastreamento inteligente de objetos |
| **Visual Assistant** | visual_assistant | Assistente visual |
| **Sabotage** | defocus, flash, smear, scene_change, blackout | Detecção de sabotagem de câmera |
| **Connection** | connection | Status de conexão |
| **Access Control** | access_control | Eventos de controle de acesso |

### 2. **Edge AI** (processamento na câmera)

| Tipo | Descrição |
|------|-----------|
| motion | Detecção de movimento |
| face_detection | Detecção facial |
| human_vehicle | Detecção humano/veículo |
| perimeter_intrusion | Intrusão de perímetro |
| line_crossing | Cruzamento de linha |
| stationary_object | Objeto estacionário |
| cross_counting | Contagem de cruzamentos |
| crowd_density | Densidade de multidão |
| queue_length | Tamanho de fila |
| license_plate | Placa de licença |
| intrusion | Intrusão |
| region_exiting | Saída de região |
| video_tampering | Tamper de vídeo |
| sound | Detecção de som |
| rare_sound | Som incomum |
| region_entrance | Entrada de região |

### 3. **Custom Analytics** (Modelos IA Customizados)

O sistema permite criar modelos de IA customizados baseados em **YOLO** ou **TensorFlow**:

| Tipo | Classes Pré-configuradas |
|------|-------------------------|
| **SMOKE_AND_FIRE** | smoke, fire |
| **BIKER** | WO_Helmet, W_Helmet, biker |
| **PPE** | No_Hard_Hat, Hard_Hat, NO_Safety_Vest, Safety_Vest |
| **TRAFFIC** | person, car, motorcycle, bus, truck |
| **OBJECT** | person, car, motorcycle, bus, truck |
| **CUSTOM** | Classes definidas pelo usuário |

---

## 🔧 Configuração de Analytics por Câmera

Cada câmera (`CameraConf`) possui configurações específicas para cada tipo de analytics:

### Object in Zone
```javascript
{
  isObjectInZoneEnabled: true,
  objectInZoneFPS: 5,                    // Frames por segundo (1-25)
  objectInZonePolygon: [...],            // Polígono da zona (coordenadas)
  objectInZoneTypes: ['person', 'car'],  // Tipos de objetos a detectar
  objectInZoneTrigger: 0,                // Gatilho (0 = entrada)
  objectInZoneDwellTime: 5,              // Tempo de permanência (1-3600s)
  objectInZoneObjectCounter: 1,          // Contador de objetos (1-50)
  isObjectInZonePolygonVisible: false,   // Mostrar polígono na UI
  isObjectInZoneAlarmSendEnabled: false, // Enviar alarme
  isObjectInZoneUseGPU: false,           // Usar GPU para inferência
  isObjectInZoneDecodeGPU: false,        // Usar GPU para decode
  objectInZoneModel: 'Quality',          // Performance | Quality | Head Recognition
  vcaObjectInZoneEventManagerID: uuid,   // ID do gerenciador de eventos
  vcaObjectInZoneAnalyticsID: int        // ID do serviço de analytics
}
```

### Face Recognition
```javascript
{
  isFREnabled: true,
  frSensitivity: 70,                // Sensibilidade (1-100)
  frViewZone: false,                // Mostrar zona
  frPolygon: [...],                 // Polígono da zona
  isFRAlarmSendEnabled: false,      // Enviar alarme
  frFrameFrequency: 2,              // Frequência de frames (1-5)
  frDetectionDelay: 4,              // Delay de detecção (1-10)
  frScheduleId: uuid,               // Agendamento
  minFRFaceHeight: 20,              // Altura mínima do rosto (20-600px)
  maxFRFaceHeight: 600              // Altura máxima do rosto (20-600px)
}
```

### LPR (License Plate Recognition)
```javascript
{
  isLprEnabled: true,
  lprFPS: 25,                        // Frames por segundo (1-25)
  lprFramesToDetect: 60,             // Frames para detectar (1-100)
  minPlateHeight: 15,                // Altura mínima da placa (px)
  minPlateWidth: 60,                 // Largura mínima da placa (px)
  isSaveVehicleWithoutLicensePlate: false,  // Salvar veículo sem placa
  isBlurLicensePlate: false,         // Borrar placas (privacidade)
  lprPolygon: [...],                 // Polígono da zona
  isLprPolygonVisible: false,        // Mostrar polígono
  isLprAlarmSendEnabled: false,      // Enviar alarme
  isLprUseGPU: false,                // Usar GPU para inferência
  isLprDecodeGPU: false,             // Usar GPU para decode
  vcaLprEventManagerID: uuid,        // ID do gerenciador de eventos
  vcaLprAnalyticsID: int             // ID do serviço de analytics
}
```

---

## 🎯 Custom Analytics (Modelos IA Customizados)

### Modelo CustomAnalytics

Permite configurar detecção IA customizada por câmera:

```javascript
{
  cameraInfoId: uuid,          // ID da câmera
  name: 'Minha Detecção',
  type: 'CUSTOM',              // SMOKE_AND_FIRE | LPR | FACE | OBJECT | PPE | TRAFFIC | HEATMAP | POSE | CUSTOM
  customModelId: uuid,         // Referência ao modelo customizado
  isEnabled: true,
  showPolygon: false,
  confidence: 0.8,             // Threshold de confiança (0-1)
  fps: 5,                      // FPS de análise (0-50)
  decodeWithGpu: false,        // Decode com GPU
  isHighQuality: false,        // Modo alta qualidade
  classes: [                   // Classes a detectar
    { class: 'person', enabled: true },
    { class: 'car', enabled: true }
  ],
  polygon: [...],              // Polígono principal
  extraPolygon: [...],         // Polígono extra
  extraConf: {...},            // Configuração extra
  detectionDelay: 300,         // Delay de detecção (1-300s)
  AtoB: true,                  // Contagem A→B
  BtoA: true,                  // Contagem B→A
  sendToAlarmPanel: true,      // Enviar para painel de alarme
  detectAllFaces: false,       // Detectar todos os rostos
  minFace: 70,                 // Tamanho mínimo do rosto (px)
  maxFace: 140,                // Tamanho máximo do rosto (px)
  logic: 'DETECTION',          // DETECTION | COUNT
  minPlate: 10                 // Tamanho mínimo da placa (px)
}
```

### Modelo CustomModel

Define modelos de IA treinados pelo usuário:

```javascript
{
  name: 'Meu Modelo YOLO',
  type: 'CUSTOM_1',          // CUSTOM_1 a CUSTOM_5
  library: 'YOLO',           // YOLO | TENSORFLOW
  customConfig: {
    classes: [
      { name: 'objeto1', enabled: true },
      { name: 'objeto2', enabled: true }
    ]
    // ... configuração específica do modelo
  },
  reportDetectionTypes: ['objeto1', 'objeto2']
}
```

**Diretórios de armazenamento:**
- `/static/models` - Modelos AI customizados
- `/static/customAIModels` - Modelos customizados (produção)
- `/static/customAIStorage` - Storage de dados customizados

---

## 🔌 Integrações com Provedores Externos de IA

### Provedores Suportados

| Provedor | Variável .env | Tipo | Descrição |
|----------|---------------|------|-----------|
| **YOLO** | `DISABLE_YOLO_OPT` | Built-in | Detecção de objetos YOLO (modelo padrão) |
| **VCA (Incoresoft)** | `DISABLE_VCA_OPT` | Cloud API | Analytics em nuvem: Object, Crowd, Face, LPR, Gun, Traffic, Smart Tracking |
| **Luna AI** | `DISABLE_LUNA_OPT` | Cloud API | Analytics Luna |
| **Ollama/LLaVA** | `DISABLE_LLAVA_OPT` | Local | IA local com modelo LLaVA via Ollama (porta 11434) |
| **Roadar** | `DISABLE_ROADAR_OPT` | Local | Analytics Roadar (porta 8095) |
| **Ntech** | `DISABLE_NTECH_OPT` | Cloud/Local | Analytics Ntech |
| **Bolid** | `DISABLE_BLD_OPT` | Hardware | Integração com controladores Bolid |
| **Sigur** | `DISABLE_SGR_OPT` | Hardware | Integração com controladores Sigur |
| **Infinity Electronics** | `DISABLE_INF_OPT` | Hardware | Integração com controladores Infinity |

### Configuração de Serviços de Analytics (Modelo `Analytics`)

Serviços de analytics externos são registrados com:

```javascript
{
  serviceName: 'VCA',    // Nome do serviço
  apiKey: 'abc123...'    // Chave de API
}
```

### URLs de Serviços IA (config.js)

```javascript
{
  baseCustomAnalyticsServerUrl: 'http://MACHINE_HOST:9001/api',
  baseRoadarAnalyticsServerUrl: 'http://MACHINE_HOST:8095/api',
  ollamaPort: 11434,
  gptProxy: {
    accessKey: 'efg-GPT-6245gsl_$@flk',
    address: 'https://link.vcloud.ai:4040'
  }
}
```

### OpenAI/LLM Integration

O sistema possui integração com OpenAI (via proxy):

```javascript
// Migracao 20240610135952
GeneralSettings.openaiApiKey: string  // Chave API OpenAI
```

---

## 🎥 Pipeline de Vídeo com IA

### Fluxo Completo

```
1. RTSP Stream da Câmera
        │
        ▼
2. RTSP Server (aler9/rtsp-simple-server:8565)
        │
        ▼
3. VA Service (Motion Detection:4646)
        │
        ▼
4. AI Service (Port 9001) ──┬── YOLO Local
                             ├── Custom Models (YOLO/TensorFlow)
                             ├── Ollama/LLaVA (Port 11434)
                             └── Roadar (Port 8095)
        │
        ▼
5. VCA Cloud API (Opcional)
        │
        ▼
6. Eventos salvos no MySQL
        │
        ▼
7. Backend API (Node.js:3000) ──┬── WebSocket (Socket.io:4444)
                                 ├── Event Manager (HTTP callbacks)
                                 └── Notificações (Email, Telegram)
        │
        ▼
8. Frontend React (Nginx:80) ───┬── Live View (WebRTC)
                                 ├── Events Report
                                 └── Maps/Floor Plans
```

---

## 📡 Event Manager

O sistema possui um **EventManager** para encaminhar eventos para sistemas externos:

```javascript
{
  userId: uuid,
  url: 'http://exemplo.com/webhook',
  method: 'POST',              // GET | POST | ISAPI
  sendEventInfo: true,
  cameras: [...],              // Câmeras para monitorar
  outputCameras: [...],        // Câmeras de saída (alarmes)
  types: ['lpr', 'face', ...], // Tipos de eventos
  resetDelay: 2                // Delay de reset (1-300s)
}
```

---

## 🗄️ Estrutura do Banco de Dados (Tabelas de IA)

### Tabela `Analytics`
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | UUID | ID único |
| serviceName | STRING | Nome do serviço (VCA, Luna, etc) |
| apiKey | STRING | Chave de API |

### Tabela `CustomAnalytics`
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | UUID | ID único |
| cameraInfoId | UUID | Referência à câmera |
| name | TEXT | Nome da configuração |
| type | ENUM | Tipo de analytics |
| customModelId | UUID | Modelo customizado |
| isEnabled | BOOLEAN | Ativado/desativado |
| confidence | FLOAT | Threshold (0-1) |
| fps | INTEGER | FPS de análise |
| decodeWithGpu | BOOLEAN | Usar GPU para decode |
| isHighQuality | BOOLEAN | Modo alta qualidade |
| classes | JSON | Classes a detectar |
| polygon | JSON | Polígono da zona |
| extraPolygon | JSON | Polígono extra |
| extraConf | JSON | Config extra |
| detectionDelay | INTEGER | Delay (1-300s) |
| AtoB / BtoA | BOOLEAN | Contagem direcional |
| sendToAlarmPanel | BOOLEAN | Enviar alarme |
| detectAllFaces | BOOLEAN | Detectar todos os rostos |
| minFace / maxFace | INTEGER | Tamanho do rosto |
| logic | ENUM | DETECTION | COUNT |
| minPlate | INTEGER | Tamanho mínimo da placa |

### Tabela `CustomModel`
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | UUID | ID único |
| name | STRING | Nome do modelo |
| type | ENUM | CUSTOM_1 a CUSTOM_5 |
| library | ENUM | YOLO | TENSORFLOW |
| customConfig | JSON | Configuração do modelo |
| reportDetectionTypes | JSON | Tipos para relatório |

### Tabela `DetectionRule`
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | UUID | ID único |
| name | STRING | Nome da regra |
| prompt | TEXT | Prompt (para LLM) |
| logic | ENUM | YES | NO | COUNT |

### Tabela `List` (Watchlists)
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | UUID | ID único |
| type | ENUM | FACE | LPR |
| name | STRING | Nome da lista |
| organizationId | UUID | Organização |

### Tabela `Face`
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | UUID | ID único |
| name | STRING | Nome da pessoa |
| comment | STRING | Comentário |
| images | JSON | Array de imagens |
| listId | UUID | Lista pertencente |

### Tabela `LicensePlate`
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | UUID | ID único |
| licensePlate | STRING | Número da placa |
| comment | STRING | Comentário |
| listId | UUID | Lista pertencente |

### Tabela `Event` (Campos de IA)
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| detectionType | STRING | Tipo de detecção |
| confidence | STRING | Confiança da detecção |
| name | STRING | Nome (face recognition) |
| serviceName | STRING | Serviço que detectou |
| plateNumber | STRING | Placa detectada |
| peopleCount | INTEGER | Contagem de pessoas |
| list | STRING | Lista (watchlist) |
| age | STRING | Idade estimada |
| gender | STRING | Gênero estimado |
| mask | STRING | Uso de máscara |
| hair | STRING | Cor do cabelo |
| bag | STRING | Tipo de bolsa |
| topColor / bottomColor | STRING | Cor da roupa |
| make | STRING | Marca (veículo) |
| metadata | JSON | Metadata completa da detecção |
| entrance / exit | BOOLEAN | Direção do movimento |
| detectionName | STRING | Nome da detecção |
| direction | JSON | Dados de direção (counting) |

---

## 🖥️ RTSP-to-WebRTC (Streaming Go)

O serviço de streaming em Go converte RTSP para WebRTC:

### Configuração (`webrtc-config.json`)
```json
{
  "server": {
    "http_port": ":4002",
    "ice_servers": [
      "stun:stun.l.google.com:19302",
      "stun:stun4.l.google.com:19302"
    ]
  }
}
```

### APIs HTTP
| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/stream/start` | POST | Iniciar stream RTSP |
| `/stream/stop` | POST | Parar stream |
| `/stream/receiver/:uuid` | POST | WebRTC receiver |
| `/stream/codec/:uuid` | GET | Info do codec |
| `/stream` | POST | WebRTC genérico |

### Codecs Suportados
- **Vídeo**: H264 apenas
- **Áudio**: PCM alaw, PCM mulaw, OPUS

### Bibliotecas Go
```go
github.com/deepch/vdk          // Parsing de vídeo
github.com/deepch/vdk/codec/h264parser  // Parser H264
github.com/pion/webrtc/v3      // WebRTC
github.com/gin-gonic/gin       // HTTP framework
github.com/joho/godotenv       // .env loading
```

---

## ⚙️ Configuração .env (Toggle de IA)

```bash
# Portas de serviços IA
AI_PORT=9001
ROADAR_PORT=8095
OLLAMA_PORT=11434

# Toggles (0 = habilitado, 1 = desabilitado)
DISABLE_ONLINE_LICENSE_OPT=0   # License server
DISABLE_YOLO_OPT=0             # YOLO Object Detection
DISABLE_LLAVA_OPT=0            # Ollama/LLaVA
DISABLE_VCA_OPT=0              # Incoresoft VCA
DISABLE_LUNA_OPT=1             # Luna AI (desabilitado)
DISABLE_BLD_OPT=1              # Bolid (desabilitado)
DISABLE_SGR_OPT=1              # Sigur (desabilitado)
DISABLE_INF_OPT=1              # Infinity Electronics (desabilitado)
DISABLE_ROADAR_OPT=1           # Roadar (desabilitado)
DISABLE_NTECH_OPT=0            # Ntech
```

---

## 📅 Cronologia de Desenvolvimento de IA

| Data | Feature | Descrição |
|------|---------|-----------|
| Set 2022 | Analytics Settings | Configurações básicas de analytics |
| Set 2022 | Camera Conf Analytics | Configuração de analytics por câmera |
| Set 2022 | Object in Zone | Detecção de objetos em zonas |
| Set 2022 | Detection Delay | Delay entre detecções |
| Ago 2022 | Face Recognition (Event) | Colunas de face em eventos |
| Ago 2023 | Face Analytics Conf | Config completa de face recognition |
| Ago 2023 | LPR Analytics Conf | Config de reconhecimento de placas |
| Set 2023 | Crowd Analytics | Detecção de multidão |
| Set 2023 | Smoke Analytics | Detecção de fumaça/fogo |
| Set 2023 | Object Analytics | Detecção de objetos |
| Fev 2024 | Custom Analytics | Modelos IA customizados |
| Fev 2024 | Custom AI Detect Delay | Delay customizável |
| Abr 2024 | Edit Custom AI Types | Novos tipos de IA |
| Mai 2024 | Face Recognition | Sistema completo de FR |
| Mai 2024 | Lists & Faces | Watchlists de rostos |
| Jun 2024 | AI Tags | Tags de IA |
| Jun 2024 | OpenAI API Key | Integração OpenAI |
| Jun 2024 | Update Custom Analytics | Polygons extras, A→B counting |
| Jun 2024 | AI Permissions | Permissões de IA |
| Jul 2024 | Motion Detection | Detecção de movimento |
| Jul 2024 | Detection Rules | Regras de detecção customizadas |
| Jun 2024 | Face Detection Alarm | Alarme de detecção facial |
| Nov 2024 | Face VA Attributes | Atributos visuais de face |
| Mar 2025 | AI Extra Conf | Configurações extras de IA |

---

## 🔍 Recursos Avançados

### 1. **GPU Acceleration**
O sistema suporta aceleração por GPU:
- `decodeWithGpu: true` - Decode de vídeo com GPU
- `isHighQuality: true` - Modo de alta qualidade
- `isObjectInZoneUseGPU: true` - Inferência com GPU
- `isObjectInZoneDecodeGPU: true` - Decode com GPU

### 2. **Polygon Zones**
Múltiplos polígonos configuráveis por câmera:
- `polygon` - Zona principal
- `extraPolygon` - Zonas adicionais
- `showPolygon` - Visibilidade na UI

### 3. **Directional Counting (A→B / B→A)**
Contagem direcional de objetos entre zonas.

### 4. **Face Recognition com Watchlists**
- Listas de pessoas conhecidas/desconhecidas
- Organização por listas
- Múltiplas imagens por pessoa
- Sensibilidade configurável

### 5. **LPR com Watchlists**
- Listas brancas/negras de placas
- Blur automático para privacidade
- Detecção de veículos sem placa

### 6. **AI com LLM (Ollama/LLaVA + OpenAI)**
- Integração com LLaVA via Ollama (local, porta 11434)
- Proxy OpenAI (GPT) via `https://link.vcloud.ai:4040`
- DetectionRules com prompts para LLM

### 7. **Event Groups**
Eventos podem ser agrupados por:
- `groupId` - ID do grupo
- `groupCreationTime` - Timestamp de criação
- `groupType` - Tipo do grupo

### 8. **Custom Models (5 slots)**
Suporte a 5 modelos customizados simultâneos:
- `CUSTOM_1` a `CUSTOM_5`
- Bibliotecas: YOLO ou TensorFlow
- Configuração flexível via JSON

---

## 📦 Containers de IA

| Container | Imagem | Porta | Descrição |
|-----------|--------|-------|-----------|
| `ai` | vcloudaiorg/vcloudai-vms-ai:latest | 9001 | Serviço principal de IA |
| `va` | vcloudaiorg/vcloudai-vms-motion:latest | 4646 | Detecção de movimento |

### Volumes do Container AI
```yaml
volumes:
  - ./static/customAIModels:/app/Models/customAIModels
  - ./static/customAIStorage:/app/Storage
```

---

*Documento gerado em 11 de Abril de 2026*
