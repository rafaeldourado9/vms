"""Casos de uso do bounded context de gravações."""
from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import uuid
from datetime import UTC, datetime, timedelta

from vms.recordings.domain import Clip, RecordingSegment
from vms.recordings.repository import ClipRepositoryPort, RecordingSegmentRepositoryPort
from vms.shared.value_objects import Sha256Hash

logger = logging.getLogger(__name__)

_PATH_RE = re.compile(r"tenant-(?P<tenant_id>[^/]+)/cam-(?P<camera_id>.+)")


async def build_segment_hls(file_path: str) -> str | None:
    """
    Remux a single fMP4 segment to HLS TS chunks using FFmpeg (-c copy, no reencoding).

    Output layout (alongside the original MP4, which is kept for forensics):
        12-00-00.mp4         ← original, untouched
        12-00-00.m3u8        ← per-segment VOD playlist  (created here)
        12-00-00_000.ts      ← 6-second TS chunks        (created here)
        12-00-00_001.ts
        ...

    Returns the .m3u8 path on success, None on failure.
    Idempotent: if the .m3u8 already exists it is returned immediately.
    """
    if not os.path.exists(file_path):
        logger.warning("build_segment_hls: arquivo não encontrado: %s", file_path)
        return None

    stem = file_path[:-4] if file_path.endswith(".mp4") else file_path
    m3u8_path = f"{stem}.m3u8"
    ts_pattern = f"{stem}_%03d.ts"

    if os.path.exists(m3u8_path):
        return m3u8_path

    cmd = [
        "ffmpeg", "-y",
        "-i", file_path,
        "-c", "copy",
        "-f", "hls",
        "-hls_time", "6",
        "-hls_list_size", "0",
        "-hls_segment_type", "mpegts",
        "-hls_segment_filename", ts_pattern,
        "-hls_flags", "independent_segments",
        m3u8_path,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        if proc.returncode != 0:
            logger.error(
                "FFmpeg HLS falhou para %s: %s",
                file_path,
                stderr.decode(errors="replace")[-500:],
            )
            return None
        logger.info("HLS gerado: %s", m3u8_path)
        return m3u8_path
    except asyncio.TimeoutError:
        logger.error("FFmpeg HLS timeout para %s", file_path)
        try:
            proc.kill()
        except Exception:
            pass
        return None
    except Exception:
        logger.exception("Erro ao gerar HLS para %s", file_path)
        return None


def _parse_m3u8_entries(m3u8_path: str) -> list[tuple[float, str]]:
    """
    Parse a per-segment .m3u8 and return [(duration_seconds, ts_path), ...].
    Skips header/footer tags; only returns #EXTINF + URI pairs.
    """
    entries: list[tuple[float, str]] = []
    try:
        with open(m3u8_path) as fh:
            lines = fh.readlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF:"):
                dur = float(line[8:].split(",")[0])
                uri = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if uri and not uri.startswith("#"):
                    entries.append((dur, uri))
                    i += 2
                    continue
            i += 1
    except Exception:
        logger.exception("Falha ao parsear %s", m3u8_path)
    return entries


_LIVE_RE = re.compile(r"live/(?P<stream_key>[^/]+?)(?:\.stream)?$")
_DATETIME_PATH_RE = re.compile(
    r"/(\d{4})/(\d{2})/(\d{2})/(\d{2})-(\d{2})-(\d{2})(?:-\d+)?\.mp4$"
)


class RecordingService:
    """Casos de uso de indexação e gerenciamento de gravações."""

    def __init__(
        self,
        segment_repo: RecordingSegmentRepositoryPort,
        clip_repo: ClipRepositoryPort,
    ) -> None:
        self._segments = segment_repo
        self._clips = clip_repo

    async def index_segment(
        self,
        tenant_id: str,
        camera_id: str,
        file_path: str,
        mediamtx_path: str,
    ) -> RecordingSegment:
        """
        Indexa segmento de gravação.

        Extrai tenant_id/camera_id do mediamtx_path se não fornecidos explicitamente.
        Calcula SHA-256 do arquivo para cadeia de custódia.
        """
        resolved_tenant, resolved_camera = _resolve_ids(
            mediamtx_path, tenant_id, camera_id
        )
        started_at, ended_at, duration, size = _parse_file_metadata(file_path)

        # Calcular SHA-256 se arquivo existe
        sha256_hash = None
        try:
            if os.path.exists(file_path):
                sha256_hash = Sha256Hash.from_file(file_path)
                logger.debug("SHA-256 calculado para segmento: %s", file_path)
        except Exception:
            logger.warning("Falha ao calcular SHA-256 para %s (não crítico)", file_path, exc_info=True)

        segment = RecordingSegment(
            id=str(uuid.uuid4()),
            tenant_id=resolved_tenant,
            camera_id=resolved_camera,
            mediamtx_path=mediamtx_path,
            file_path=file_path,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=duration,
            size_bytes=size,
            sha256_hash=sha256_hash,
        )
        return await self._segments.create(segment)

    async def cleanup_expired_segments(
        self, tenant_id: str, camera_id: str, retention_days: int
    ) -> int:
        """Remove segmentos expirados. Retorna quantidade de registros removidos."""
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        count = await self._segments.delete_older_than(tenant_id, camera_id, cutoff)
        logger.info(
            "Limpeza: %d segmentos removidos — tenant=%s camera=%s retenção=%dd",
            count,
            tenant_id,
            camera_id,
            retention_days,
        )
        return count

    async def prepare_day_hls(
        self,
        tenant_id: str,
        camera_id: str,
        day: datetime,
    ) -> dict | None:
        """
        Prepara metadados pra um playlist HLS-VOD montado pela própria API
        a partir dos fMP4 já gravados em disco.

        O playlist real é servido por `/cameras/{id}/recordings/day-hls.m3u8`
        — um m3u8 estático com #EXTINF por segmento de 60s apontando pros
        arquivos sob `/recordings/...` (servidos pelo nginx com Range).

        Por que não usar o `/mediamtx-playback/get`: o playback server do
        MediaMTX retorna fMP4 concatenado, não HLS. hls.js recebia binário
        no lugar de manifesto e estourava manifestParsingError.
        """
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        if day_start.tzinfo is None:
            day_start = day_start.replace(tzinfo=UTC)
        day_end = day_start + timedelta(days=1)

        segments, _ = await self._segments.list_by_camera(
            tenant_id=tenant_id,
            camera_id=camera_id,
            started_after=day_start,
            started_before=day_end,
            limit=10000,
            offset=0,
        )
        if not segments:
            return None

        segments_sorted = sorted(segments, key=lambda s: s.started_at)
        first = segments_sorted[0]
        last = segments_sorted[-1]

        started_at = first.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
        ended_at = last.ended_at
        if ended_at.tzinfo is None:
            ended_at = ended_at.replace(tzinfo=UTC)

        total_seconds = max(int((ended_at - started_at).total_seconds()), 1)

        date_str = day_start.strftime("%Y-%m-%d")
        playlist_url = f"/api/v1/cameras/{camera_id}/recordings/day-hls.m3u8?date={date_str}"

        intervals = []
        for seg in segments_sorted:
            seg_start = seg.started_at.replace(tzinfo=UTC) if seg.started_at.tzinfo is None else seg.started_at
            seg_end = seg.ended_at.replace(tzinfo=UTC) if seg.ended_at.tzinfo is None else seg.ended_at
            intervals.append({
                "id": seg.id,
                "started_at": seg_start.isoformat(),
                "ended_at": seg_end.isoformat(),
                "duration_seconds": seg.duration_seconds,
            })

        logger.info(
            "Day HLS playlist preparado: camera=%s segments=%d window=%ss",
            camera_id, len(segments_sorted), total_seconds,
        )

        return {
            "hls_url": playlist_url,
            "path_name": first.mediamtx_path,
            "camera_id": camera_id,
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "window_seconds": total_seconds,
            "intervals": intervals,
        }

    async def build_day_playlist(
        self,
        tenant_id: str,
        camera_id: str,
        day: datetime,
    ) -> str | None:
        """
        Monta um playlist HLS-VOD em texto puro a partir dos chunks TS gerados
        por build_segment_hls (FFmpeg remux, sem reencoding).

        Cada segmento de 60s já foi convertido para ~10 chunks de 6s cada.
        Discontinuidades (gaps entre segmentos) são marcadas com
        #EXT-X-DISCONTINUITY para que hls.js resete o demuxer.

        Compatível com hls.js e Safari nativo.
        Retorna None se não há gravações no dia.
        """
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        if day_start.tzinfo is None:
            day_start = day_start.replace(tzinfo=UTC)
        day_end = day_start + timedelta(days=1)

        segments, _ = await self._segments.list_by_camera(
            tenant_id=tenant_id,
            camera_id=camera_id,
            started_after=day_start,
            started_before=day_end,
            limit=10000,
            offset=0,
        )
        if not segments:
            return None

        segments_sorted = sorted(segments, key=lambda s: s.started_at)

        # Ensure TS chunks exist — run all missing conversions in parallel (max 8 concurrent).
        # FFmpeg remux is fast (~0.3s per 60s fMP4), so a typical few-hour window
        # completes in a handful of seconds. A 30s timeout prevents runaway on huge days.
        _sem = asyncio.Semaphore(8)

        async def _ensure_hls(seg: "RecordingSegment") -> None:
            stem = seg.file_path[:-4] if seg.file_path.endswith(".mp4") else seg.file_path
            if os.path.exists(f"{stem}.m3u8"):
                return
            async with _sem:
                await build_segment_hls(seg.file_path)

        try:
            await asyncio.wait_for(
                asyncio.gather(*[_ensure_hls(s) for s in segments_sorted], return_exceptions=True),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Timeout na conversão HLS (30s): dia=%s camera=%s — segmentos sem TS serão omitidos",
                day.date(), camera_id,
            )

        # Collect TS entries for every segment that was successfully converted.
        # ts_dir is stored alongside because FFmpeg writes relative (basename-only)
        # paths in the per-segment m3u8; we resolve them to absolute paths so that
        # hls.js fetches from /recordings/… (nginx static) rather than from the API.
        collected: list[tuple[datetime, datetime, list[tuple[float, str]]]] = []
        for seg in segments_sorted:
            seg_start = seg.started_at.replace(tzinfo=UTC) if seg.started_at.tzinfo is None else seg.started_at
            seg_end   = seg.ended_at.replace(tzinfo=UTC)   if seg.ended_at.tzinfo is None   else seg.ended_at

            stem = seg.file_path[:-4] if seg.file_path.endswith(".mp4") else seg.file_path
            m3u8_path = f"{stem}.m3u8"
            raw_entries = _parse_m3u8_entries(m3u8_path) if os.path.exists(m3u8_path) else []
            if not raw_entries:
                logger.debug("Segmento sem TS disponível, omitido do playlist: %s", seg.file_path)
                continue

            # Resolve relative paths (basename only written by FFmpeg) to absolute paths.
            ts_dir = os.path.dirname(seg.file_path)
            ts_entries = [
                (dur, ts_path if ts_path.startswith("/") else f"{ts_dir}/{ts_path}")
                for dur, ts_path in raw_entries
            ]

            collected.append((seg_start, seg_end, ts_entries))

        if not collected:
            return None

        # #EXT-X-TARGETDURATION = max chunk duration, rounded up
        max_chunk = max(dur for _, _, entries in collected for dur, _ in entries)
        target_dur = max(1, math.ceil(max_chunk))

        lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:7",
            "#EXT-X-PLAYLIST-TYPE:VOD",
            f"#EXT-X-TARGETDURATION:{target_dur}",
            "#EXT-X-INDEPENDENT-SEGMENTS",
            "#EXT-X-MEDIA-SEQUENCE:0",
        ]

        _RECORDINGS_ROOT = "/recordings"

        prev_end: datetime | None = None
        for seg_start, seg_end, ts_entries in collected:
            if prev_end is not None and (seg_start - prev_end).total_seconds() > 1.5:
                lines.append("#EXT-X-DISCONTINUITY")

            lines.append(f"#EXT-X-PROGRAM-DATE-TIME:{seg_start.isoformat()}")
            for dur, ts_path in ts_entries:
                lines.append(f"#EXTINF:{dur:.3f},")
                # Emit API URL so the segment is served authenticated.
                # Token is injected by the router at response time.
                if ts_path.startswith(_RECORDINGS_ROOT + "/"):
                    rel = ts_path[len(_RECORDINGS_ROOT) + 1:]
                    lines.append(f"/api/v1/recordings/segment?path={rel}")
                else:
                    lines.append(ts_path)

            prev_end = seg_end

        lines.append("#EXT-X-ENDLIST")
        return "\n".join(lines) + "\n"

    async def prepare_hls_playback(
        self,
        tenant_id: str,
        recording_id: str,
        mediamtx_client: "MediaMTXClient | None" = None,
    ) -> dict | None:
        """
        Retorna a URL de playback HLS para um segmento gravado usando o servidor
        de playback nativo do MediaMTX (porta 9996).

        O servidor de playback do MediaMTX v1.x agrupa os segmentos fMP4 de um
        path e serve como HLS diretamente, sem precisar de paths dinâmicos com
        source `file://` (que não são suportados via API dinâmica na v1.17).

        URL resultante: /mediamtx-playback/get?path=<mediamtx_path>&start=<ISO>&duration=<s>
        Esta URL é exposta pelo nginx na rota /mediamtx-playback/ → mediamtx:9996.
        """
        from urllib.parse import urlencode

        segment = await self._segments.get_by_id(recording_id, tenant_id)
        if not segment:
            return None

        # Garante timezone-aware para serialização ISO 8601 correta
        started_at = segment.started_at
        if started_at.tzinfo is None:
            from datetime import timezone as _tz
            started_at = started_at.replace(tzinfo=_tz.utc)

        # Monta URL para o playback server nativo do MediaMTX.
        # O servidor agrupa os fMP4 pela sessão de gravação e serve como HLS.
        # IMPORTANTE: MediaMTX espera `duration` como Go duration string (ex: "60s"),
        # não como número float. Passar um float nu causa o erro:
        #   "invalid duration: time: invalid duration \"\""
        duration_secs = int(segment.duration_seconds) if segment.duration_seconds else 60
        go_duration = f"{duration_secs}s"

        qs = urlencode({
            "path": segment.mediamtx_path,
            "start": started_at.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
            "duration": go_duration,
        })
        playback_url = f"/mediamtx-playback/get?{qs}"

        logger.info(
            "Playback URL gerada via playback server: recording=%s path=%s start=%s",
            recording_id,
            segment.mediamtx_path,
            started_at.isoformat(),
        )

        return {
            "hls_url": playback_url,
            "path_name": segment.mediamtx_path,
            "recording_id": recording_id,
            "camera_id": segment.camera_id,
            "started_at": started_at.isoformat(),
            "duration_seconds": segment.duration_seconds,
        }

    async def create_clip(
        self,
        tenant_id: str,
        camera_id: str,
        starts_at: datetime,
        ends_at: datetime,
        vms_event_id: str | None = None,
    ) -> Clip:
        """Cria solicitação de clipe. O processamento ocorre via tarefa background."""
        clip = Clip(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            camera_id=camera_id,
            starts_at=starts_at,
            ends_at=ends_at,
            vms_event_id=vms_event_id,
        )
        return await self._clips.create(clip)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_ids(
    mediamtx_path: str,
    tenant_id: str,
    camera_id: str,
) -> tuple[str, str]:
    """
    Extrai IDs do path MediaMTX se não fornecidos.

    Suporta dois formatos:
    - tenant-{tid}/cam-{cid}  → extrai tenant_id e camera_id diretamente
    - live/{stream_key}       → IDs devem ser fornecidos explicitamente (pelo webhook)
    """
    if tenant_id and camera_id:
        return tenant_id, camera_id
    match = _PATH_RE.match(mediamtx_path)
    if match:
        return match.group("tenant_id"), match.group("camera_id")
    return tenant_id, camera_id


