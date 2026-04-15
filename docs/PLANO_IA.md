# 🤖 Plano: Extrair Serviços de IA do CluebaseVMS

## Objetivo

Extrair os serviços de IA do CluebaseVMS para integrar no VMS em nuvem que você está desenvolvendo, com analytics como plugins independentes.

## O Que Sabemos Até Agora

### Serviços de IA do Cluebase (da análise do código fonte)

```
Container AI (vcloudaiorg/vcloudai-vms-ai:latest)
├── Porta: 9001
├── Base: Python (provavelmente)
├── Volumes:
│   - ./static/customAIModels:/app/Models/customAIModels
│   - ./static/customAIStorage:/app/Storage
├── Funcionalidades:
│   ├── YOLO Object Detection
│   ├── Custom Models (YOLO/TensorFlow)
│   ├── Face Recognition
│   ├── LPR (License Plate Recognition)
│   ├── Crowd Detection
│   ├── Smoke & Fire Detection
│   ├── PPE Detection
│   └── Traffic Counting
│
└── Config via MySQL:
    - host: 127.0.0.1
    - port: 3306 (via EXTERNAL_MYSQL_PORT)
    - db: vcloud
    - secret_word: verysecret

Container VA Motion (vcloudaiorg/vcloudai-vms-motion:latest)
├── Porta: 4646
├── Funcionalidade: Detecção de movimento
└── Secret: ${SECRET_WORD}

Container RTSP-to-WebRTC (Go - código fonte DISPONÍVEL)
├── Porta: 4002
├── Código: /backend/src/rtsp-to-webrtc/ (50 arquivos Go)
├── Framework: Pion WebRTC + Gin
└── Codecs: H264, PCM alaw/mulaw, OPUS
```

### Tipos de Analytics Suportados (do código fonte)

1. **object_in_zone** - person, bicycle, car, motorbike, bus, truck, airplane, +50 objetos
2. **motion** - Detecção de movimento
3. **face** - Reconhecimento facial
4. **lpr** - Placas de veículos
5. **crowd** - Densidade de multidão
6. **smoke_and_fire** - Fumaça e fogo
7. **ppe** - EPIs (capacete, colete)
8. **traffic** - Contagem de tráfego
9. **w/o_helmet** - Motociclistas sem capacete
10. **smart_tracking** - Rastreamento inteligente
11. **visual_assistant** - Assistente visual
12. **sabotage** - Defocus, flash, smear, scene_change
13. **edge_ai** - Processamento na câmera

### Configuração de Analytics por Câmera (CameraConf)

```javascript
// Object in Zone
{
  isObjectInZoneEnabled: true,
  objectInZoneFPS: 5,
  objectInZonePolygon: [...],
  objectInZoneTypes: ['person', 'car'],
  objectInZoneModel: 'Quality',  // Performance | Quality | Head Recognition
  isObjectInZoneUseGPU: false,
  isObjectInZoneDecodeGPU: false,
}

// Face Recognition
{
  isFREnabled: true,
  frSensitivity: 70,
  frFrameFrequency: 2,
  frDetectionDelay: 4,
  minFRFaceHeight: 20,
  maxFRFaceHeight: 600,
}

// LPR
{
  isLprEnabled: true,
  lprFPS: 25,
  lprFramesToDetect: 60,
  minPlateHeight: 15,
  minPlateWidth: 60,
  isLprUseGPU: false,
  isLprDecodeGPU: false,
}
```

## 📋 Plano de Ação

### Fase 1: Carregar Imagens Docker (EM ANDAMENTO)
```bash
docker load -i all_images.tar
# Aguardar ~15-30 minutos para 9.5GB
```

### Fase 2: Inspecionar Imagens de IA
```bash
# Verificar imagens carregadas
docker images | grep vcloud

# Inspecionar imagem AI
docker inspect vcloudaiorg/vcloudai-vms-ai:latest
docker inspect vcloudaiorg/vcloudai-vms-motion:latest

# Extrair Dockerfile/histórico
docker history vcloudaiorg/vcloudai-vms-ai:latest --no-trunc
```

