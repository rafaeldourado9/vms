# VMS MVP — Guia de Plugins Analytics

> Para câmeras sem IA embarcada. Roda no `analytics_service`.

---

## Conceito

Qualquer câmera bullet envia stream RTSP → MediaMTX captura → analytics_service
extrai 1 frame/segundo → plugin processa → evento publicado no VMS.

```
Câmera RTSP → MediaMTX → analytics_service
                              ├── intrusion_detection
                              ├── people_count
                              ├── vehicle_count
                              └── lpr (plate recognition)
                                      ↓
                              POST /internal/analytics/ingest/
                                      ↓
                              VmsEvent criado + publicado
```

---

## Interface Base

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import numpy as np

@dataclass
class ROIConfig:
    """Configuração de região de interesse para o plugin."""
    id: str
    name: str
    ia_type: str
    polygon_points: list[list[float]]  # normalizado 0.0–1.0
    config: dict                        # configuração específica do plugin

@dataclass
class FrameMetadata:
    """Metadados do frame sendo processado."""
    camera_id: str
    tenant_id: str
    timestamp: datetime
    stream_url: str

@dataclass
class AnalyticsResult:
    """Resultado de análise de um plugin."""
    plugin: str
    camera_id: str
    tenant_id: str
    roi_id: str
    event_type: str
    payload: dict
    occurred_at: datetime

class AnalyticsPlugin(ABC):
    """Base para todos os plugins de analytics."""

    name: str        # identificador único: "people_count"
    version: str     # semver: "1.0.0"
    roi_type: str    # tipo de ROI que este plugin processa: "human_traffic"

    async def initialize(self, config: dict) -> None:
        """Carrega modelos, aloca recursos. Chamado uma vez no startup."""

    @abstractmethod
    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        """Processa um frame e retorna lista de resultados."""

    async def shutdown(self) -> None:
        """Libera recursos. Chamado no shutdown do serviço."""
```

---

## Plugin: intrusion_detection

**ROI type:** `intrusion`
**Evento:** `analytics.intrusion.detected`
**Modelo:** YOLOv8n (COCO)
**Classes padrão:** person (0)

### Lógica
1. Inferência YOLO no frame completo
2. Filtrar detecções pela(s) classe(s) configurada(s)
3. Para cada ROI ativa, checar se centroide da bbox está dentro do polígono
4. Emitir evento se houver detecção dentro da ROI

### Config da ROI
```json
{
  "classes": [0],          // IDs COCO (padrão: person)
  "min_confidence": 0.5,
  "cooldown_seconds": 30   // não re-emitir dentro deste intervalo
}
```

### Payload do Evento
```json
{
  "roi_id": "uuid",
  "roi_name": "Zona Proibida",
  "detection_count": 2,
  "detections": [
    { "class": "person", "confidence": 0.87, "bbox": [0.1, 0.2, 0.3, 0.4] }
  ],
  "frame_path": "/frames/tenant-1/cam-1/2026-03-30T12:34:56.jpg"
}
```

---

## Plugin: people_count

**ROI type:** `human_traffic`
**Evento:** `analytics.people.count`
**Modelo:** YOLOv8n
**Classe:** person (0)

### Lógica
1. Inferência YOLO
2. Contar pessoas com centroide dentro da ROI
3. Emitir evento se contagem > threshold configurado

### Config da ROI
```json
{
  "emit_threshold": 0,     // emitir quando count > este valor
  "interval_seconds": 60   // frequência mínima de emissão
}
```

### Payload
```json
{
  "roi_id": "uuid",
  "count": 5,
  "detections": [...],
  "interval_start": "2026-03-30T12:34:00Z",
  "interval_end": "2026-03-30T12:35:00Z"
}
```

---

## Plugin: vehicle_count

**ROI type:** `vehicle_traffic`
**Evento:** `analytics.vehicle.count`
**Modelo:** YOLOv8n
**Classes:** car (2), motorcycle (3), bus (5), truck (7)

Mesma lógica de `people_count`, classes diferentes.

---

## Plugin: lpr (License Plate Recognition)

**ROI type:** `lpr`
**Evento:** `analytics.lpr.detected`
**Modelos:** YOLOv8 plate detector + fast-plate-ocr
**Fluxo B:** câmeras sem módulo ANPR

### Lógica
1. YOLOv8 detecta bbox da placa no frame
2. Crop da região da placa
3. fast-plate-ocr extrai texto
4. Normalizar formato (AAA-1234 ou AAA1A23 Mercosul)
5. Dedup Redis (mesmo plate + câmera < TTL = ignorar)
6. Emitir evento

### Config da ROI
```json
{
  "min_plate_confidence": 0.7,
  "min_ocr_confidence": 0.6,
  "dedup_ttl_seconds": 60
}
```

### Payload
```json
{
  "roi_id": "uuid",
  "plate": "ABC1D23",
  "plate_confidence": 0.92,
  "ocr_confidence": 0.88,
  "bbox": [0.1, 0.2, 0.4, 0.35],
  "frame_path": "/frames/tenant-1/cam-1/2026-03-30T12:34:56.jpg"
}
```

---

## Como Criar um Novo Plugin

### 1. Criar o módulo

```
analytics/src/analytics/plugins/
└── meu_plugin/
    ├── __init__.py
    └── plugin.py
