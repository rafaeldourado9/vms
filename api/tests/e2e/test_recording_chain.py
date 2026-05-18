"""E2E: pipeline gravação → day-HLS (Sprint α.5).

Requer: docker-compose up (PostgreSQL, Redis, API, MediaMTX).
Rodar com: make test-e2e
           pytest tests/e2e/test_recording_chain.py -v

O teste NÃO precisa de ffmpeg real — simula o webhook segment_ready que o
MediaMTX enviaria após gravar 60s de stream. Isso permite rodar o E2E em CI
sem precisar de câmera ou stream RTMP real.

Para testar com RTMP real:
    ffmpeg -re -f lavfi -i testsrc=size=1280x720:rate=25 \\
           -c:v libx264 -preset ultrafast -f flv \\
           rtmp://localhost:1935/live/<stream_key>
"""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import httpx
import pytest


pytestmark = pytest.mark.e2e


def _fake_segment_path(tenant_id: str, camera_id: str, dt: datetime) -> str:
    """Gera path de segmento no formato que o MediaMTX produz.

    O _DATETIME_PATH_RE do service espera: /YYYY/MM/DD/HH-MM-SS.mp4
    """
    ts = dt.strftime("%H-%M-%S")
    return (
        f"/recordings/tenant-{tenant_id}/cam-{camera_id}"
        f"/{dt.year}/{dt.month:02d}/{dt.day:02d}/{ts}.mp4"
    )


