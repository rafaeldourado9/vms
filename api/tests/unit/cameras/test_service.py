"""Testes unitários dos services de câmeras e agents."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from vms.cameras.domain import Agent, AgentStatus, Camera, CameraConfig, CameraManufacturer, StreamProtocol
from vms.cameras.service import AgentService, CameraService
from vms.core.exceptions import NotFoundError
from vms.iam.domain import ApiKey, ApiKeyOwnerType


class TestCameraService:
    """Testes do CameraService."""

    @pytest.fixture
    def camera_repo(self):
        repo = AsyncMock()
        repo.create = AsyncMock(side_effect=lambda c: c)
        repo.update = AsyncMock(side_effect=lambda c: c)
        repo.delete = AsyncMock(return_value=True)
        repo.get_by_id = AsyncMock(return_value=None)
        repo.list_by_tenant = AsyncMock(return_value=[])
        return repo

    @pytest.fixture
    def mediamtx(self):
        mtx = AsyncMock()
        mtx.add_path = AsyncMock(return_value=True)
        mtx.remove_path = AsyncMock(return_value=True)
        return mtx

    @pytest.fixture
    def svc(self, camera_repo, mediamtx):
        return CameraService(camera_repo, mediamtx)

    async def test_create_camera(self, svc, camera_repo, mediamtx):
        """Criar câmera persiste e registra no MediaMTX."""
        from vms.cameras.domain import StreamProtocol
        cam = await svc.create_camera(
            tenant_id="t1",
            name="Cam 1",
            stream_protocol=StreamProtocol.RTSP_PULL,
            rtsp_url="rtsp://x",
            agent_id="a1",
        )
        assert cam.name == "Cam 1"
        camera_repo.create.assert_called_once()
        mediamtx.add_path.assert_called_once()

    async def test_get_camera_ok(self, svc, camera_repo):
        """Retorna câmera quando existe."""
        expected = Camera(
            id="c1", tenant_id="t1", name="Cam",
            rtsp_url="rtsp://x", manufacturer=CameraManufacturer.GENERIC,
        )
        camera_repo.get_by_id.return_value = expected
        result = await svc.get_camera("c1", "t1")
        assert result.id == "c1"

    async def test_get_camera_not_found(self, svc):
        """Lança NotFoundError quando câmera não existe."""
        with pytest.raises(NotFoundError):
            await svc.get_camera("xxx", "t1")

    async def test_list_cameras(self, svc, camera_repo):
        """Lista câmeras do tenant."""
        camera_repo.list_by_tenant.return_value = [
            Camera(id="c1", tenant_id="t1", name="A", rtsp_url="rtsp://a", manufacturer=CameraManufacturer.GENERIC),
            Camera(id="c2", tenant_id="t1", name="B", rtsp_url="rtsp://b", manufacturer=CameraManufacturer.GENERIC),
        ]
        result = await svc.list_cameras("t1")
        assert len(result) == 2

    async def test_update_camera(self, svc, camera_repo):
        """Atualiza câmera existente."""
        existing = Camera(
            id="c1", tenant_id="t1", name="Old",
            rtsp_url="rtsp://x", manufacturer=CameraManufacturer.GENERIC,
        )
        camera_repo.get_by_id.return_value = existing
        result = await svc.update_camera("c1", "t1", name="New")
        assert result.name == "New"

    async def test_delete_camera(self, svc, camera_repo, mediamtx):
        """Delete remove do banco e do MediaMTX."""
        existing = Camera(
            id="c1", tenant_id="t1", name="Cam",
            rtsp_url="rtsp://x", manufacturer=CameraManufacturer.GENERIC,
        )
        camera_repo.get_by_id.return_value = existing
        await svc.delete_camera("c1", "t1")
        mediamtx.remove_path.assert_called_once()
        camera_repo.delete.assert_called_once_with("c1", "t1")


class TestAgentService:
    """Testes do AgentService."""

    @pytest.fixture
    def agent_repo(self):
        repo = AsyncMock()
        repo.create = AsyncMock(side_effect=lambda a: a)
        repo.update = AsyncMock(side_effect=lambda a: a)
        repo.get_by_id = AsyncMock(return_value=None)
        repo.list_by_tenant = AsyncMock(return_value=[])
        return repo

    @pytest.fixture
    def camera_repo(self):
        repo = AsyncMock()
        repo.list_by_agent = AsyncMock(return_value=[])
        return repo

    @pytest.fixture
    def api_key_svc(self):
        svc = AsyncMock()
        svc.issue_api_key = AsyncMock(return_value=(
            ApiKey(
                id="k1", tenant_id="t1", owner_type=ApiKeyOwnerType.AGENT,
                owner_id="a1", key_hash="h", prefix="vms_abc12345",
            ),
            "vms_plain_key_1234",
        ))
        return svc

    @pytest.fixture
    def svc(self, agent_repo, camera_repo, api_key_svc):
        return AgentService(agent_repo, camera_repo, api_key_svc)

    async def test_create_agent(self, svc, agent_repo, api_key_svc):
        """Criar agent persiste e emite API key."""
        agent, plain_key = await svc.create_agent("t1", "Agent 1")
        assert agent.name == "Agent 1"
        assert plain_key == "vms_plain_key_1234"
        agent_repo.create.assert_called_once()
        api_key_svc.issue_api_key.assert_called_once()

    async def test_get_agent_not_found(self, svc):
        """Lança NotFoundError quando agent não existe."""
        with pytest.raises(NotFoundError):
            await svc.get_agent("xxx", "t1")

    async def test_get_agent_config(self, svc, agent_repo, camera_repo):
        """Retorna config com câmeras vinculadas."""
        agent = Agent(id="a1", tenant_id="t1", name="Agent")
        agent_repo.get_by_id.return_value = agent
        camera_repo.list_by_agent.return_value = [
            Camera(
                id="c1", tenant_id="t1", name="Cam",
                stream_protocol=StreamProtocol.RTSP_PULL,
                rtsp_url="rtsp://x", manufacturer=CameraManufacturer.GENERIC,
                agent_id="a1",
            ),
        ]
        result_agent, configs = await svc.get_agent_config("a1", "t1")
        assert result_agent.id == "a1"
        assert len(configs) == 1
        assert configs[0].rtmp_push_url.endswith("tenant-t1/cam-c1")

    async def test_heartbeat(self, svc, agent_repo):
        """Heartbeat marca agent como online."""
        agent = Agent(id="a1", tenant_id="t1", name="Agent")
        agent_repo.get_by_id.return_value = agent
        result = await svc.register_heartbeat("a1", "t1", "1.0.0", 5, 0)
        assert result.status == AgentStatus.ONLINE
        assert result.version == "1.0.0"
        agent_repo.update.assert_called_once()

    async def test_delete_agent(self, svc, agent_repo):
        """Delete marca agent como offline."""
        agent = Agent(id="a1", tenant_id="t1", name="Agent")
        agent_repo.get_by_id.return_value = agent
        await svc.delete_agent("a1", "t1")
        agent_repo.update.assert_called_once()
