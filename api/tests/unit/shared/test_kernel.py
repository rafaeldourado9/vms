"""
Testes unitários do Shared Kernel.

Cobre: EntityId, Entity, AggregateRoot, DomainEvent, ValueObject,
       Clock, Coordinates, IpAddress, TimeRange, Confidence, Sha256Hash,
       Domain Exceptions.

Estrutura: Given-When-Then (AAA)
"""
from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from vms.shared.clock import FakeClock, RealClock
from vms.shared.events import DomainEvent
from vms.shared.exceptions import (
    BusinessRuleViolation,
    DomainError,
    DuplicateError,
    IntegrityError,
    NotFoundError,
    StateTransitionError,
    UnauthorizedError,
)
from vms.shared.kernel import (
    AggregateRoot,
    AuditId,
    BillingId,
    CameraId,
    Entity,
    EntityId,
    EventId,
    PluginId,
    RecordingId,
    ReportId,
    Repository,
    TenantId,
    UserId,
    VODStreamId,
)
from vms.shared.value_objects import (
    Confidence,
    Coordinates,
    IpAddress,
    Sha256Hash,
    TimeRange,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_clock() -> FakeClock:
    """Clock fixo para testes determinísticos."""
    return FakeClock(datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc))


# ─── Testes: EntityId ────────────────────────────────────────────────────────

class TestEntityId:
    """Testes de EntityId e subclasses."""

    def test_new_id_is_unique(self):
        # Given
        id1 = EntityId.new()
        id2 = EntityId.new()

        # Then
        assert id1 != id2

    def test_id_from_string(self):
        # Given
        uuid_str = str(uuid4())

        # When
        entity_id = EntityId.from_string(uuid_str)

        # Then
        assert str(entity_id.value) == uuid_str

    def test_equality_same_type(self):
        # Given
        uuid_val = uuid4()
        id1 = EntityId(uuid_val)
        id2 = EntityId(uuid_val)

        # Then
        assert id1 == id2

    def test_equality_different_type(self):
        # Given
        uuid_val = uuid4()
        camera_id = CameraId(uuid_val)
        tenant_id = TenantId(uuid_val)

        # Then
        assert camera_id == tenant_id  # Ambos são EntityId com mesmo UUID

    def test_string_representation(self):
        # Given
        camera_id = CameraId.new()

        # Then
        assert str(camera_id) == str(camera_id.value)

    def test_hash_consistency(self):
        # Given
        id1 = EntityId.new()
        id2 = EntityId(id1.value)

        # Then
        assert hash(id1) == hash(id2)

    def test_id_subclasses_are_distinct(self):
        # Given/When
        camera = CameraId.new()
        tenant = TenantId.new()
        user = UserId.new()
        event = EventId.new()
        audit = AuditId.new()
        recording = RecordingId.new()
        vod = VODStreamId.new()
        plugin = PluginId.new()
        report = ReportId.new()
        billing = BillingId.new()

        # Then
        ids = [camera, tenant, user, event, audit, recording, vod, plugin, report, billing]
        assert len(set(str(i) for i in ids)) == len(ids)  # Todos únicos


# ─── Testes: Entity ──────────────────────────────────────────────────────────

class TestEntity:
    """Testes de Entity base."""

    def test_equality_by_id(self):
        # Given
        id1 = CameraId.new()
        id2 = CameraId.new()

        # Entity equality is by ID only (not by all fields)
        @dataclass
        class TestEntity(Entity):
            id: CameraId
            name: str = "default"

        entity1 = TestEntity(id=id1, name="Camera 1")
        entity1_copy = TestEntity(id=id1, name="Camera 2")  # Same ID, different name
        entity2 = TestEntity(id=id2, name="Camera 1")  # Different ID

        # Then - Entity equality is by ID only
        assert entity1.id == entity1_copy.id  # Same ID
        assert entity1.id != entity2.id  # Different ID

    def test_hash_by_id(self):
        # Given
        id1 = CameraId.new()

        class TestEntity(Entity):
            id: CameraId

        entity1 = TestEntity(id=id1)
        entity1_copy = TestEntity(id=id1)

        # Then
        assert hash(entity1) == hash(entity1_copy)


