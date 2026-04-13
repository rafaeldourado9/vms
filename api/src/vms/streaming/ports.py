"""
Ports do Bounded Context: Streaming.

Interfaces que o Streaming Context exporta para outros contexts usarem.
Implementações são injetadas via Composition Root (main.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class StreamCameraInfo:
    """DTO mínimo de câmera necessário para o Streaming Context."""
    id: str
    tenant_id: str
    mediamtx_path: str
    is_active: bool


class StreamCameraPort(Protocol):
    """
    Porta para buscar câmeras no Streaming Context.

    O Streaming precisa apenas de informações mínimas da câmera
    para validar e gerenciar sessões de stream.

    Implementação real: CameraRepository do bounded context Cameras.
    """

    async def get_by_id(self, camera_id: str, tenant_id: str) -> StreamCameraInfo | None: ...
    async def get_by_stream_key(self, stream_key: str) -> StreamCameraInfo | None: ...
    async def get_by_mediamtx_path(self, mediamtx_path: str) -> StreamCameraInfo | None: ...


class StreamAuthPort(Protocol):
    """
    Porta para autenticação no Streaming Context.

    Delega ao IAM Context a validação de API keys e tokens.

    Implementação real: AuthService + ApiKeyRepository do IAM Context.
    """

    async def verify_api_key(self, api_key: str) -> str | None:
        """Retorna owner_id se API key válida, None caso contrário."""
        ...

    async def decode_viewer_token(self, token: str) -> dict | None:
        """Decodifica viewer token. Retorna claims ou None."""
        ...
