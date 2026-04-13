"""
Ports do Bounded Context: VOD.

Interfaces que o VOD Context exporta para outros contexts usarem.
"""
from __future__ import annotations

from typing import Protocol


class VODSegmentPort(Protocol):
    """
    Porta para buscar segmentos de gravação no VOD Context.

    VOD precisa de segmentos para gerar streams HLS.

    Implementação real: RecordingSegmentRepository do bounded context Recordings.
    """

    async def get_by_id(self, segment_id: str, tenant_id: str) -> dict | None:
        """Retorna segmento com file_path e metadados mínimos."""
        ...