```

### 2. Implementar a interface

```python
# analytics/src/analytics/plugins/meu_plugin/plugin.py

import numpy as np
from analytics.core.plugin_base import (
    AnalyticsPlugin, AnalyticsResult, FrameMetadata, ROIConfig
)

class MeuPlugin(AnalyticsPlugin):
    """Descrição do que o plugin faz."""

    name = "meu_plugin"
    version = "1.0.0"
    roi_type = "meu_tipo"

    async def initialize(self, config: dict) -> None:
        """Carrega modelo e recursos."""
        # carregar modelo aqui
        self._modelo = ...

    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        """Processa frame e retorna resultados."""
        resultados = []

        for roi in rois:
            # lógica de detecção
            if self._detectou_algo(frame, roi):
                resultados.append(AnalyticsResult(
                    plugin=self.name,
                    camera_id=metadata.camera_id,
                    tenant_id=metadata.tenant_id,
                    roi_id=roi.id,
                    event_type="analytics.meu_plugin.detected",
                    payload={"detalhes": "..."},
                    occurred_at=metadata.timestamp,
                ))

        return resultados
```

### 3. O plugin é carregado automaticamente
O `PluginLoader` escaneia `plugins/*/plugin.py` no startup.
Nenhuma mudança necessária no orchestrator ou em outros arquivos.

### 4. Criar ROI com o tipo correto
```json
POST /api/v1/analytics/rois
{
  "camera_id": "uuid",
  "ia_type": "meu_tipo",
  "polygon_points": [[...], ...],
  "config": {}
}
```

### 5. Testes obrigatórios
```python
# tests/unit/test_meu_plugin.py
async def test_detecta_quando_objeto_na_roi(): ...
async def test_nao_detecta_quando_fora_da_roi(): ...
async def test_resultado_tem_campos_obrigatorios(): ...
async def test_exception_na_inferencia_nao_propaga(): ...
```

---

## Ordem de Implementação

| # | Plugin | Complexidade | GPU? | Sprint |
|---|--------|-------------|------|--------|
| 1 | intrusion_detection | baixa | não | 7 |
| 2 | people_count | baixa | não | 7 |
| 3 | vehicle_count | baixa | não | 7 |
| 4 | lpr | média | não | 7 |
| 5 | weapon_detection | alta | recomendado | pós-MVP |
| 6 | face_recognition | alta (LGPD) | recomendado | pós-MVP |

---

## Performance (200 câmeras)

- 1 fps/câmera × 200 câmeras = 200 frames/s total
- YOLOv8n no CPU: ~30ms/frame (imgsz=640)
- 4 workers analytics = 50 frames/s cada = buffer adequado
- Configurável: `ANALYTICS_FPS`, `ANALYTICS_WORKERS`
- GPU opcional: com RTX 4060, throughput ~10× maior
