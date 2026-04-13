"""Testes do serviço VOD."""
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from vms.vod.service import VODService, VODStream
from vms.vod.repository import VODRepository


@pytest.fixture
def mock_repo():
    """Mock do repositório VOD."""
    repo = AsyncMock(spec=VODRepository)
    repo.create.return_value = VODStream(
        id="test-stream-1",
        tenant_id="tenant-1",
        camera_id="cam-1",
        segments=["/recordings/tenant-1/cam-1/2026/04/12/10-00-00.mp4"],
        started_at=datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 4, 12, 10, 1, 0, tzinfo=timezone.utc),
        playlist_path="",
        status="pending",
    )
    return repo


@pytest.fixture
def vod_service(mock_repo, tmp_path):
    """Instância do serviço VOD com diretório temporário."""
    return VODService(repository=mock_repo, output_dir=str(tmp_path / "vod"))


class TestVODService:
    """Testes do VODService."""

    async def test_create_vod_stream(self, vod_service, mock_repo):
        """Testa criação de stream VOD."""
        segments = ["/recordings/tenant-1/cam-1/2026/04/12/10-00-00.mp4"]
        started_at = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        ended_at = datetime(2026, 4, 12, 10, 1, 0, tzinfo=timezone.utc)

        vod = await vod_service.create_vod_stream(
            stream_id="test-stream-1",
            tenant_id="tenant-1",
            camera_id="cam-1",
            segments=segments,
            started_at=started_at,
            ended_at=ended_at,
        )

        assert vod.id == "test-stream-1"
        assert vod.tenant_id == "tenant-1"
        assert vod.camera_id == "cam-1"
        assert vod.segments == segments
        assert vod.status == "pending"

        mock_repo.create.assert_awaited_once()

    async def test_generate_hls_single_segment(self, vod_service, mock_repo, tmp_path):
        """Testa geração de HLS com único segmento."""
        # Cria arquivo MP4 falso
        mp4_dir = tmp_path / "recordings" / "tenant-1" / "cam-1" / "2026" / "04" / "12"
        mp4_dir.mkdir(parents=True)
        mp4_file = mp4_dir / "10-00-00.mp4"
        mp4_file.write_bytes(b"fake mp4 content")

        vod = VODStream(
            id="test-stream-1",
            tenant_id="tenant-1",
            camera_id="cam-1",
            segments=[str(mp4_file)],
            started_at=datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 4, 12, 10, 1, 0, tzinfo=timezone.utc),
            playlist_path="",
            status="pending",
        )

        mock_repo.get_by_id.return_value = vod

        # Mock do ffmpeg
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            mock_exec.return_value = mock_process

            playlist_path = await vod_service.generate_hls_playlist(vod)

            assert playlist_path.endswith("playlist.m3u8")
            assert vod.status == "ready"
            mock_exec.assert_called_once()

    async def test_generate_hls_multiple_segments(self, vod_service, mock_repo, tmp_path):
        """Testa geração de HLS com múltiplos segmentos."""
        # Cria arquivos MP4 falsos
        segments = []
        for i in range(3):
            mp4_dir = tmp_path / "recordings" / "tenant-1" / "cam-1" / "2026" / "04" / "12"
            mp4_dir.mkdir(parents=True)
            mp4_file = mp4_dir / f"10-0{i}-00.mp4"
            mp4_file.write_bytes(b"fake mp4 content")
            segments.append(str(mp4_file))

        vod = VODStream(
            id="test-stream-2",
            tenant_id="tenant-1",
            camera_id="cam-1",
            segments=segments,
            started_at=datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 4, 12, 10, 3, 0, tzinfo=timezone.utc),
            playlist_path="",
            status="pending",
        )

        # Mock do ffmpeg
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            mock_exec.return_value = mock_process

            playlist_path = await vod_service.generate_hls_playlist(vod)

            assert playlist_path.endswith("playlist.m3u8")
            assert vod.status == "ready"
            assert mock_exec.call_count == 1

    async def test_generate_hls_file_not_found(self, vod_service, mock_repo):
        """Testa falha quando segmento não existe."""
        vod = VODStream(
            id="test-stream-3",
            tenant_id="tenant-1",
            camera_id="cam-1",
            segments=["/nonexistent/file.mp4"],
            started_at=datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 4, 12, 10, 1, 0, tzinfo=timezone.utc),
            playlist_path="",
            status="pending",
        )

        with pytest.raises(RuntimeError, match="ffmpeg falhou"):
            await vod_service.generate_hls_playlist(vod)

        assert vod.status == "failed"
        assert vod.error is not None

    async def test_get_streaming_url_ready(self, vod_service, mock_repo):
        """Testa obtenção de URL de stream pronto."""
        vod = VODStream(
            id="test-stream-1",
            tenant_id="tenant-1",
            camera_id="cam-1",
            segments=[],
            started_at=datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 4, 12, 10, 1, 0, tzinfo=timezone.utc),
            playlist_path="/tmp/vod/tenant-1/cam-1/test-stream-1/playlist.m3u8",
            status="ready",
        )

        mock_repo.get_by_id.return_value = vod

        url = await vod_service.get_streaming_url("test-stream-1", "tenant-1")

        assert url == vod.playlist_path

    async def test_get_streaming_url_pending(self, vod_service, mock_repo):
        """Testa obtenção de URL de stream pendente."""
        vod = VODStream(
            id="test-stream-1",
            tenant_id="tenant-1",
            camera_id="cam-1",
            segments=[],
            started_at=datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 4, 12, 10, 1, 0, tzinfo=timezone.utc),
            playlist_path="",
            status="pending",
        )

        mock_repo.get_by_id.return_value = vod

        with patch.object(vod_service, 'generate_hls_playlist', new_callable=AsyncMock):
            url = await vod_service.get_streaming_url("test-stream-1", "tenant-1")
            assert url is None  # Ainda não está pronto

    async def test_cleanup_old_streams(self, vod_service, mock_repo, tmp_path):
        """Testa limpeza de streams antigos."""
        # Cria diretórios de streams falsos
        vod_dir = tmp_path / "vod" / "tenant-1"
        vod_dir.mkdir(parents=True)
        (vod_dir / "cam-1" / "old-stream").mkdir(parents=True)
        (vod_dir / "cam-1" / "new-stream").mkdir(parents=True)

        mock_repo.cleanup_expired.return_value = 2

        before_date = datetime(2026, 4, 11, tzinfo=timezone.utc)
        count = await vod_service.cleanup_old_streams("tenant-1", before_date)

        assert count == 2
        mock_repo.cleanup_expired.assert_awaited_once_with("tenant-1", before_date)