# ─── Testes: AggregateRoot ───────────────────────────────────────────────────

class TestAggregateRoot:
    """Testes de AggregateRoot."""

    def test_record_and_pull_events(self):
        # Given
        @dataclass(frozen=True, kw_only=True)
        class TestEvent(DomainEvent):
            entity_id: EntityId | None = None

        entity_id = EntityId.new()

        @dataclass
        class TestAggregate(AggregateRoot):
            id: EntityId

            def do_something(self) -> None:
                self.record_event(TestEvent(entity_id=self.id))

        aggregate = TestAggregate(id=entity_id)

        # When
        aggregate.do_something()
        aggregate.do_something()
        events = aggregate.pull_events()

        # Then
        assert len(events) == 2
        assert all(isinstance(e, TestEvent) for e in events)
        assert aggregate.has_pending_events is False

    def test_pull_events_clears_list(self):
        # Given
        class TestEvent(DomainEvent):
            pass

        class TestAggregate(AggregateRoot):
            id: EntityId

            def trigger(self) -> None:
                self.record_event(TestEvent())

        aggregate = TestAggregate(id=EntityId.new())
        aggregate.trigger()

        # When
        events1 = aggregate.pull_events()
        events2 = aggregate.pull_events()

        # Then
        assert len(events1) == 1
        assert len(events2) == 0

    def test_clear_events_without_pull(self):
        # Given
        class TestEvent(DomainEvent):
            pass

        class TestAggregate(AggregateRoot):
            id: EntityId

            def trigger(self) -> None:
                self.record_event(TestEvent())

        aggregate = TestAggregate(id=EntityId.new())
        aggregate.trigger()
        aggregate.trigger()

        # When
        aggregate.clear_events()

        # Then
        assert aggregate.pending_events_count == 0

    def test_has_pending_events(self):
        # Given
        class TestEvent(DomainEvent):
            pass

        class TestAggregate(AggregateRoot):
            id: EntityId

            def trigger(self) -> None:
                self.record_event(TestEvent())

        aggregate = TestAggregate(id=EntityId.new())

        # Then (initially)
        assert aggregate.has_pending_events is False

        # When
        aggregate.trigger()

        # Then
        assert aggregate.has_pending_events is True
        assert aggregate.pending_events_count == 1


# ─── Testes: DomainEvent ─────────────────────────────────────────────────────

class TestDomainEvent:
    """Testes de DomainEvent."""

    def test_event_type_from_class_name(self):
        # Given
        class CameraCreated(DomainEvent):
            pass

        # Then
        event = CameraCreated()
        assert event.event_type == "CameraCreated"

    def test_to_dict_serialization(self, fake_clock: FakeClock):
        # Given
        @dataclass(frozen=True, kw_only=True)
        class TestEvent(DomainEvent):
            camera_id: EntityId | None = None
            name: str = ""

        camera_id = EntityId.new()
        event = TestEvent(camera_id=camera_id, name="Test Camera")

        # When
        data = event.to_dict()

        # Then
        assert data["event_type"] == "TestEvent"
        # camera_id is serialized as dict by asdict()
        assert data["camera_id"]["value"] == camera_id.value
        assert data["name"] == "Test Camera"
        # occurred_at is auto-generated, just check it exists and is ISO string
        assert "occurred_at" in data
        assert isinstance(data["occurred_at"], datetime)

    def test_from_dict_deserialization(self):
        # Given
        @dataclass(frozen=True, kw_only=True)
        class TestEvent(DomainEvent):
            value: int = 0

        original = TestEvent(value=42)
        data = original.to_dict()

        # When
        restored = TestEvent.from_dict(data)

        # Then
        assert restored.value == 42

    def test_event_is_immutable(self):
        # Given
        @dataclass(frozen=True, kw_only=True)
        class TestEvent(DomainEvent):
            value: int = 0

        event = TestEvent(value=10)

        # Then
        with pytest.raises(Exception):
            event.value = 20  # type: ignore


# ─── Testes: Clock ───────────────────────────────────────────────────────────

