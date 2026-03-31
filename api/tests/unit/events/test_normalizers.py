"""Testes unitários dos normalizadores ALPR (Hikvision, Intelbras, Genérico)."""
from __future__ import annotations

import pytest

from vms.events.normalizers.base import NormalizerRegistry, registry
from vms.events.normalizers.hikvision import HikvisionNormalizer
from vms.events.normalizers.intelbras import IntelbrasNormalizer
from vms.events.normalizers.generic import GenericNormalizer


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fresh_registry() -> NormalizerRegistry:
    """Registry limpo para testes isolados."""
    reg = NormalizerRegistry()
    reg.register(HikvisionNormalizer())
    reg.register(IntelbrasNormalizer())
    reg.register(GenericNormalizer())
    return reg


CAMERA_ID = "cam-001"
TENANT_ID = "tenant-001"


# ── NormalizerRegistry ────────────────────────────────────────────────────────

class TestNormalizerRegistry:
    """Testes do registro de normalizadores."""

    def test_registry_global_has_hikvision(self):
        """Registro global contém Hikvision (auto-registrado na importação)."""
        assert registry.get("hikvision") is not None

    def test_registry_global_has_intelbras(self):
        """Registro global contém Intelbras."""
        assert registry.get("intelbras") is not None

    def test_registry_global_has_generic(self):
        """Registro global contém Generic."""
        assert registry.get("generic") is not None

    def test_unknown_manufacturer_returns_none(self):
        """Fabricante não registrado retorna None."""
        assert registry.get("desconhecido") is None

    def test_normalize_unknown_manufacturer_raises(self, fresh_registry):
        """Fabricante não suportado lança ValueError."""
        with pytest.raises(ValueError, match="Fabricante não suportado"):
            fresh_registry.normalize("desconhecido", {}, CAMERA_ID, TENANT_ID)


# ── HikvisionNormalizer ──────────────────────────────────────────────────────

class TestHikvisionNormalizer:
    """Testes do normalizador Hikvision ANPR."""

    def test_can_handle_with_anpr_key(self):
        """Reconhece payload com chave 'ANPR'."""
        norm = HikvisionNormalizer()
        assert norm.can_handle({"ANPR": {}}) is True

    def test_cannot_handle_without_anpr_key(self):
        """Rejeita payload sem chave 'ANPR'."""
        norm = HikvisionNormalizer()
        assert norm.can_handle({"plate": "ABC1D23"}) is False

    def test_normalize_valid_payload(self):
        """Normaliza payload Hikvision completo."""
        raw = {
            "ANPR": {"licensePlate": "abc1d23", "confidence": 85},
            "dateTime": "20260330123456",
            "pictureBase64": "base64data",
        }
        result = HikvisionNormalizer().normalize(raw, CAMERA_ID, TENANT_ID)
        assert result.plate == "ABC1D23"
        assert result.confidence == 0.85
        assert result.manufacturer == "hikvision"
        assert result.camera_id == CAMERA_ID
        assert result.tenant_id == TENANT_ID
        assert result.image_b64 == "base64data"
        assert result.timestamp.year == 2026

    def test_normalize_missing_confidence_defaults_zero(self):
        """Confiança ausente assume 0."""
        raw = {"ANPR": {"licensePlate": "XYZ9A00"}, "dateTime": ""}
        result = HikvisionNormalizer().normalize(raw, CAMERA_ID, TENANT_ID)
        assert result.confidence == 0.0

    def test_normalize_invalid_datetime_uses_fallback(self):
        """DateTime inválido usa utcnow() como fallback."""
        raw = {"ANPR": {"licensePlate": "AAA0A00"}, "dateTime": "not-a-date"}
        result = HikvisionNormalizer().normalize(raw, CAMERA_ID, TENANT_ID)
        assert result.timestamp is not None


# ── IntelbrasNormalizer ───────────────────────────────────────────────────────

