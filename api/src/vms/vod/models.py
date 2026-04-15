"""Modelos SQLAlchemy para VOD."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text, Index, func
from sqlalchemy.dialects.postgresql import ARRAY
from vms.infrastructure.database import Base


class VODStreamModel(Base):
    """Modelo para streams VOD gerados."""

    __tablename__ = "vod_streams"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    camera_id = Column(String, nullable=False, index=True)
    segments = Column(ARRAY(Text), nullable=False)  # Lista de file_paths
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=False)
    playlist_path = Column(Text, default="")
    status = Column(String, default="pending", index=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('ix_vod_streams_tenant_id', 'tenant_id'),
        Index('ix_vod_streams_camera_id', 'camera_id'),
        Index('ix_vod_streams_status', 'status'),
    )