class TestClock:
    """Testes de Clock abstraction."""

    def test_real_clock_returns_utc(self):
        # Given
        clock = RealClock()

        # When
        now = clock.now()

        # Then
        assert now.tzinfo == timezone.utc

    def test_fake_clock_returns_fixed_time(self):
        # Given
        fixed = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        clock = FakeClock(fixed)

        # When
        now = clock.now()

        # Then
        assert now == fixed

    def test_fake_clock_advance(self):
        # Given
        fixed = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        clock = FakeClock(fixed)

        # When
        clock.advance(hours=1, minutes=30)

        # Then
        expected = datetime(2026, 4, 12, 11, 30, 0, tzinfo=timezone.utc)
        assert clock.now() == expected

    def test_fake_clock_set(self):
        # Given
        clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
        new_time = datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

        # When
        clock.set(new_time)

        # Then
        assert clock.now() == new_time

    def test_fake_clock_adds_timezone_if_missing(self):
        # Given
        naive_time = datetime(2026, 4, 12, 10, 0, 0)  # Sem timezone
        clock = FakeClock(naive_time)

        # When
        now = clock.now()

        # Then
        assert now.tzinfo == timezone.utc


# ─── Testes: Coordinates ─────────────────────────────────────────────────────

class TestCoordinates:
    """Testes de Coordinates Value Object."""

    def test_valid_coordinates(self):
        # Given/When
        coords = Coordinates(Decimal("-23.5505"), Decimal("-46.6333"))

        # Then
        assert coords.latitude == Decimal("-23.5505")
        assert coords.longitude == Decimal("-46.6333")

    def test_invalid_latitude_too_high(self):
        # Then
        with pytest.raises(ValueError, match="Latitude inválida"):
            Coordinates(Decimal("91.0"), Decimal("0.0"))

    def test_invalid_latitude_too_low(self):
        # Then
        with pytest.raises(ValueError, match="Latitude inválida"):
            Coordinates(Decimal("-91.0"), Decimal("0.0"))

    def test_invalid_longitude_too_high(self):
        # Then
        with pytest.raises(ValueError, match="Longitude inválida"):
            Coordinates(Decimal("0.0"), Decimal("181.0"))

    def test_invalid_longitude_too_low(self):
        # Then
        with pytest.raises(ValueError, match="Longitude inválida"):
            Coordinates(Decimal("0.0"), Decimal("-181.0"))

    def test_brazil_center(self):
        # When
        coords = Coordinates.brazil_center()

        # Then
        assert coords.latitude == Decimal("-14.2350")
        assert coords.longitude == Decimal("-51.9253")

    def test_distance_to(self):
        # Given
        sao_paulo = Coordinates(Decimal("-23.5505"), Decimal("-46.6333"))
        rio = Coordinates(Decimal("-22.9068"), Decimal("-43.1729"))

        # When
        distance = sao_paulo.distance_to(rio)

        # Then (distância aproximada SP-Rio é ~350km)
        assert 300 < distance < 400

    def test_string_representation(self):
        # Given
        coords = Coordinates(Decimal("-23.5505"), Decimal("-46.6333"))

        # Then
        assert str(coords) == "-23.5505, -46.6333"

    def test_equality(self):
        # Given
        coords1 = Coordinates(Decimal("-23.5505"), Decimal("-46.6333"))
        coords2 = Coordinates(Decimal("-23.5505"), Decimal("-46.6333"))
        coords3 = Coordinates(Decimal("-22.9068"), Decimal("-43.1729"))

        # Then
        assert coords1 == coords2
        assert coords1 != coords3


# ─── Testes: IpAddress ───────────────────────────────────────────────────────

class TestIpAddress:
    """Testes de IpAddress Value Object."""

    def test_valid_ipv4(self):
        # Given/When
        ip = IpAddress("192.168.1.100")

        # Then
        assert ip.value == "192.168.1.100"

    def test_invalid_ipv4_octet(self):
        # Then
        with pytest.raises(ValueError, match="Octeto IPv4 inválido"):
            IpAddress("192.168.1.256")

    def test_private_ip(self):
        # Given/When
        ip = IpAddress("192.168.1.1")

        # Then
        assert ip.is_private is True

    def test_public_ip(self):
        # Given/When
        ip = IpAddress("8.8.8.8")

        # Then
        assert ip.is_private is False

    def test_localhost(self):
        # Given/When
        ip = IpAddress("127.0.0.1")

        # Then
        assert ip.is_localhost is True
        assert ip.is_private is True

    def test_string_representation(self):
        # Given
        ip = IpAddress("10.0.0.1")

        # Then
        assert str(ip) == "10.0.0.1"


