/**
 * RecordingsPage — NVR playback.
 *
 * HLS flow (novo):
 *   1. On camera/date change → GET /cameras/{id}/recordings/day-hls?date=...
 *      Retorna UMA url HLS do playback server cobrindo toda a janela do dia.
 *   2. RecordingPlayer carrega o .m3u8 com hls.js. MediaMTX costura os fMP4
 *      internamente — nenhum reload ao passar de um segmento para outro.
 *   3. User seeks via DayProgressTimeline: video.currentTime seek direto,
 *      zero novas requisições (hls.js baixa só o chunk necessário).
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, FileSearch, ShieldCheck, VideoOff } from 'lucide-react'
import { camerasService } from '@/services/cameras'
import { recordingsService } from '@/services/recordings'
import { useAuthStore } from '@/store/authStore'
import { RecordingPlayer } from '@/components/camera/RecordingPlayer'
import { DayProgressTimeline, type DayInterval } from '@/components/camera/DayProgressTimeline'
import { CustodyChainViewer } from '@/components/recordings/CustodyChainViewer'
import { ForensicExportModal } from '@/components/recordings/ForensicExportModal'
import { Modal } from '@/components/ui/Modal'
import type { Camera, RecordingSegment } from '@/types'
import type { CustodyChainResult } from '@/services/recordings'
import toast from 'react-hot-toast'

// ── Helpers ────────────────────────────────────────────────────────────────────

function shiftDate(iso: string, days: number): string {
  const d = new Date(iso)
  d.setDate(d.getDate() + days)
  return d.toISOString().split('T')[0]
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function fmtDate(iso: string) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('pt-BR', {
    day: '2-digit', month: 'short', year: 'numeric',
  })
}

function fmtDuration(seconds: number) {
  if (seconds < 60) return `${Math.round(seconds)}s`
  return `${Math.round(seconds / 60)}m`
}

// ── Component ──────────────────────────────────────────────────────────────────

export function RecordingsPage() {
  const [searchParams] = useSearchParams()
  const initCameraId   = searchParams.get('camera_id')
  const initDate       = searchParams.get('date')

  const token = useAuthStore((s) => s.tokens?.access_token ?? '')

  const [cameras,  setCameras ] = useState<Camera[]>([])
  const [selCam,   setSelCam  ] = useState<Camera | null>(null)
  const [selDate,  setSelDate ] = useState(() => initDate ?? new Date().toISOString().split('T')[0])

  // Day HLS state — uma URL cobrindo o dia inteiro
  const [hlsUrl,         setHlsUrl        ] = useState<string | null>(null)
  const [windowStartMs,  setWindowStartMs ] = useState<number>(0)
  const [windowEndMs,    setWindowEndMs   ] = useState<number>(0)
  const [intervals,      setIntervals     ] = useState<DayInterval[]>([])
  const [loading,        setLoading       ] = useState(false)
  const [error,          setError         ] = useState<string | null>(null)

  // Playhead (sincronizado com o player)
  const [playheadMs, setPlayheadMs] = useState<number>(() => Date.now())
  const [seekToMs,   setSeekToMs  ] = useState<number | undefined>(undefined)
  const [playing,    setPlaying   ] = useState(false)

  // Segmentos (só para os atalhos de integridade/forense do badge atual)
  const [segments, setSegments] = useState<RecordingSegment[]>([])
  const currentSeg = useMemo(() => {
    return segments.find((s) => {
      const s0 = new Date(s.started_at).getTime()
      const s1 = new Date(s.ended_at).getTime()
      return playheadMs >= s0 && playheadMs <= s1
    }) ?? null
  }, [segments, playheadMs])

  // Cadeia de Custódia
  const [showCustody,    setShowCustody   ] = useState(false)
  const [custodyData,    setCustodyData   ] = useState<CustodyChainResult | null>(null)
  const [custodyLoading, setCustodyLoading] = useState(false)
  const [showForensic,   setShowForensic  ] = useState(false)
  const [forensicSeg,    setForensicSeg   ] = useState<RecordingSegment | null>(null)

  // ── Load cameras once ──────────────────────────────────────────────────────
  useEffect(() => {
    camerasService.list({ page_size: 200 }).then((list) => {
      setCameras(list)
      const cam = initCameraId
        ? (list.find((c) => c.id === initCameraId) ?? list[0])
        : list[0]
      if (cam) setSelCam(cam)
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Load day HLS on camera/date change ─────────────────────────────────────
  const loadDay = useCallback(() => {
    if (!selCam || !token) return
    setLoading(true)
    setError(null)
    setHlsUrl(null)

    recordingsService.getDayHls(selCam.id, selDate)
      .then((res) => {
        const startMs = new Date(res.started_at).getTime()
        const endMs = new Date(res.ended_at).getTime()
        setWindowStartMs(startMs)
        setWindowEndMs(endMs)
        setIntervals(res.intervals)
        const sep = res.hls_url.includes('?') ? '&' : '?'
        setHlsUrl(`${res.hls_url}${sep}token=${encodeURIComponent(token)}`)
        // Posição inicial = último segmento (ponto mais recente)
        setPlayheadMs(endMs)
        setSeekToMs(endMs)
      })
      .catch((err) => {
        setError(err?.response?.data?.detail ?? 'Sem gravações nesta data')
        setIntervals([])
        setWindowStartMs(0)
        setWindowEndMs(0)
      })
      .finally(() => setLoading(false))
  }, [selCam, selDate, token])

  useEffect(() => { loadDay() }, [loadDay])

  // Mantém segmentos carregados em paralelo para os botões de integridade
  useEffect(() => {
    if (!selCam) { setSegments([]); return }
    const startIso = new Date(selDate + 'T00:00:00').toISOString()
    const endIso   = new Date(selDate + 'T23:59:59.999').toISOString()
    recordingsService.listSegments({
      camera_id: selCam.id,
      started_after: startIso,
      started_before: endIso,
      page_size: 500,
    }).then((res) => {
      setSegments((res.items ?? []).slice().sort(
        (a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime(),
      ))
    }).catch(() => setSegments([]))
  }, [selCam, selDate])

  // ── Refresh automático para o dia de hoje ─────────────────────────────────
  useEffect(() => {
    const todayStr = new Date().toISOString().split('T')[0]
    if (selDate !== todayStr || !selCam) return
    const interval = setInterval(loadDay, 60_000)
    return () => clearInterval(interval)
  }, [selDate, selCam, loadDay])

  // ── Callbacks ──────────────────────────────────────────────────────────────
  const handleSeek = useCallback((ms: number) => {
    setPlayheadMs(ms)
    setSeekToMs(ms)
  }, [])

  const handleTimeUpdate = useCallback((currentMs: number) => {
    setPlayheadMs(currentMs)
  }, [])

  const handleTogglePlay = useCallback(() => {
    const video = document.querySelector<HTMLVideoElement>('video')
    if (!video) return
    if (video.paused) video.play().catch(() => {})
    else video.pause()
    setPlaying(!video.paused)
  }, [])

  // ── Stats ──────────────────────────────────────────────────────────────────
  const today = new Date().toISOString().split('T')[0]
  const totalMin = useMemo(
    () => Math.round(intervals.reduce((a, s) => a + s.duration_seconds, 0) / 60),
    [intervals],
  )

  // ── Cadeia de Custódia handlers ────────────────────────────────────────────
  const handleVerifyIntegrity = async (seg: RecordingSegment) => {
    try {
      toast.loading('Verificando integridade...', { id: `integrity-${seg.id}` })
      const result = await recordingsService.verifyIntegrity(seg.id)
      if (result.verified) {
        toast.success('Integridade verificada ✓', { id: `integrity-${seg.id}` })
      } else {
        toast.error('Integridade COMPROMETIDA ✗', { id: `integrity-${seg.id}` })
      }
    } catch {
      toast.error('Erro ao verificar integridade', { id: `integrity-${seg.id}` })
    }
  }

  const handleViewCustodyChain = async (seg: RecordingSegment) => {
    setCustodyLoading(true)
    setShowCustody(true)
    try {
      const data = await recordingsService.getCustodyChain(seg.id)
      setCustodyData(data)
    } catch {
      toast.error('Erro ao carregar cadeia de custódia')
      setCustodyData(null)
    } finally {
      setCustodyLoading(false)
    }
  }

  const handleExportForensic = (seg: RecordingSegment) => {
    setForensicSeg(seg)
    setShowForensic(true)
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full overflow-hidden">

      {/* ── Toolbar ──────────────────────────────────────────────────── */}
      <div
        className="flex items-center gap-2 px-4 shrink-0 flex-wrap"
        style={{ height: 48, background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}
      >
        {/* Camera selector */}
        <select
          className="select"
          style={{ width: 'auto', minWidth: 140, maxWidth: 240, fontSize: 12 }}
          value={selCam?.id ?? ''}
          onChange={(e) => setSelCam(cameras.find((c) => c.id === e.target.value) ?? null)}
        >
          {cameras.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>

        {/* Date nav */}
        <div className="flex items-center gap-0.5">
          <button
            className="btn btn-ghost w-7 h-7 p-0"
            onClick={() => setSelDate((d) => shiftDate(d, -1))}
          >
            <ChevronLeft size={14} />
          </button>
          <label
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium cursor-pointer tabular-nums"
            style={{ background: 'var(--elevated)', border: '1px solid var(--border)', fontSize: 12 }}
          >
            {fmtDate(selDate)}
            <input
              type="date"
              className="sr-only"
              value={selDate}
              max={today}
              onChange={(e) => e.target.value && setSelDate(e.target.value)}
            />
          </label>
          <button
            className="btn btn-ghost w-7 h-7 p-0"
            onClick={() => setSelDate((d) => shiftDate(d, 1))}
            disabled={selDate >= today}
          >
            <ChevronRight size={14} />
          </button>
        </div>

        {/* Stats */}
        <div className="ml-auto flex items-center gap-3 tabular-nums" style={{ fontSize: 11, color: '#525252' }}>
          {loading ? (
            <span>Carregando…</span>
          ) : error && intervals.length === 0 ? (
            <span style={{ color: '#ef4444', fontSize: 11 }}>{error}</span>
          ) : (
            <span>{intervals.length} segmentos · {totalMin}min gravados</span>
          )}
        </div>
      </div>

      {/* ── Player ───────────────────────────────────────────────────── */}
      <div className="flex-1 min-h-0 relative bg-black flex items-center justify-center">
        {hlsUrl ? (
          <RecordingPlayer
            hlsUrl={hlsUrl}
            windowStartMs={windowStartMs}
            seekToMs={seekToMs}
            className="w-full h-full"
            onReady={() => { setLoading(false); setPlaying(true) }}
            onError={(msg) => setError(msg)}
            onTimeUpdate={handleTimeUpdate}
          />
        ) : loading ? (
          <div
            className="w-8 h-8 rounded-full animate-spin"
            style={{ border: '1.5px solid #1c1c1e', borderTopColor: '#3b82f6' }}
          />
        ) : (
          <div className="flex flex-col items-center gap-2" style={{ color: '#2a2a2a' }}>
            <VideoOff size={40} strokeWidth={1} />
            <p style={{ fontSize: 13 }}>
              {error ?? `Sem gravações em ${fmtDate(selDate)}`}
            </p>
          </div>
        )}

        {/* ── Badge: posição atual ──────────────────────────────────── */}
        {hlsUrl && (
          <div
            className="absolute top-3 left-3 flex items-center gap-2 tabular-nums"
            style={{
              fontSize: 11,
              padding: '4px 10px',
              borderRadius: 6,
              background: 'rgba(0,0,0,0.65)',
              color: '#a3a3a3',
              backdropFilter: 'blur(6px)',
            }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-teal-500" />
            {new Date(playheadMs).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            {currentSeg && (
              <span style={{ color: '#404040' }}>· {fmtDuration(currentSeg.duration_seconds)}</span>
            )}
            <span
              className="ml-1 px-1.5 py-0.5 rounded text-[9px] font-semibold"
              style={{ background: 'rgba(59,130,246,0.22)', color: '#60a5fa' }}
            >
              HLS
            </span>
            {currentSeg && (
              <>
                <button
                  className="ml-2 p-0.5 rounded opacity-60 hover:opacity-100 transition-opacity"
                  title="Verificar integridade"
                  onClick={() => handleVerifyIntegrity(currentSeg)}
                >
                  <ShieldCheck size={11} />
                </button>
                <button
                  className="p-0.5 rounded opacity-60 hover:opacity-100 transition-opacity"
                  title="Exportar laudo forense"
                  onClick={() => handleExportForensic(currentSeg)}
                >
                  <FileSearch size={11} />
                </button>
                <button
                  className="p-0.5 rounded opacity-60 hover:opacity-100 transition-opacity"
                  title="Cadeia de custódia"
                  onClick={() => handleViewCustodyChain(currentSeg)}
                >
                  🔗
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {/* ── Timeline ─────────────────────────────────────────────────── */}
      <div
        className="shrink-0"
        style={{ background: 'var(--surface)', borderTop: '1px solid var(--border)' }}
      >
        <div className="px-4 pt-4 pb-3">
          {windowEndMs > windowStartMs ? (
            <DayProgressTimeline
              windowStartMs={windowStartMs}
              windowEndMs={windowEndMs}
              currentMs={playheadMs}
              onSeek={handleSeek}
              playing={playing}
              onTogglePlay={handleTogglePlay}
              intervals={intervals}
            />
          ) : (
            <div style={{
              height: 80,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'rgba(255,255,255,0.3)',
              fontSize: 12,
            }}>
              {loading ? 'Carregando gravações…' : 'Sem gravações neste dia.'}
            </div>
          )}
        </div>
      </div>

      {/* ── Cadeia de Custódia modals ─────────────────────────────────── */}
      <Modal
        open={showCustody}
        onClose={() => setShowCustody(false)}
        title="Cadeia de Custódia"
        size="md"
      >
        {custodyLoading ? (
          <div className="py-8 text-center">
            <div
              className="w-8 h-8 rounded-full animate-spin mx-auto"
              style={{ border: '2px solid var(--border)', borderTopColor: 'var(--accent)' }}
            />
          </div>
        ) : custodyData ? (
          <CustodyChainViewer entries={custodyData.custody_chain} />
        ) : (
          <p className="text-sm text-t3 text-center py-8">Nenhum dado de custódia disponível</p>
        )}
      </Modal>

      {forensicSeg && (
        <ForensicExportModal
          open={showForensic}
          recordingId={forensicSeg.id}
          recordingLabel={`${selCam?.name ?? ''} · ${fmtTime(forensicSeg.started_at)}`}
          onClose={() => { setShowForensic(false); setForensicSeg(null) }}
          onExported={() => { handleViewCustodyChain(forensicSeg) }}
        />
      )}
    </div>
  )
}
