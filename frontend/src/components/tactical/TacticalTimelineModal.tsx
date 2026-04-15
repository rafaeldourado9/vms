import { useCallback, useEffect, useMemo, useState } from 'react'
import { Brain, ChevronLeft, ChevronRight, X } from 'lucide-react'
import { recordingsService } from '@/services/recordings'
import { analyticsService, type AnalyticsEvent } from '@/services/analytics'
import { VideoPlayer } from '@/components/camera/VideoPlayer'
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

function fmtDateShort(iso: string) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('pt-BR', {
    day: '2-digit', month: 'short',
  })
}

interface Props {
  camera: Camera
  onClose: () => void
}

export function TacticalTimelineModal({ camera, onClose }: Props) {
  const token = useAuthStore((s) => s.tokens?.access_token ?? '')
  const today = new Date().toISOString().split('T')[0]

  const [selDate, setSelDate]         = useState(today)
  const [segments, setSegments]       = useState<RecordingSegment[]>([])
  const [loading, setLoading]         = useState(false)
  const [playbackSeg, setPlaybackSeg] = useState<RecordingSegment | null>(null)
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null)
  const [analyticsEvents, setAnalyticsEvents] = useState<AnalyticsEvent[]>([])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  useEffect(() => {
    setLoading(true)
    setPlaybackUrl(null)
    setPlaybackSeg(null)
    setSegments([])

    recordingsService
      .listSegments({
        camera_id:      camera.id,
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
  }, [camera.id, selDate])

  useEffect(() => {
    setAnalyticsEvents([])
    analyticsService.getEvents({
      camera_id:       camera.id,
      occurred_after:  new Date(selDate + 'T00:00:00').toISOString(),
      occurred_before: new Date(selDate + 'T23:59:59.999').toISOString(),
      limit: 500,
    }).then(setAnalyticsEvents).catch(() => {})
  }, [camera.id, selDate])

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
      id: ev.id, time: new Date(ev.occurred_at),
      severity: ev.severity, plugin_id: ev.plugin_id, event_type: ev.event_type,
    })), [analyticsEvents])

  const segmentEvents = useMemo(() => {
    if (!playbackSeg) return []
    const s0 = new Date(playbackSeg.started_at).getTime()
    const s1 = new Date(playbackSeg.ended_at).getTime()
    return analyticsEvents
      .filter((ev) => { const t = new Date(ev.occurred_at).getTime(); return t >= s0 && t <= s1 })
      .sort((a, b) => new Date(a.occurred_at).getTime() - new Date(b.occurred_at).getTime())
  }, [analyticsEvents, playbackSeg])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.92)', backdropFilter: 'blur(12px)' }}
      onClick={onClose}
    >
      <div
        className="relative flex flex-col w-full max-w-6xl"
        style={{
          height: '92vh',
          background: '#0a0a0a',
          borderRadius: 12,
          border: '1px solid rgba(255,255,255,0.06)',
          boxShadow: '0 32px 80px rgba(0,0,0,0.8)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Header ─────────────────────────────────────────────────── */}
        <div
          className="flex items-center gap-3 px-5 shrink-0"
          style={{
            height: 48,
            borderBottom: '1px solid rgba(255,255,255,0.05)',
          }}
        >
          {/* Camera name */}
          <span className="text-[13px] font-medium text-white/90 truncate flex-1 tracking-tight">
            {camera.name}
          </span>

          {camera.location && (
            <span className="hidden lg:block text-[11px] truncate max-w-xs" style={{ color: '#3f3f46' }}>
              {camera.location}
            </span>
          )}

          {analyticsEvents.length > 0 && (
            <span className="flex items-center gap-1.5 text-[11px]" style={{ color: '#60a5fa' }}>
              <Brain size={11} strokeWidth={1.5} />
              <span className="tabular-nums">{analyticsEvents.length}</span>
            </span>
          )}

          {/* Date nav */}
          <div className="flex items-center gap-0.5">
            <button
              onClick={() => setSelDate((d) => shiftDate(d, -1))}
              className="w-7 h-7 flex items-center justify-center rounded-md transition-colors"
              style={{ color: '#525252' }}
              onMouseEnter={e => (e.currentTarget.style.color = '#a3a3a3')}
              onMouseLeave={e => (e.currentTarget.style.color = '#525252')}
            >
              <ChevronLeft size={14} />
            </button>
            <label
              className="px-2.5 py-1 rounded-md text-[11px] cursor-pointer transition-colors tabular-nums"
              style={{
                color: '#a3a3a3',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}
            >
              {fmtDateShort(selDate)}
              <input
                type="date"
                className="sr-only"
                value={selDate}
                max={today}
                onChange={(e) => e.target.value && setSelDate(e.target.value)}
              />
            </label>
            <button
              onClick={() => setSelDate((d) => shiftDate(d, 1))}
              disabled={selDate >= today}
              className="w-7 h-7 flex items-center justify-center rounded-md transition-colors disabled:opacity-25"
              style={{ color: '#525252' }}
              onMouseEnter={e => (e.currentTarget.style.color = '#a3a3a3')}
              onMouseLeave={e => (e.currentTarget.style.color = '#525252')}
            >
              <ChevronRight size={14} />
            </button>
          </div>

          {/* Close */}
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-md transition-colors"
            style={{ color: '#525252' }}
            onMouseEnter={e => (e.currentTarget.style.color = '#e4e4e7')}
            onMouseLeave={e => (e.currentTarget.style.color = '#525252')}
          >
            <X size={15} />
          </button>
        </div>

        {/* ── Video ──────────────────────────────────────────────────── */}
        <div className="flex-1 min-h-0 bg-black relative">
          {loading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div
                className="w-8 h-8 rounded-full border-t border-white/20 animate-spin"
                style={{ borderWidth: 1.5 }}
              />
            </div>
          ) : playbackUrl && playbackSeg ? (
            <VideoPlayer
              src={playbackUrl}
              name={`${fmtTime(playbackSeg.started_at)} — ${fmtTime(playbackSeg.ended_at)}`}
              className="w-full h-full object-contain"
              muted={false}
              autoPlay
            />
          ) : (
            <div
              className="absolute inset-0 flex items-center justify-center text-[13px]"
              style={{ color: '#2a2a2a' }}
            >
              {segments.length === 0 ? 'Sem gravações nesta data' : 'Selecione um segmento'}
            </div>
          )}
        </div>

        {/* ── Bottom ─────────────────────────────────────────────────── */}
        <div
          className="shrink-0"
          style={{ borderTop: '1px solid rgba(255,255,255,0.04)', background: '#0a0a0a' }}
        >
          {/* Timeline scrubber */}
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

          {/* Analytics events */}
          {segmentEvents.length > 0 && (
            <div
              className="flex items-center gap-1 px-5 pb-3 overflow-x-auto"
              style={{
                scrollbarWidth: 'none',
                borderTop: '1px solid rgba(255,255,255,0.04)',
                paddingTop: 8,
              }}
            >
              <span
                className="flex items-center gap-1 shrink-0 mr-1"
                style={{ color: '#2a2a2a', fontSize: 10 }}
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
                    title={ev.event_type}
                  >
                    <span
                      className="w-1 h-1 rounded-full shrink-0"
                      style={{ background: sev.dot }}
                    />
                    <span className="font-medium">
                      {PLUGIN_NAMES[ev.plugin_id] ?? ev.plugin_id}
                    </span>
                    <span className="tabular-nums" style={{ opacity: 0.55 }}>
                      {fmtTimeFull(ev.occurred_at)}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