# ─── Testes: TimeRange ───────────────────────────────────────────────────────

class TestTimeRange:
    """Testes de TimeRange Value Object."""

    def test_valid_range(self, fake_clock: FakeClock):
        # Given
        start = fake_clock.now()
        end = start + timedelta(hours=1)

        # When
        time_range = TimeRange(start, end)

        # Then
        assert time_range.duration_seconds == 3600.0
        assert time_range.duration_minutes == 60.0

    def test_invalid_range_end_before_start(self):
        # Given
        start = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        end = start - timedelta(hours=1)

        # Then
        with pytest.raises(ValueError, match="end deve ser posterior a start"):
            TimeRange(start, end)

    def test_contains_true(self, fake_clock: FakeClock):
        # Given
        start = fake_clock.now()
        end = start + timedelta(hours=1)
        time_range = TimeRange(start, end)
        mid = start + timedelta(minutes=30)

        # Then
        assert time_range.contains(mid) is True

    def test_contains_false(self, fake_clock: FakeClock):
        # Given
        start = fake_clock.now()
        end = start + timedelta(hours=1)
        time_range = TimeRange(start, end)
        outside = end + timedelta(hours=1)

        # Then
        assert time_range.contains(outside) is False

    def test_overlaps_true(self, fake_clock: FakeClock):
        # Given
        range1 = TimeRange(fake_clock.now(), fake_clock.now() + timedelta(hours=2))
        fake_clock.advance(hours=1)
        range2 = TimeRange(fake_clock.now(), fake_clock.now() + timedelta(hours=2))

        # Then
        assert range1.overlaps(range2) is True

    def test_overlaps_false(self, fake_clock: FakeClock):
        # Given
        range1 = TimeRange(fake_clock.now(), fake_clock.now() + timedelta(hours=1))
        fake_clock.advance(hours=2)
        range2 = TimeRange(fake_clock.now(), fake_clock.now() + timedelta(hours=1))

        # Then
        assert range1.overlaps(range2) is False

    def test_merge(self, fake_clock: FakeClock):
        # Given
        start1 = fake_clock.now()
        end1 = start1 + timedelta(hours=2)
        fake_clock.advance(hours=1)
        start2 = fake_clock.now()
        end2 = start2 + timedelta(hours=2)

        range1 = TimeRange(start1, end1)
        range2 = TimeRange(start2, end2)

        # When
        merged = range1.merge(range2)

        # Then
        assert merged.start == start1
        assert merged.end == end2

    def test_merge_no_overlap_raises(self):
        # Given
        range1 = TimeRange(
            datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 12, 11, 0, 0, tzinfo=timezone.utc),
        )
        range2 = TimeRange(
            datetime(2026, 4, 12, 13, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 12, 14, 0, 0, tzinfo=timezone.utc),
        )

        # Then
        with pytest.raises(ValueError, match="não se sobrepõem"):
            range1.merge(range2)


# ─── Testes: Confidence ──────────────────────────────────────────────────────

class TestConfidence:
    """Testes de Confidence Value Object."""

    def test_valid_confidence(self):
        # Given/When
        conf = Confidence(0.95)

        # Then
        assert conf.value == 0.95
        assert float(conf) == 0.95

    def test_invalid_confidence_too_high(self):
        # Then
        with pytest.raises(ValueError, match="entre 0 e 1"):
            Confidence(1.5)

    def test_invalid_confidence_too_low(self):
        # Then
        with pytest.raises(ValueError, match="entre 0 e 1"):
            Confidence(-0.1)

    def test_is_high(self):
        # Then
        assert Confidence(0.8).is_high is True
        assert Confidence(0.9).is_high is True
        assert Confidence(0.79).is_high is False

    def test_is_medium(self):
        # Then
        assert Confidence(0.5).is_medium is True
        assert Confidence(0.7).is_medium is True
        assert Confidence(0.49).is_medium is False
        assert Confidence(0.8).is_medium is False

    def test_is_low(self):
        # Then
        assert Confidence(0.3).is_low is True
        assert Confidence(0.49).is_low is True
        assert Confidence(0.5).is_low is False

    def test_meets_threshold(self):
        # Given
        conf = Confidence(0.75)

        # Then
        assert conf.meets_threshold(0.7) is True
        assert conf.meets_threshold(0.8) is False

    def test_string_representation(self):
        # Given
        conf = Confidence(0.95)

        # Then
        assert str(conf) == "95.00%"


