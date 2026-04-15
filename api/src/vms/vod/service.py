"""Serviço VOD para streaming de gravações.

Converte segmentos MP4 em streams HLS dinâmicos para playback eficiente.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Protocol

from vms.vod.domain import VODStream

logger = logging.getLogger(__name__)


class VODRepositoryPort(Protocol):
    """Interface do repositório de streams VOD."""

    async def create(self, stream: VODStream) -> VODStream: ...
    async def get_by_id(self, stream_id: str, tenant_id: str) -> VODStream | None: ...
    async def update(self, stream: VODStream) -> VODStream: ...
    async def cleanup_expired(self, tenant_id: str, before_date: datetime) -> int: ...


class VODService:
    """Serviço para gerenciamento de streams VOD (HLS)."""

    def __init__(
        self,
        repository: VODRepositoryPort,
        output_dir: str = "/tmp/vod",
        segment_duration: int = 10,
    ) -> None:
        self._repo = repository
        self._output_dir = Path(output_dir)
        self._segment_duration = segment_duration
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def create_vod_stream(
        self,
        stream_id: VODStreamId,
        tenant_id: TenantId,
        camera_id: CameraId,
        segments: list[str],
        started_at: datetime,
        ended_at: datetime,
    ) -> VODStream:
        """Cria e gera um stream VOD a partir de segmentos MP4."""
        vod = VODStream.create(
            id=stream_id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            segments=segments,
            started_at=started_at,
            ended_at=ended_at,
        )
        vod = await self._repo.create(vod)
        return vod

    async def generate_hls_playlist(self, vod: VODStream) -> str:
        """Gera playlist HLS a partir de segmentos MP4.

        Retorna o caminho do arquivo .m3u8 gerado.
        """
        try:
            vod.start_generation()
            await self._repo.update(vod)

            # Cria diretório para este stream
            stream_dir = self._output_dir / str(vod.tenant_id) / str(vod.camera_id) / str(vod.id)
            stream_dir.mkdir(parents=True, exist_ok=True)

            playlist_path = stream_dir / "playlist.m3u8"

            # Se há apenas um segmento, cria HLS direto
            if len(vod.segments) == 1:
                await self._create_hls_from_single_segment(vod.segments[0], str(playlist_path))
            else:
                # Múltiplos segmentos: concatena e converte
                await self._create_hls_from_multiple_segments(vod.segments, str(playlist_path))

            vod.mark_ready(str(playlist_path))
            await self._repo.update(vod)

            logger.info("HLS gerado com sucesso: %s", vod.playlist_path)
            return vod.playlist_path

        except Exception as exc:
            vod.mark_failed(str(exc))
            await self._repo.update(vod)
            logger.exception("Erro ao gerar HLS para stream %s", vod.id)
            raise

    async def _create_hls_from_single_segment(self, mp4_path: str, playlist_path: str) -> None:
        """Cria HLS a partir de um único segmento MP4."""
        if not os.path.exists(mp4_path):
            raise FileNotFoundError(f"Segmento não encontrado: {mp4_path}")

        # Usa ffmpeg para criar HLS
        cmd = [
            "ffmpeg",
            "-i", mp4_path,
            "-c", "copy",  # Copia codecs (sem re-encoding)
            "-f", "hls",
            "-hls_time", str(self._segment_duration),
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", f"{playlist_path.rsplit('.', 1)[0]}_%03d.ts",
            "-y",  # Overwrite
            playlist_path,
        ]

        await self._run_ffmpeg(cmd)

    async def _create_hls_from_multiple_segments(
        self,
        segment_paths: list[str],
        playlist_path: str,
    ) -> None:
        """Cria HLS a partir de múltiplos segmentos MP4."""
        # Passo 1: Criar arquivo de lista para concat
        concat_file = playlist_path.rsplit(".", 1)[0] + "_concat.txt"
        with open(concat_file, "w") as f:
            for seg_path in segment_paths:
                if os.path.exists(seg_path):
                    f.write(f"file '{seg_path}'\n")
                else:
                    logger.warning("Segmento não encontrado, ignorando: %s", seg_path)

        # Passo 2: Concatenar e converter para HLS
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            "-f", "hls",
            "-hls_time", str(self._segment_duration),
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", f"{playlist_path.rsplit('.', 1)[0]}_%03d.ts",
            "-y",
            playlist_path,
        ]

        try:
            await self._run_ffmpeg(cmd)
        finally:
            # Limpa arquivo de concat
            if os.path.exists(concat_file):
                os.unlink(concat_file)

    async def _run_ffmpeg(self, cmd: list[str]) -> None:
        """Executa comando ffmpeg de forma assíncrona."""
        logger.debug("Executando ffmpeg: %s", " ".join(cmd))

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Erro desconhecido"
            logger.error("ffmpeg falhou: %s", error_msg)
            raise RuntimeError(f"ffmpeg falhou: {error_msg}")

        logger.debug("ffmpeg concluído com sucesso")

    async def get_streaming_url(self, vod_id: str, tenant_id: str) -> str | None:
        """Retorna URL de streaming HLS para um VOD."""
        vod = await self._repo.get_by_id(vod_id, tenant_id)
        if not vod:
            return None

        if vod.status == "pending":
            # Gera playlist em background
            asyncio.create_task(self.generate_hls_playlist(vod))
            return None

        if vod.status == "generating":
            return None  # Ainda gerando

        if vod.status == "ready":
            return vod.playlist_path

        return None  # failed

    async def cleanup_old_streams(self, tenant_id: str, before_date: datetime) -> int:
        """Remove streams VOD antigos."""
        count = await self._repo.cleanup_expired(tenant_id, before_date)

        # Remove arquivos físicos
        stream_dir = self._output_dir / tenant_id
        if stream_dir.exists():
            for item in stream_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)

        return count
