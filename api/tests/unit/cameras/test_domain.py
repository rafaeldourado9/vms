"""Testes unitários das entidades de domínio de câmeras e agents."""
import pytest

from vms.cameras.domain import (
    Agent,
    AgentStatus,
    Camera,
    CameraConfig,
    CameraManufacturer,
)


class TestCamera:
    """Testes da entidade Camera."""

    def test_create_camera_defaults(self):
        camera = Camera(
            id="c1", tenant_id="t1", name="Cam 1",
            rtsp_url="rtsp://192.168.1.100:554/stream",
            manufacturer=CameraManufacturer.GENERIC,
        )
        assert camera.is_active is True
        assert camera.is_online is False
        assert camera.retention_days == 7
        assert camera.agent_id is None

    def test_mediamtx_path(self):
        camera = Camera(
            id="cam-1", tenant_id="tenant-1", name="Cam",
            rtsp_url="rtsp://x", manufacturer=CameraManufacturer.HIKVISION,
        )
        assert camera.mediamtx_path == "tenant-tenant-1/cam-cam-1"

    def test_mark_online(self):
        camera = Camera(
            id="c1", tenant_id="t1", name="Cam",
            rtsp_url="rtsp://x", manufacturer=CameraManufacturer.GENERIC,
        )
        assert camera.is_online is False
        camera.mark_online()
        assert camera.is_online is True
        assert camera.last_seen_at is not None

    def test_mark_offline(self):
        camera = Camera(
            id="c1", tenant_id="t1", name="Cam",
            rtsp_url="rtsp://x", manufacturer=CameraManufacturer.GENERIC,
        )
        camera.mark_online()
        camera.mark_offline()
        assert camera.is_online is False


class TestAgent:
    """Testes da entidade Agent."""

    def test_create_agent_defaults(self):
        agent = Agent(id="a1", tenant_id="t1", name="Agent 1")
        assert agent.status == AgentStatus.PENDING
        assert agent.streams_running == 0
        assert agent.streams_failed == 0

    def test_mark_online(self):
        agent = Agent(id="a1", tenant_id="t1", name="Agent 1")
        agent.mark_online("1.0.0", 3, 1)
        assert agent.status == AgentStatus.ONLINE
        assert agent.version == "1.0.0"
        assert agent.streams_running == 3
        assert agent.streams_failed == 1
        assert agent.last_heartbeat_at is not None

    def test_mark_offline(self):
        agent = Agent(id="a1", tenant_id="t1", name="Agent 1")
        agent.mark_online("1.0.0", 0, 0)
        agent.mark_offline()
        assert agent.status == AgentStatus.OFFLINE


class TestCameraConfig:
    """Testes do dataclass CameraConfig."""

    def test_create(self):
        config = CameraConfig(
            id="c1", name="Cam", rtsp_url="rtsp://x",
            rtmp_push_url="rtmp://y", enabled=True,
        )
        assert config.enabled is True


class TestEnums:
    """Testes dos enums de câmeras."""

    def test_manufacturers(self):
        assert CameraManufacturer.HIKVISION == "hikvision"
        assert CameraManufacturer.INTELBRAS == "intelbras"
        assert CameraManufacturer.GENERIC == "generic"

    def test_agent_statuses(self):
        assert AgentStatus.PENDING == "pending"
        assert AgentStatus.ONLINE == "online"
        assert AgentStatus.OFFLINE == "offline"
