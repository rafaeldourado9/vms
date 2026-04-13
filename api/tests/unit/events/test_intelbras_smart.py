"""Testes unitários do normalizador de Smart Events Intelbras."""
from __future__ import annotations

import pytest

from vms.events.normalizers.intelbras_smart import (
    EVENT_TYPE_MAP,
    IntelbrasSmartNormalizer,
)


@pytest.fixture
def norm() -> IntelbrasSmartNormalizer:
    return IntelbrasSmartNormalizer()


# ─── Testes: can_handle ────────────────────────────────────────────────────────

class TestCanHandle:
    def test_handles_crossline(self, norm):
        assert norm.can_handle({"event": "CrossLineDetection"})

    def test_handles_intrusion(self, norm):
        assert norm.can_handle({"event": "IntrusionDetection"})

    def test_handles_face_recognition(self, norm):
        assert norm.can_handle({"event": "FaceRecognition"})

    def test_handles_people_counting(self, norm):
        assert norm.can_handle({"event": "PeopleCounting"})

    def test_handles_motion(self, norm):
        assert norm.can_handle({"event": "MotionDetection"})

    def test_handles_video_loss(self, norm):
        assert norm.can_handle({"event": "VideoLoss"})

    def test_does_not_handle_alpr(self, norm):
        # ALPR tem normalizador dedicado
        assert not norm.can_handle({"event": "ALPR"})
        assert not norm.can_handle({"event": "alpr"})

    def test_does_not_handle_generic_event(self, norm):
        assert not norm.can_handle({"some": "data"})
        assert not norm.can_handle({"eventType": "UnknownEvent"})


# ─── Testes: normalize ───────────────────────────────────────────────────────

class TestNormalize:
    def test_normalizes_crossline(self, norm):
        payload = {
            "event": "CrossLineDetection",
            "channel": 1,
            "timestamp": "2026-04-12T10:00:00",
            "data": {"direction": "AtoB"},
        }
        detection = norm.normalize(payload, "cam-1", "tenant-1")
        assert detection.manufacturer == "intelbras_smart"
        assert detection.raw_payload["event"] == "CrossLineDetection"
        assert "direction" in detection.raw_payload.get("data", {})

    def test_normalizes_face_recognition(self, norm):
        payload = {
            "event": "FaceRecognition",
            "person_id": "EMP-001",
            "person_name": "João Silva",
            "similarity": 0.95,
            "access_granted": True,
            "timestamp": "2026-04-12T10:00:00",
        }
        detection = norm.normalize(payload, "cam-1", "tenant-1")
        assert detection.confidence == 0.95
        assert detection.raw_payload["person_id"] == "EMP-001"

    def test_normalizes_people_counting(self, norm):
        payload = {
            "event": "PeopleCounting",
            "enter": 15,
            "exit": 12,
            "current": 3,
            "timestamp": "2026-04-12T10:00:00",
        }
        detection = norm.normalize(payload, "cam-1", "tenant-1")
        assert detection.raw_payload["enter"] == 15
        assert detection.raw_payload["current"] == 3

    def test_normalizes_intrusion(self, norm):
        payload = {
            "event": "IntrusionDetection",
            "data": {"regionId": 1, "sensitivity": 80},
            "timestamp": "2026-04-12T10:00:00",
        }
        detection = norm.normalize(payload, "cam-1", "tenant-1")
        assert detection.raw_payload["data"]["regionId"] == 1


# ─── Testes: Mapeamento ─────────────────────────────────────────────────────

class TestEventMap:
    def test_all_mapped_events_are_valid_vms_types(self):
        for event_type, vms_type in EVENT_TYPE_MAP.items():
            assert "." in vms_type, f"VMS type for {event_type} deve conter ponto: {vms_type}"
            assert vms_type.startswith(("analytics.", "camera.", "motion.", "alarm."))