### Fase 3: Extrair Código dos Containers
```bash
# Extrair filesystem completo
mkdir -p /tmp/ai-extract /tmp/motion-extract
docker create --name ai-temp vcloudaiorg/vcloudai-vms-ai:latest
docker export ai-temp | tar -x -C /tmp/ai-extract

docker create --name motion-temp vcloudaiorg/vcloudai-vms-motion:latest
docker export motion-temp | tar -x -C /tmp/motion-extract
```

### Fase 4: Analisar Estrutura dos Serviços
- Verificar linguagem (Python? Go? Node.js?)
- Identificar frameworks e dependências
- Mapear endpoints HTTP
- Entender comunicação com MySQL
- Localizar modelos pré-treinados (.pt, .onnx, .pb, etc)

### Fase 5: Recriar como Plugins
```
seu-vms-analytics/
├── yolo-detector/          # Detecção de objetos
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   └── models/
│       └── yolov8n.pt      # Modelo pré-treinado
│
├── face-recognition/       # Reconhecimento facial
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   └── models/
│
├── lpr/                    # Reconhecimento de placas
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
│
├── smoke-fire/             # Detecção fumaça/fogo
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
│
├── crowd-detection/        # Densidade de multidão
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
│
├── ppe-detection/          # EPIs
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
│
└── motion-detector/        # Detecção de movimento
    ├── Dockerfile
    ├── requirements.txt
    └── main.py
```

## 🎯 Arquitetura Alvo (Seu VMS em Nuvem)

```
┌──────────────────────────────────────────────────────────────┐
│                     Seu VMS Cloud                             │
│                                                               │
│  ┌──────────┐    ┌──────────┐    ┌────────────────────────┐  │
│  │  API     │◄──►│   MySQL  │    │   Analytics Plugins    │  │
│  │ (FastAPI)│    │/Postgres │    │                        │  │
│  └──────────┘    └──────────┘    │ ┌──────────────────┐   │  │
│         │                        │ │  YOLO Detector   │   │  │
│         ▼                        │ │  (porta 9001)    │   │  │
│  ┌──────────┐    ┌──────────┐    │ └──────────────────┘   │  │
│  │Frontend  │◄──►│  MediaMTX│    │                        │  │
│  │  (React) │    │  (RTSP)  │◄──►│ ┌──────────────────┐   │  │
│  └──────────┘    └──────────┘    │ │  Face Recognition│   │  │
│                                  │ │  (porta 9002)    │   │  │
│  ┌──────────┐                    │ └──────────────────┘   │  │
│  │  Ollama  │                    │                        │  │
│  │  (LLM)   │◄───────────────────│ ┌──────────────────┐   │  │
│  └──────────┘                    │ │  LPR             │   │  │
│                                  │ │  (porta 9003)    │   │  │
│  ┌──────────┐                    │ └──────────────────┘   │  │
│  │  Qdrant  │                    │                        │  │
│  │  (Vector)│                    │ ┌──────────────────┐   │  │
│  └──────────┘                    │ │  Smoke/Fire      │   │  │
│                                  │ │  (porta 9004)    │   │  │
│                                  │ └──────────────────┘   │  │
│                                  │                        │  │
│                                  │ ┌──────────────────┐   │  │
│                                  │ │  Motion Detector │   │  │
│                                  │ │  (porta 4646)    │   │  │
│                                  │ └──────────────────┘   │  │
│                                  └────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## ✅ Status

- [x] **Análise do código fonte** - Modelos, configurações, constantes
- [x] **Entendimento da arquitetura** - Containers, portas, volumes
- [ ] **Carregar imagens Docker** (em andamento - docker load)
- [ ] **Inspecionar containers AI**
- [ ] **Extrair código dos serviços**
- [ ] **Localizar modelos pré-treinados**
- [ ] **Recriar como plugins independentes**

## 📁 Próximos Passos

1. Aguardar `docker load` completar
2. Inspecionar imagens `vcloudaiorg/vcloudai-vms-ai` e `vcloudaiorg/vcloudai-vms-motion`
3. Extrair filesystem dos containers
4. Analisar código e modelos
5. Recriar como plugins para seu VMS

---

*Plano criado em 11 de Abril de 2026*
