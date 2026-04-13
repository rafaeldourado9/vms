"""
Entidades de domínio de gravações e clipes.

Bounded Context: Recordings

Responsabilidade:
    Gerenciar segmentos de gravação gerados pelo MediaMTX.
    Controlar ciclo de vida de clipes (pending → processing → ready/failed).
    Validar integridade de segmentos via hash SHA-256.

Atores:
    - RecordingSegment: segmento de 60s gerado pelo MediaMTX
    - Clip: clipe solicitado pelo usuário (processamento assíncrono)

Integrações:
    - Cameras Context: segmentos pertencem a uma câmera
    - VOD Context: segmentos são usados para gerar streams HLS
    - Audit Context: acesso a gravações é auditado
    - Events Context: segmentos podem estar associados a eventos

Regras de Negócio:
    1. Segmento só pode ser deletado após expirar retenção
    2. Hash SHA-256 calculado no momento da indexação (imutável)
    3. Clip deve ter ends_at > starts_at
    4. Transições de estado do Clip são validadas (pending → processing → ready/failed)
    5. Cadeia de custódia registra TODO acesso à gravação

Não faz:
    - Transcoding (responsabilidade do VOD Context)
    - Streaming ao vivo (responsabilidade do Streaming Context)
    - Detecção de eventos (responsabilidade do Events Context)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from vms.shared.events import DomainEvent
from vms.shared.exceptions import BusinessRuleViolation, StateTransitionError
from vms.shared.kernel import (
    AggregateRoot,
    CameraId,
    RecordingId,
    TenantId,
)
from vms.shared.value_objects import Sha256Hash


# ─── Enums ────────────────────────────────────────────────────────────────────

class ClipStatus(StrEnum):
    """Estado de processamento de um clipe."""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


# ─── Domain Events ────────────────────────────────────────────────────────────

@dataclass(frozen=True, kw_only=True)
class SegmentIndexed(DomainEvent):
    """Segmento de gravação foi indexado no sistema."""
    segment_id: RecordingId | None = None
    camera_id: CameraId | None = None
    tenant_id: TenantId | None = None
    file_path: str = ""
    duration_seconds: float = 0.0


@dataclass(frozen=True, kw_only=True)
class ClipRequested(DomainEvent):
    """Clipe foi solicitado pelo usuário."""
    clip_id: RecordingId | None = None
    camera_id: CameraId | None = None
    tenant_id: TenantId | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class ClipReady(DomainEvent):
    """Clipe foi processado e está pronto para download."""
    clip_id: RecordingId | None = None
    camera_id: CameraId | None = None
    tenant_id: TenantId | None = None
    file_path: str = ""


@dataclass(frozen=True, kw_only=True)
class ClipFailed(DomainEvent):
    """Falha ao processar clipe."""
    clip_id: RecordingId | None = None
    camera_id: CameraId | None = None
    tenant_id: TenantId | None = None
    error: str = ""


# ─── Entidades ────────────────────────────────────────────────────────────────

@dataclass
class RecordingSegment:
    """
    Segmento de gravação de 60s gerado pelo MediaMTX.

    Entidade imutável após indexação.
    Representa um arquivo de vídeo gravado pela câmera.
    """
    id: RecordingId
    tenant_id: TenantId
    camera_id: CameraId
    mediamtx_path: str
    file_path: str
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    size_bytes: int
    sha256_hash: Sha256Hash | None = None
    # Analytics batch processing flags
    analytics_processed: bool = False
    analytics_plugins_processed: list[str] = field(default_factory=list)
    analytics_processed_at: datetime | None = None

    @classmethod
    def from_file_path(
        cls,
        id: RecordingId,
        tenant_id: TenantId,
        camera_id: CameraId,
        mediamtx_path: str,
        file_path: str,
    ) -> RecordingSegment:
        """
        Factory que extrai metadados do path do arquivo.

        Parseia timestamp do path MediaMTX: /YYYY/MM/DD/HH-MM-SS.mp4
        Corrige double extension (.mp4.mp4) se presente.
        Garante path absoluto com leading slash.

        Uso:
            segment = RecordingSegment.from_file_path(
                id=RecordingId.new(),
                tenant_id=tenant_id,
                camera_id=camera_id,
                mediamtx_path="tenant-1/cam-abc",
                file_path="/recordings/tenant-1/cam-abc/2026/04/12/10-00-00.mp4",
            )
        """
        import os
        import re

        # Corrige double extension
        if file_path.endswith(".mp4.mp4"):
            file_path = file_path[:-4]

        # Garante path absoluto
        if not file_path.startswith("/"):
            file_path = f"/{file_path}"

        # Parseia timestamp do path
        datetime_pattern = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/(\d{2})-(\d{2})-(\d{2})\.mp4$")
        match = datetime_pattern.search(file_path)
        if match:
            y, mo, d, h, mi, s = map(int, match.groups())
            started_at = datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)
        else:
            started_at = datetime.now(timezone.utc)

        duration = 60.0  # MediaMTX gera segmentos de 60s
        ended_at = started_at

        # Tenta obter tamanho do arquivo
        size_bytes = 0
        try:
            size_bytes = os.path.getsize(file_path)
        except OSError:
            pass

        return cls(
            id=id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            mediamtx_path=mediamtx_path,
            file_path=file_path,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=duration,
            size_bytes=size_bytes,
        )

    def is_expired(self, retention_days: int) -> bool:
        """
        Verifica se segmento expirou conforme política de retenção.

        Uso:
            if segment.is_expired(retention_days=7):
                # pode deletar
        """
        cutoff = self.started_at.replace(tzinfo=timezone.utc) if self.started_at.tzinfo is None else self.started_at
        from datetime import timedelta
        expiry_date = cutoff + timedelta(days=retention_days)
        return datetime.now(timezone.utc) > expiry_date

    def verify_integrity(self, current_hash: Sha256Hash) -> bool:
        """
        Verifica integridade do arquivo contra hash armazenado.

        Uso:
            if not segment.verify_integrity(current_hash):
                raise IntegrityError("Arquivo adulterado!")
        """
        if self.sha256_hash is None:
            return False  # Sem hash para comparar
        return self.sha256_hash.value == current_hash.value

    def covers_time(self, timestamp: datetime) -> bool:
        """Verifica se segmento cobre um determinado timestamp."""
        ts = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        return self.started_at <= ts <= self.ended_at

    def mark_processed(self, plugin_name: str) -> None:
        """Marca segmento como processado por um plugin específico."""
        from vms.shared.clock import clock
        self.analytics_processed = True
        if plugin_name not in self.analytics_plugins_processed:
            self.analytics_plugins_processed.append(plugin_name)
        self.analytics_processed_at = clock.now()

    def is_processed_for(self, plugin_name: str) -> bool:
        """Verifica se segmento já foi processado por um plugin específico."""
        return plugin_name in self.analytics_plugins_processed


@dataclass
class Clip(AggregateRoot):
    """
    Clipe de vídeo gerado a partir de segmentos de gravação.

    Aggregate Root do Clip Aggregate.
    Controla ciclo de vida: pending → processing → ready/failed.

    Invariantes:
        1. ends_at deve ser posterior a starts_at
        2. Transições de estado são validadas
        3. Clip ready deve ter file_path preenchido
    """
    id: RecordingId
    tenant_id: TenantId
    camera_id: CameraId
    starts_at: datetime
    ends_at: datetime
    status: str = ClipStatus.PENDING
    file_path: str | None = None
    vms_event_id: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Valida invariantes na criação."""
        starts = self.starts_at if self.starts_at.tzinfo else self.starts_at.replace(tzinfo=timezone.utc)
        ends = self.ends_at if self.ends_at.tzinfo else self.ends_at.replace(tzinfo=timezone.utc)
        if ends <= starts:
            raise BusinessRuleViolation(
                "ends_at deve ser posterior a starts_at",
                details={"starts_at": str(starts), "ends_at": str(ends)},
            )

    # ─── Transições de Estado ──────────────────────────────────────────────

    def start_processing(self) -> None:
        """
        Inicia processamento do clipe.

        Transição: pending → processing.

        Raises:
            StateTransitionError: Se clipe não está em pending.
        """
        if self.status != ClipStatus.PENDING:
            raise StateTransitionError(
                f"Não é possível iniciar processamento de clipe com status '{self.status}'. "
                f"Esperado: {ClipStatus.PENDING}"
            )
        self.status = ClipStatus.PROCESSING
        self.record_event(ClipRequested(
            clip_id=self.id,
            camera_id=self.camera_id,
            tenant_id=self.tenant_id,
            starts_at=self.starts_at,
            ends_at=self.ends_at,
        ))

    def mark_ready(self, file_path: str) -> None:
        """
        Marca clipe como pronto com arquivo gerado.

        Transição: processing → ready.

        Raises:
            StateTransitionError: Se clipe não está em processing.
        """
        if self.status != ClipStatus.PROCESSING:
            raise StateTransitionError(
                f"Não é possível marcar como pronto clipe com status '{self.status}'. "
                f"Esperado: {ClipStatus.PROCESSING}"
            )
        self.status = ClipStatus.READY
        self.file_path = file_path
        self.record_event(ClipReady(
            clip_id=self.id,
            camera_id=self.camera_id,
            tenant_id=self.tenant_id,
            file_path=file_path,
        ))

    def mark_failed(self, error: str) -> None:
        """
        Marca clipe como falho.

        Transição: pending/processing → failed.
        Sempre permitido.
        """
        self.status = ClipStatus.FAILED
        self.error = error
        self.record_event(ClipFailed(
            clip_id=self.id,
            camera_id=self.camera_id,
            tenant_id=self.tenant_id,
            error=error,
        ))

    @property
    def is_ready(self) -> bool:
        """Verifica se clipe está pronto para download."""
        return self.status == ClipStatus.READY

    @property
    def duration_seconds(self) -> float:
        """Duração do clipe em segundos."""
        starts = self.starts_at if self.starts_at.tzinfo else self.starts_at.replace(tzinfo=timezone.utc)
        ends = self.ends_at if self.ends_at.tzinfo else self.ends_at.replace(tzinfo=timezone.utc)
        return (ends - starts).total_seconds()