# ─── Testes: Sha256Hash ──────────────────────────────────────────────────────

class TestSha256Hash:
    """Testes de Sha256Hash Value Object."""

    def test_valid_hash(self):
        # Given
        hash_str = "a" * 64

        # When
        file_hash = Sha256Hash(hash_str)

        # Then
        assert file_hash.value == hash_str

    def test_invalid_hash_length(self):
        # Then
        with pytest.raises(ValueError, match="deve ter 64 caracteres"):
            Sha256Hash("abc123")

    def test_invalid_hash_characters(self):
        # Then
        with pytest.raises(ValueError, match="hexadecimais"):
            Sha256Hash("g" * 64)

    def test_from_bytes(self):
        # Given
        data = b"hello world"

        # When
        file_hash = Sha256Hash.from_bytes(data)

        # Then
        expected = hashlib.sha256(data).hexdigest()
        assert file_hash.value == expected

    def test_from_file(self):
        # Given
        content = b"test file content"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as f:
            f.write(content)
            temp_path = f.name

        try:
            # When
            file_hash = Sha256Hash.from_file(temp_path)

            # Then
            expected = hashlib.sha256(content).hexdigest()
            assert file_hash.value == expected
        finally:
            Path(temp_path).unlink()

    def test_verify_file_valid(self):
        # Given
        content = b"verify this content"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as f:
            f.write(content)
            temp_path = f.name

        try:
            file_hash = Sha256Hash.from_bytes(content)

            # When
            is_valid = file_hash.verify_file(temp_path)

            # Then
            assert is_valid is True
        finally:
            Path(temp_path).unlink()

    def test_verify_file_tampered(self):
        # Given
        original_content = b"original content"
        tampered_content = b"tampered content"

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as f:
            f.write(original_content)
            temp_path = f.name

        try:
            file_hash = Sha256Hash.from_bytes(original_content)

            # Tamper the file
            with open(temp_path, "wb") as f:
                f.write(tampered_content)

            # When
            is_valid = file_hash.verify_file(temp_path)

            # Then
            assert is_valid is False
        finally:
            Path(temp_path).unlink()

    def test_string_representation(self):
        # Given
        hash_str = "abc123" + "0" * 58
        file_hash = Sha256Hash(hash_str)

        # Then
        assert str(file_hash) == hash_str

    def test_repr_truncates(self):
        # Given
        hash_str = "a" * 64
        file_hash = Sha256Hash(hash_str)

        # Then
        repr_str = repr(file_hash)
        assert "..." in repr_str
        assert len(repr_str) < 64  # Deve ser truncado


# ─── Testes: Domain Exceptions ───────────────────────────────────────────────

class TestDomainExceptions:
    """Testes de exceções de domínio."""

    def test_domain_error_with_details(self):
        # Given/When
        error = BusinessRuleViolation(
            "Câmera inativa não pode ter analytics",
            details={"camera_id": "123"},
        )

        # Then
        assert error.message == "Câmera inativa não pode ter analytics"
        assert error.details == {"camera_id": "123"}
        assert "camera_id" in str(error)

    def test_domain_error_without_details(self):
        # Given/When
        error = NotFoundError("Câmera não encontrada")

        # Then
        assert error.message == "Câmera não encontrada"
        assert error.details == {}

    def test_all_exception_subclasses(self):
        # Given/When/Then
        assert issubclass(NotFoundError, DomainError)
        assert issubclass(BusinessRuleViolation, DomainError)
        assert issubclass(UnauthorizedError, DomainError)
        assert issubclass(IntegrityError, DomainError)
        assert issubclass(DuplicateError, DomainError)
        assert issubclass(StateTransitionError, DomainError)