class TestRecordingChain:
    """Pipeline completo: segment_ready → índice → day-HLS playlist."""

    async def test_segment_indexed_via_webhook(
        self, e2e_client: httpx.AsyncClient, e2e_data: dict
    ):
        """Webhook segment_ready indexa o segmento no banco."""
        now = datetime.now(UTC)
        seg_path = _fake_segment_path(e2e_data["tenant_id"], e2e_data["camera_id"], now)

        resp = await e2e_client.post(
            "/api/v1/webhooks/mediamtx/segment_ready",
            json={
                "path": e2e_data["mediamtx_path"],
                "segment_path": seg_path,
            },
        )
        assert resp.status_code == 200, f"segment_ready falhou: {resp.text}"
        assert resp.json().get("ok") is True

    async def test_day_hls_contains_indexed_segment(
        self, e2e_client: httpx.AsyncClient, e2e_data: dict
    ):
        """Segmento indexado aparece no playlist day-HLS do dia."""
        now = datetime.now(UTC)
        seg_path = _fake_segment_path(e2e_data["tenant_id"], e2e_data["camera_id"], now)

        # 1. Indexa o segmento via webhook
        idx_resp = await e2e_client.post(
            "/api/v1/webhooks/mediamtx/segment_ready",
            json={"path": e2e_data["mediamtx_path"], "segment_path": seg_path},
        )
        assert idx_resp.status_code == 200

        # 2. Solicita o playlist day-HLS
        playlist_resp = await e2e_client.get(
            f"/api/v1/cameras/{e2e_data['camera_id']}/recordings/day-hls.m3u8",
            params={"date": now.strftime("%Y-%m-%d"), "token": e2e_data["token"]},
        )
        assert playlist_resp.status_code == 200, f"day-hls.m3u8 falhou: {playlist_resp.text}"

        body = playlist_resp.text
        assert seg_path in body, f"Segmento {seg_path} não encontrado no playlist:\n{body}"

    async def test_day_hls_m3u8_format_valid(
        self, e2e_client: httpx.AsyncClient, e2e_data: dict
    ):
        """Playlist day-HLS está no formato m3u8 correto (RFC 8216)."""
        now = datetime.now(UTC)
        seg_path = _fake_segment_path(e2e_data["tenant_id"], e2e_data["camera_id"], now)

        await e2e_client.post(
            "/api/v1/webhooks/mediamtx/segment_ready",
            json={"path": e2e_data["mediamtx_path"], "segment_path": seg_path},
        )

        resp = await e2e_client.get(
            f"/api/v1/cameras/{e2e_data['camera_id']}/recordings/day-hls.m3u8",
            params={"date": now.strftime("%Y-%m-%d"), "token": e2e_data["token"]},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/vnd.apple.mpegurl")

        body = resp.text
        assert body.startswith("#EXTM3U"), "Playlist não começa com #EXTM3U"
        assert "#EXT-X-VERSION:7" in body
        assert "#EXT-X-PLAYLIST-TYPE:VOD" in body
        assert re.search(r"#EXT-X-TARGETDURATION:\d+", body)
        assert "#EXTINF:" in body
        assert "#EXT-X-ENDLIST" in body
        assert "#EXT-X-PROGRAM-DATE-TIME:" in body

    async def test_day_hls_redis_cache(
        self, e2e_client: httpx.AsyncClient, e2e_data: dict
    ):
        """Segundo request ao mesmo playlist retorna X-Cache: HIT (cache Redis)."""
        now = datetime.now(UTC)
        seg_path = _fake_segment_path(e2e_data["tenant_id"], e2e_data["camera_id"], now)
        date_str = now.strftime("%Y-%m-%d")
        url = f"/api/v1/cameras/{e2e_data['camera_id']}/recordings/day-hls.m3u8"
        params = {"date": date_str, "token": e2e_data["token"]}

        await e2e_client.post(
            "/api/v1/webhooks/mediamtx/segment_ready",
            json={"path": e2e_data["mediamtx_path"], "segment_path": seg_path},
        )

        first = await e2e_client.get(url, params=params)
        assert first.status_code == 200
        assert first.headers.get("x-cache") == "MISS"

        second = await e2e_client.get(url, params=params)
        assert second.status_code == 200
        assert second.headers.get("x-cache") == "HIT"
        assert first.text == second.text

    async def test_day_hls_discontinuity_on_gap(
        self, e2e_client: httpx.AsyncClient, e2e_data: dict
    ):
        """Dois segmentos com gap > 1.5s geram #EXT-X-DISCONTINUITY no playlist."""
        base = datetime.now(UTC).replace(hour=6, minute=0, second=0, microsecond=0)
        seg1 = _fake_segment_path(e2e_data["tenant_id"], e2e_data["camera_id"], base)
        # gap de 5 minutos → bien mayor que 1.5s
        seg2 = _fake_segment_path(
            e2e_data["tenant_id"], e2e_data["camera_id"], base + timedelta(minutes=5, seconds=1)
        )

        for seg in (seg1, seg2):
            resp = await e2e_client.post(
                "/api/v1/webhooks/mediamtx/segment_ready",
                json={"path": e2e_data["mediamtx_path"], "segment_path": seg},
            )
            assert resp.status_code == 200

        playlist = await e2e_client.get(
            f"/api/v1/cameras/{e2e_data['camera_id']}/recordings/day-hls.m3u8",
            params={"date": base.strftime("%Y-%m-%d"), "token": e2e_data["token"]},
        )
        assert playlist.status_code == 200
        assert "#EXT-X-DISCONTINUITY" in playlist.text, (
            f"#EXT-X-DISCONTINUITY ausente:\n{playlist.text}"
        )

    async def test_day_hls_not_found_without_segments(
        self, e2e_client: httpx.AsyncClient, e2e_data: dict
    ):
        """Câmera sem gravações retorna 404."""
        yesterday = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")
        resp = await e2e_client.get(
            f"/api/v1/cameras/{e2e_data['camera_id']}/recordings/day-hls.m3u8",
            params={"date": yesterday, "token": e2e_data["token"]},
        )
        assert resp.status_code == 404

    async def test_day_hls_invalid_token_rejected(
        self, e2e_client: httpx.AsyncClient, e2e_data: dict
    ):
        """Token inválido retorna 401."""
        resp = await e2e_client.get(
            f"/api/v1/cameras/{e2e_data['camera_id']}/recordings/day-hls.m3u8",
            params={"date": "2026-04-29", "token": "token-invalido"},
        )
        assert resp.status_code == 401
