"""
Entidades de domínio para serviço VOD.

Bounded Context: VOD (Video on Demand)

Responsabilidade:
    Gerenciar streams VOD gerados a partir de segmentos de gravação.
    Controlar ciclo de vida de geração de HLS (pending → generating → ready/failed).
    Fornecer playlists HLS para playback eficiente.

Atores:
    - VODStream: stream HLS gerado a partir de segmentos MP4

Integrações:
    - Recordings Context: consome segmentos de gravação
    - Frontend: consome playlist HLS via hls.js

Regras de Negócio:
    1. VODStream deve ter pelo menos um segmento
    2. Transições de estado são validadas
    3. Stream ready deve ter playlist_path preenchido
    4. Stream failed deve ter error preenchido

Não faz:
    - Gravação de segmentos (responsabilidade do Recordings Context)
    - Streaming ao vivo (responsabilidade do Streaming Context)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from vms.shared.events import DomainEvent
from vms.shared.exceptions import BusinessRuleViolation, StateTransitionError
from vms.shared.kernel import (
    AggregateRoot,
    CameraId,
    TenantId,
    VODStreamId,
)


# ─── Domain Events ────────────────────────────────────────────────────────────

@dataclass(frozen=True, kw_only=True)
class VODStreamCreated(DomainEvent):
    """Stream VOD foi criado."""
    stream_id: VODStreamId | None = None
    camera_id: CameraId | None = None
    tenant_id: TenantId | None = None
    segment_count: int = 0


@dataclass(frozen=True, kw_only=True)
class VODStreamGenerationStarted(DomainEvent):
    """Geração de HLS foi iniciada."""
    stream_id: VODStreamId | None = None
    camera_id: CameraId | None = None
    tenant_id: TenantId | None = None


@dataclass(frozen=True, kw_only=True)
class VODStreamReady(DomainEvent):
    """Stream VOD foi gerado com sucesso."""
    stream_id: VODStreamId | None = None
    camera_id: CameraId | None = None
    tenant_id: TenantId | None = None
    playlist_path: str = ""


@dataclass(frozen=True, kw_only=True)
class VODStreamFailed(DomainEvent):
    """Falha ao gerar stream VOD."""
    stream_id: VODStreamId | None = None
    camera_id: CameraId | None = None
    tenant_id: TenantId | None = None
    error: str = ""


# ─── Entidades ────────────────────────────────────────────────────────────────

@dataclass
class VODStream(AggregateRoot):
    """
    Stream VOD gerado a partir de segmentos de gravação.

    Aggregate Root do VODStream Aggregate.
    Controla ciclo de vida de geração de HLS:
        pending → generating → ready
        pending/processing → failed

    Invariantes:
        1. Deve ter pelo menos um segmento
        2. Transições de estado são validadas
        3. Stream ready deve ter playlist_path
        4. Stream failed deve ter error
    """
    id: VODStreamId
    tenant_id: TenantId
    camera_id: CameraId
    segments: list[str]  # file_paths dos segmentos MP4 originais
    started_at: datetime
    ended_at: datetime
    playlist_path: str = ""
    status: str = "pending"  # pending, generating, ready, failed
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Valida invariantes na criação."""
        if not self.segments:
            raise BusinessRuleViolation(
                "VODStream deve ter pelo menos um segmento",
                details={"stream_id": str(self.id)},
            )

    @classmethod
    def create(
        cls,
        id: VODStreamId,
        tenant_id: TenantId,
        camera_id: CameraId,
        segments: list[str],
        started_at: datetime,
        ended_at: datetime,
    ) -> VODStream:
        """
        Factory para stream VOD.

        Uso:
            stream = VODStream.create(
                id=VODStreamId.new(),
                tenant_id=tenant_id,
                camera_id=camera_id,
                segments=["/path/seg1.mp4", "/path/seg2.mp4"],
                started_at=start,
                ended_at=end,
            )
        """
        return cls(
            id=id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            segments=segments,
            started_at=started_at,
            ended_at=ended_at,
        )

    # ─── Transições de Estado ──────────────────────────────────────────────

    def start_generation(self) -> None:
        """
        Inicia geração de playlist HLS.

        Transição: pending → generating.

        Raises:
            StateTransitionError: Se stream não está em pending.
        """
        if self.status != "pending":
            raise StateTransitionError(
                f"Não é possível iniciar geração de stream com status '{self.status}'. "
                f"Esperado: pending"
            )
        self.status = "generating"
        self.updated_at = datetime.now(timezone.utc)
        self.record_event(VODStreamGenerationStarted(
            stream_id=self.id,
            camera_id=self.camera_id,
            tenant_id=self.tenant_id,
        ))

    def mark_ready(self, playlist_path: str) -> None:
        """
        Marca stream como pronto com playlist gerada.

        Transição: generating → ready.

        Raises:
            StateTransitionError: Se stream não está em generating.
        """
        if self.status != "generating":
            raise StateTransitionError(
                f"Não é possível marcar como pronto stream com status '{self.status}'. "
                f"Esperado: generating"
            )
        self.status = "ready"
        self.playlist_path = playlist_path
        self.updated_at = datetime.now(timezone.utc)
        self.record_event(VODStreamReady(
            stream_id=self.id,
            camera_id=self.camera_id,
            tenant_id=self.tenant_id,
            playlist_path=playlist_path,
        ))

    def mark_failed(self, error: str) -> None:
        """
        Marca stream como falho.

        Transição: pending/generating → failed.
        Sempre permitido.
        """
        self.status = "failed"
        self.error = error
        self.updated_at = datetime.now(timezone.utc)
        self.record_event(VODStreamFailed(
            stream_id=self.id,
            camera_id=self.camera_id,
            tenant_id=self.tenant_id,
            error=error,
        ))

    @property
    def is_ready(self) -> bool:
        """Verifica se stream está pronto para playback."""
        return self.status == "ready"

    @property
    def is_failed(self) -> bool:
        """Verifica se stream falhou."""
        return self.status == "failed"

    @property
    def is_generating(self) -> bool:
        """Verifica se stream está sendo gerado."""
        return self.status == "generating"

    @property
    def segment_count(self) -> int:
        """Quantidade de segmentos neste stream."""
        return len(self.segments)

    @property
    def duration_seconds(self) -> float:
        """Duração total do stream em segundos."""
        starts = self.started_at if self.started_at.tzinfo else self.started_at.replace(tzinfo=timezone.utc)
        ends = self.ended_at if self.ended_at.tzinfo else self.ended_at.replace(tzinfo=timezone.utc)
        return (ends - starts).total_seconds()