def _parse_file_metadata(
    file_path: str,
) -> tuple[datetime, datetime, float, int]:
    """Extrai metadados básicos do arquivo de segmento.

    Parseia o timestamp real do path MediaMTX: /YYYY/MM/DD/HH-MM-SS.mp4
    Corrige double extension (.mp4.mp4) se presente.
    Garante path absoluto com leading slash.
    """
    now = datetime.now(UTC)
    size = 0
    duration = 60.0

    # Corrige double extension: MediaMTX às vezes adiciona .mp4 extra
    if file_path.endswith(".mp4.mp4"):
        file_path = file_path[:-4]

    # Garante path absoluto
    if not file_path.startswith("/"):
        file_path = f"/{file_path}"

    try:
        stat = os.stat(file_path)
        size = stat.st_size
    except OSError:
        pass

    # Parseia timestamp do path: /recordings/tenant-X/cam-Y/YYYY/MM/DD/HH-MM-SS.mp4
    m = _DATETIME_PATH_RE.search(file_path)
    if m:
        y, mo, d, h, mi, s = map(int, m.groups())
        started_at = datetime(y, mo, d, h, mi, s, tzinfo=UTC)
        ended_at = started_at + timedelta(seconds=duration)
    else:
        started_at = now - timedelta(seconds=duration)
        ended_at = now

    return started_at, ended_at, duration, size
