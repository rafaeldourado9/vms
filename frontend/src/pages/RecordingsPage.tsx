import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Brain, ChevronLeft, ChevronRight, VideoOff } from 'lucide-react'
import { camerasService } from '@/services/cameras'
import { recordingsService } from '@/services/recordings'
import { analyticsService, type AnalyticsEvent } from '@/services/analytics'
import { VideoPlayer } from '@/components/camera/VideoPlayer'
import { RecordingPlayer } from '@/components/camera/RecordingPlayer'
import { ModernTimeline, type EventMarker } from '@/components/map/ModernTimeline'
import { useAuthStore } from '@/store/authStore'
import { PLUGIN_NAMES, SEV_STYLE } from '@/constants/plugins'
import type { Camera, RecordingSegment } from '@/types'

function shiftDate(iso: string, days: number): string {
  const d = new Date(iso)
  d.setDate(d.getDate() + days)
  return d.toISOString().split('T')[0]
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

function fmtTimeFull(iso: string) {
  return new Date(iso).toLocaleTimeString('pt-BR', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
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

export function RecordingsPage() {
  const token = useAuthStore((s) => s.tokens?.access_token ?? '')
  const [searchParams] = useSearchParams()

  const initCameraId = searchParams.get('camera_id')
  const initDate     = searchParams.get('date')

  const [cameras, setCameras]         = useState<Camera[]>([])
  const [selCam, setSelCam]           = useState<Camera | null>(null)
  const [selDate, setSelDate]         = useState(() => initDate ?? new Date().toISOString().split('T')[0])
  const [segments, setSegments]       = useState<RecordingSegment[]>([])
  const [loading, setLoading]         = useState(false)
  const [playbackSeg, setPlaybackSeg] = useState<RecordingSegment | null>(null)
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null)
  const [useVOD, setUseVOD]           = useState(true) // Toggle para modo VOD
  const [analyticsEvents, setAnalyticsEvents] = useState<AnalyticsEvent[]>([])

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

  useEffect(() => {
    if (!selCam) { setSegments([]); return }
    setLoading(true)
    setPlaybackUrl(null)
    setPlaybackSeg(null)

    recordingsService
      .listSegments({
        camera_id: selCam.id,
        started_after:  new Date(selDate + 'T00:00:00').toISOString(),
        started_before: new Date(selDate + 'T23:59:59.999').toISOString(),
        page_size: 500,
      })
      .then((res) => {
        const sorted = (res.items ?? []).slice().sort(
          (a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime(),
        )
        setSegments(sorted)
        if (sorted.length > 0) playSeg(sorted[sorted.length - 1])
      })
      .catch(() => setSegments([]))
      .finally(() => setLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selCam, selDate])

  useEffect(() => {
    setAnalyticsEvents([])
    if (!selCam) return
    analyticsService.getEvents({
      camera_id:       selCam.id,
      occurred_after:  new Date(selDate + 'T00:00:00').toISOString(),
      occurred_before: new Date(selDate + 'T23:59:59.999').toISOString(),
      limit: 500,
    })
      .then(setAnalyticsEvents)
      .catch(() => setAnalyticsEvents([]))
  }, [selCam, selDate])

  const playSeg = useCallback((seg: RecordingSegment) => {
    if (!token) return
    const url = new URL(seg.file_path, window.location.origin)
    url.searchParams.set('token', token)
    setPlaybackSeg(seg)
    setPlaybackUrl(url.toString())
  }, [token])

  const handleSeek = useCallback((time: Date) => {
    const hit = segments.find((s) => {
      const s0 = new Date(s.started_at).getTime()
      const s1 = new Date(s.ended_at).getTime()
      return time.getTime() >= s0 && time.getTime() <= s1
    })
    if (hit) playSeg(hit)
  }, [segments, playSeg])

  const eventMarkers = useMemo<EventMarker[]>(() =>
    analyticsEvents.map((ev) => ({
      id:         ev.id,
      time:       new Date(ev.occurred_at),
      severity:   ev.severity,
      plugin_id:  ev.plugin_id,
      event_type: ev.event_type,
    })), [analyticsEvents])

  const segmentEvents = useMemo(() => {
    if (!playbackSeg) return []
    const s0 = new Date(playbackSeg.started_at).getTime()
    const s1 = new Date(playbackSeg.ended_at).getTime()
    return analyticsEvents
      .filter((ev) => { const t = new Date(ev.occurred_at).getTime(); return t >= s0 && t <= s1 })
      .sort((a, b) => new Date(a.occurred_at).getTime() - new Date(b.occurred_at).getTime())
  }, [analyticsEvents, playbackSeg])

  const today      = new Date().toISOString().split('T')[0]
  const totalMin   = useMemo(
    () => Math.round(segments.reduce((a, s) => a + s.duration_seconds, 0) / 60),
    [segments],
  )

  return (
    <div className="-m-4 flex flex-col h-[calc(100vh-3.5rem)]">

      {/* ── Toolbar ──────────────────────────────────────────────────── */}
      <div
        className="flex items-center gap-2 px-4 shrink-0 flex-wrap"
        style={{
          height: 48,
          background: 'var(--surface)',
          borderBottom: '1px solid var(--border)',
        }}
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
          <button className="btn btn-ghost w-7 h-7 p-0" onClick={() => setSelDate((d) => shiftDate(d, -1))}>
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
        <div
          className="ml-auto flex items-center gap-3 tabular-nums"
          style={{ fontSize: 11, color: '#525252' }}
        >
          {/* Toggle VOD/Legacy */}
          <button
            className="flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-colors"
            style={{
              background: useVOD ? '#3b82f6' : 'var(--elevated)',
              color: useVOD ? 'white' : '#525252',
              border: '1px solid var(--border)',
            }}
            onClick={() => {
              setUseVOD(!useVOD)
              if (useVOD) {
                setPlaybackUrl(null)
                setPlaybackSeg(null)
              }
            }}
            title={useVOD ? 'Modo VOD (streaming HLS)' : 'Modo legado (MP4 direto)'}
          >
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: useVOD ? '#60a5fa' : '#525252' }} />
            {useVOD ? 'VOD' : 'MP4'}
          </button>

          {loading ? (
            <span>Carregando…</span>
          ) : (
            <>
              <span>{segments.length} seg · {totalMin}min</span>
              {analyticsEvents.length > 0 && (
                <span className="flex items-center gap-1" style={{ color: '#3b82f6' }}>
                  <Brain size={11} strokeWidth={1.5} />
                  {analyticsEvents.length}
                </span>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── Player ───────────────────────────────────────────────────── */}
      <div className="flex-1 min-h-0 relative bg-black flex items-center justify-center">
        {loading ? (
          <div
            className="w-8 h-8 rounded-full animate-spin"
            style={{ border: '1.5px solid #1c1c1e', borderTopColor: '#3b82f6' }}
          />
        ) : useVOD && playbackSeg ? (
          // Modo VOD (streaming HLS)
          <RecordingPlayer
            segmentIds={[playbackSeg.id]}
            cameraId={selCam!.id}
            startsAt={playbackSeg.started_at}
            endsAt={playbackSeg.ended_at}
            className="w-full h-full"
            onReady={() => setLoading(false)}
            onError={() => setPlaybackUrl(null)}
          />
        ) : playbackUrl && playbackSeg ? (
          // Modo legado (MP4 direto - fallback)
          <VideoPlayer
            src={playbackUrl}
            name={`${selCam?.name} · ${fmtTime(playbackSeg.started_at)}`}
            className="w-full h-full object-contain"
            muted
            autoPlay
          />
        ) : (
          <div className="flex flex-col items-center gap-2" style={{ color: '#2a2a2a' }}>
            <VideoOff size={40} strokeWidth={1} />
            <p style={{ fontSize: 13 }}>
              {segments.length === 0
                ? `Sem gravações em ${fmtDate(selDate)}`
                : 'Selecione um segmento'}
            </p>
          </div>
        )}

        {/* Segment badge */}
        {playbackSeg && (
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
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
            {fmtTime(playbackSeg.started_at)} — {fmtTime(playbackSeg.ended_at)}
            <span style={{ color: '#404040' }}>{fmtDuration(playbackSeg.duration_seconds)}</span>
            {useVOD && (
              <span
                className="ml-2 px-1.5 py-0.5 rounded text-[9px] font-semibold"
                style={{ background: '#3b82f6', color: 'white' }}
              >
                VOD
              </span>
            )}
          </div>
        )}
      </div>

      {/* ── Bottom panel ─────────────────────────────────────────────── */}
      <div
        className="shrink-0"
        style={{ background: 'var(--surface)', borderTop: '1px solid var(--border)' }}
      >
        {/* Timeline */}
        <div className="px-5 pt-4 pb-2">
          <ModernTimeline
            segments={segments}
            currentTime={playbackSeg ? new Date(playbackSeg.started_at) : new Date()}
            onSeek={handleSeek}
            isLoading={loading}
            selectedDate={selDate}
            eventMarkers={eventMarkers}
          />
        </div>

        {/* Analytics events strip */}
        {segmentEvents.length > 0 && (
          <div
            className="flex items-center gap-1 px-5 pb-3 overflow-x-auto"
            style={{
              scrollbarWidth: 'none',
              borderTop: '1px solid var(--border)',
              paddingTop: 8,
            }}
          >
            <span
              className="flex items-center gap-1 shrink-0 mr-1"
              style={{ fontSize: 10, color: '#2a2a2a' }}
            >
              <Brain size={9} strokeWidth={1.5} />
            </span>
            {segmentEvents.map((ev) => {
              const sev = SEV_STYLE[ev.severity] ?? SEV_STYLE.info
              return (
                <div
                  key={ev.id}
                  className="shrink-0 flex items-center gap-1 rounded text-[10px]"
                  style={{
                    padding: '2px 6px',
                    background: sev.bg,
                    color: sev.text,
                    border: `1px solid ${sev.dot}20`,
                  }}
                  title={`${PLUGIN_NAMES[ev.plugin_id] ?? ev.plugin_id} · ${ev.event_type}${ev.confidence != null ? ` · ${(ev.confidence * 100).toFixed(0)}%` : ''}`}
                >
                  <span className="w-1 h-1 rounded-full shrink-0" style={{ background: sev.dot }} />
                  <span className="font-medium">{PLUGIN_NAMES[ev.plugin_id] ?? ev.plugin_id}</span>
                  <span className="tabular-nums" style={{ opacity: 0.55 }}>
                    {fmtTimeFull(ev.occurred_at)}
                  </span>
                  {ev.confidence != null && (
                    <span style={{ opacity: 0.45 }}>
                      {(ev.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
