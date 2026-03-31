"""Testes unitários do StreamManager."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.stream_manager import StreamManager, _MAX_RESTART_ATTEMPTS


@pytest.fixture
def manager() -> StreamManager:
    """StreamManager com URL RTMP de teste."""
    return StreamManager(mediamtx_rtmp_base="rtmp://mediamtx:1935")


class TestBuildRtmpUrl:
    """Testes de construção de URL RTMP."""

    def test_url_construida_corretamente(self, manager: StreamManager) -> None:
        """URL RTMP inclui base + path."""
        url = manager._build_rtmp_url("tenant-1/cam-abc")
        assert url == "rtmp://mediamtx:1935/tenant-1/cam-abc"

    def test_url_sem_barra_dupla(self, manager: StreamManager) -> None:
        """Base com barra trailing não gera barra dupla."""
        m = StreamManager("rtmp://mediamtx:1935/")
        assert m._build_rtmp_url("cam-1") == "rtmp://mediamtx:1935/cam-1"


class TestStartStream:
    """Testes de inicialização de stream."""

    @patch("agent.stream_manager.shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("asyncio.create_subprocess_exec")
    async def test_inicia_ffmpeg(
        self, mock_exec: AsyncMock, mock_which: MagicMock, manager: StreamManager
    ) -> None:
        """start_stream lança processo ffmpeg com parâmetros corretos."""
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.returncode = None
        mock_exec.return_value = mock_proc

        await manager.start_stream("cam-1", "rtsp://cam:554/live", "tenant-1/cam-1")

        assert "cam-1" in manager.active_streams
        mock_exec.assert_called_once()
        cmd_args = mock_exec.call_args[0]
        assert "ffmpeg" in cmd_args
        assert "rtsp://cam:554/live" in cmd_args
        assert "rtmp://mediamtx:1935/tenant-1/cam-1" in cmd_args

    @patch("agent.stream_manager.shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("asyncio.create_subprocess_exec")
    async def test_nao_duplica_stream(
        self, mock_exec: AsyncMock, mock_which: MagicMock, manager: StreamManager
    ) -> None:
        """start_stream ignora câmera já ativa."""
        mock_proc = MagicMock()
        mock_proc.pid = 111
        mock_proc.returncode = None
        mock_exec.return_value = mock_proc

        await manager.start_stream("cam-1", "rtsp://cam:554/live", "ten-1/cam-1")
        await manager.start_stream("cam-1", "rtsp://cam:554/live", "ten-1/cam-1")

        # Só lançou uma vez
        assert mock_exec.call_count == 1

    @patch("agent.stream_manager.shutil.which", return_value=None)
    async def test_sem_ffmpeg_nao_lanca(
        self, mock_which: MagicMock, manager: StreamManager
    ) -> None:
        """Se ffmpeg não está no PATH, não cria processo nem lança exceção."""
        await manager.start_stream("cam-1", "rtsp://cam:554/live", "ten-1/cam-1")
        assert "cam-1" not in manager.active_streams


class TestStopStream:
    """Testes de parada de stream."""

    @patch("agent.stream_manager.shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("asyncio.create_subprocess_exec")
    async def test_para_stream_ativo(
        self, mock_exec: AsyncMock, mock_which: MagicMock, manager: StreamManager
    ) -> None:
        """stop_stream termina processo e remove da lista ativa."""
        mock_proc = MagicMock()
        mock_proc.pid = 222
        mock_proc.returncode = None
        mock_proc.wait = AsyncMock(return_value=0)
        mock_exec.return_value = mock_proc

        await manager.start_stream("cam-1", "rtsp://cam:554/live", "ten/cam-1")
        await manager.stop_stream("cam-1")

        assert "cam-1" not in manager.active_streams
        mock_proc.terminate.assert_called_once()

    async def test_stop_inexistente_nao_falha(self, manager: StreamManager) -> None:
        """stop_stream de câmera inexistente não lança exceção."""
        await manager.stop_stream("cam-inexistente")  # não deve falhar


class TestReconcile:
    """Testes de reconciliação de streams."""

    @patch("agent.stream_manager.shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("asyncio.create_subprocess_exec")
    async def test_inicia_cameras_novas(
        self, mock_exec: AsyncMock, mock_which: MagicMock, manager: StreamManager
    ) -> None:
        """reconcile inicia streams para câmeras novas."""
        mock_proc = MagicMock()
        mock_proc.pid = 333
        mock_proc.returncode = None
        mock_exec.return_value = mock_proc

        desired = {
            "cam-1": ("rtsp://cam1:554/live", "ten/cam-1"),
            "cam-2": ("rtsp://cam2:554/live", "ten/cam-2"),
        }
        await manager.reconcile(desired)

        assert mock_exec.call_count == 2

    @patch("agent.stream_manager.shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("asyncio.create_subprocess_exec")
    async def test_para_cameras_removidas(
        self, mock_exec: AsyncMock, mock_which: MagicMock, manager: StreamManager
    ) -> None:
        """reconcile para streams de câmeras que saíram da config."""
        mock_proc = MagicMock()
        mock_proc.pid = 444
        mock_proc.returncode = None
        mock_proc.wait = AsyncMock(return_value=0)
        mock_exec.return_value = mock_proc

        await manager.start_stream("cam-old", "rtsp://old:554/live", "ten/cam-old")
        # Reconcilia sem cam-old
        await manager.reconcile({"cam-new": ("rtsp://new:554/live", "ten/cam-new")})

        assert "cam-old" not in manager._streams


class TestRestartDeadStreams:
    """Testes de reinicialização de streams mortos."""

    @patch("agent.stream_manager.shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("asyncio.create_subprocess_exec")
    async def test_reinicia_processo_morto(
        self, mock_exec: AsyncMock, mock_which: MagicMock, manager: StreamManager
    ) -> None:
        """restart_dead_streams reinicia ffmpeg que saiu inesperadamente."""
        mock_proc = MagicMock()
        mock_proc.pid = 555
        mock_proc.returncode = None
        mock_exec.return_value = mock_proc

        await manager.start_stream("cam-1", "rtsp://cam:554/live", "ten/cam-1")

        # Simula processo morto
        sp = manager._streams["cam-1"]
        sp.process.returncode = 1

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await manager.restart_dead_streams()

        # ffmpeg foi lançado novamente
        assert mock_exec.call_count == 2

    @patch("agent.stream_manager.shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("asyncio.create_subprocess_exec")
    async def test_nao_reinicia_apos_limite(
        self, mock_exec: AsyncMock, mock_which: MagicMock, manager: StreamManager
    ) -> None:
        """Não reinicia câmera que atingiu limite de tentativas."""
        mock_proc = MagicMock()
        mock_proc.pid = 666
        mock_proc.returncode = None
        mock_exec.return_value = mock_proc

        await manager.start_stream("cam-1", "rtsp://cam:554/live", "ten/cam-1")
        sp = manager._streams["cam-1"]
        sp.process.returncode = 1
        sp.restart_count = _MAX_RESTART_ATTEMPTS

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await manager.restart_dead_streams()

        # Não lançou novamente
        assert mock_exec.call_count == 1