class TestIntelbrasNormalizer:
    """Testes do normalizador Intelbras ITSCAM."""

    def test_can_handle_with_placa_key(self):
        """Reconhece payload com chave 'placa'."""
        norm = IntelbrasNormalizer()
        assert norm.can_handle({"placa": "ABC1D23"}) is True

    def test_cannot_handle_without_placa_key(self):
        """Rejeita payload sem chave 'placa'."""
        norm = IntelbrasNormalizer()
        assert norm.can_handle({"plate": "ABC1D23"}) is False

    def test_normalize_valid_payload(self):
        """Normaliza payload Intelbras completo."""
        raw = {
            "placa": "xyz9a00",
            "confianca": 0.92,
            "timestamp": "2026-03-30T12:34:56",
            "imagem": "imgdata",
        }
        result = IntelbrasNormalizer().normalize(raw, CAMERA_ID, TENANT_ID)
        assert result.plate == "XYZ9A00"
        assert result.confidence == 0.92
        assert result.manufacturer == "intelbras"
        assert result.image_b64 == "imgdata"
        assert result.timestamp.year == 2026

    def test_normalize_missing_confidence(self):
        """Confiança ausente assume 0."""
        raw = {"placa": "AAA0A00"}
        result = IntelbrasNormalizer().normalize(raw, CAMERA_ID, TENANT_ID)
        assert result.confidence == 0.0

    def test_normalize_invalid_timestamp(self):
        """Timestamp inválido usa fallback."""
        raw = {"placa": "BBB1B11", "timestamp": "garbage"}
        result = IntelbrasNormalizer().normalize(raw, CAMERA_ID, TENANT_ID)
        assert result.timestamp is not None


# ── GenericNormalizer ─────────────────────────────────────────────────────────

class TestGenericNormalizer:
    """Testes do normalizador genérico."""

    def test_can_handle_with_plate_key(self):
        """Reconhece payload com chave 'plate'."""
        norm = GenericNormalizer()
        assert norm.can_handle({"plate": "ABC1D23"}) is True

    def test_cannot_handle_without_plate_key(self):
        """Rejeita payload sem 'plate'."""
        norm = GenericNormalizer()
        assert norm.can_handle({"placa": "ABC1D23"}) is False

    def test_normalize_valid_payload(self):
        """Normaliza payload genérico completo."""
        raw = {
            "plate": "abc1d23",
            "confidence": 0.95,
            "timestamp": "2026-03-30T12:34:56Z",
            "image_b64": "imgdata",
            "bbox": [10.0, 20.0, 100.0, 50.0],
        }
        result = GenericNormalizer().normalize(raw, CAMERA_ID, TENANT_ID)
        assert result.plate == "ABC1D23"
        assert result.confidence == 0.95
        assert result.manufacturer == "generic"
        assert result.image_b64 == "imgdata"
        assert result.bbox == [10.0, 20.0, 100.0, 50.0]

    def test_normalize_without_optional_fields(self):
        """Campos opcionais ficam None."""
        raw = {"plate": "XYZ0A00"}
        result = GenericNormalizer().normalize(raw, CAMERA_ID, TENANT_ID)
        assert result.image_b64 is None
        assert result.bbox is None
        assert result.confidence == 0.0


# ── Registry.normalize integration ───────────────────────────────────────────

class TestRegistryNormalize:
    """Testes de normalização via registry (integração normalizer+registry)."""

    def test_normalize_hikvision_via_registry(self, fresh_registry):
        """Registry delega corretamente para Hikvision."""
        raw = {"ANPR": {"licensePlate": "ABC1D23", "confidence": 90}}
        result = fresh_registry.normalize("hikvision", raw, CAMERA_ID, TENANT_ID)
        assert result.manufacturer == "hikvision"
        assert result.plate == "ABC1D23"

    def test_normalize_intelbras_via_registry(self, fresh_registry):
        """Registry delega corretamente para Intelbras."""
        raw = {"placa": "DEF2E34", "confianca": 0.88}
        result = fresh_registry.normalize("intelbras", raw, CAMERA_ID, TENANT_ID)
        assert result.manufacturer == "intelbras"
        assert result.plate == "DEF2E34"

    def test_normalize_generic_via_registry(self, fresh_registry):
        """Registry delega corretamente para Generic."""
        raw = {"plate": "GHI3F45", "confidence": 0.75}
        result = fresh_registry.normalize("generic", raw, CAMERA_ID, TENANT_ID)
        assert result.manufacturer == "generic"
        assert result.plate == "GHI3F45"
