import { useCallback, useEffect, useState } from 'react'
import { Calendar, ChevronLeft, ChevronRight, X } from 'lucide-react'
import { recordingsService } from '@/services/recordings'
import { VideoPlayer } from '@/components/camera/VideoPlayer'
import { ModernTimeline } from '@/components/map/ModernTimeline'
import { useAuthStore } from '@/store/authStore'
import type { Camera, RecordingSegment } from '@/types'



function shiftDate(iso: string, days: number): string {
  const d = new Date(iso)
  d.setDate(d.getDate() + days)
  return d.toISOString().split('T')[0]
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}


interface MapTimelinePanelProps {
  camera: Camera
  onClose: () => void
}

export function MapTimelinePanel({ camera, onClose }: MapTimelinePanelProps) {
  const token = useAuthStore((s) => s.tokens?.access_token ?? '')
  const today = new Date().toISOString().split('T')[0]

  const [selDate, setSelDate]         = useState(today)
  const [segments, setSegments]       = useState<RecordingSegment[]>([])
  const [loading, setLoading]         = useState(false)
  const [playbackSeg, setPlaybackSeg] = useState<RecordingSegment | null>(null)
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null)

  // Carrega segmentos ao mudar câmera/data
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

  const playSeg = useCallback((seg: RecordingSegment) => {
    if (!token) return
    setPlaybackSeg(seg)
    setPlaybackUrl(null)
    recordingsService.prepareHls(seg.id).then((res) => {
      setPlaybackUrl(`${res.hls_url}?token=${encodeURIComponent(token)}`)
    }).catch(() => {
      setPlaybackUrl(null)
    })
  }, [token])

  const handleTimelineSeek = useCallback((time: Date) => {
    const hit = segments.find((s) => {
      const s0 = new Date(s.started_at).getTime()
      const s1 = new Date(s.ended_at).getTime()
      return time.getTime() >= s0 && time.getTime() <= s1
    })
    if (hit) playSeg(hit)
  }, [segments, playSeg])

  return (
    <div
      className="absolute bottom-0 left-0 right-0 flex flex-col"
      style={{
        height: 380,
        background: 'rgba(9,9,11,0.96)',
        backdropFilter: 'blur(8px)',
        borderTop: '1px solid rgba(255,255,255,0.08)',
        zIndex: 20,
      }}
    >
      {/* ── Header ─────────────────────────────────────────────── */}
      <div
        className="flex items-center gap-3 px-3 py-2 shrink-0"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
      >
        <span className="text-sm font-semibold text-white truncate flex-1">{camera.name}</span>

        {/* Date nav */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            className="w-6 h-6 flex items-center justify-center rounded text-zinc-400 hover:text-white hover:bg-white/10 transition"
            onClick={() => setSelDate((d) => shiftDate(d, -1))}
          >
            <ChevronLeft size={14} />
          </button>
          <label
            className="flex items-center gap-1 px-2 py-0.5 rounded text-xs text-zinc-300 cursor-pointer hover:bg-white/10 transition"
            style={{ border: '1px solid rgba(255,255,255,0.12)' }}
          >
            <Calendar size={11} className="text-zinc-500" />
            {new Date(selDate + 'T00:00:00').toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })}
            <input
              type="date"
              className="sr-only"
              value={selDate}
              max={today}
              onChange={(e) => e.target.value && setSelDate(e.target.value)}
            />
          </label>
          <button
            className="w-6 h-6 flex items-center justify-center rounded text-zinc-400 hover:text-white hover:bg-white/10 transition disabled:opacity-30"
            onClick={() => setSelDate((d) => shiftDate(d, 1))}
            disabled={selDate >= today}
          >
            <ChevronRight size={14} />
          </button>
        </div>

        <button
          onClick={onClose}
          className="w-6 h-6 flex items-center justify-center rounded text-zinc-500 hover:text-white hover:bg-white/10 transition shrink-0"
        >
          <X size={14} />
        </button>
      </div>

      {/* ── Video ──────────────────────────────────────────────── */}
      <div className="flex-1 min-h-0 bg-black relative">
        {loading ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-7 h-7 border-2 border-t-accent border-zinc-700 rounded-full animate-spin" />
          </div>
        ) : playbackUrl && playbackSeg ? (
          <VideoPlayer
            src={playbackUrl}
            name={`${camera.name} · ${fmtTime(playbackSeg.started_at)}`}
            className="w-full h-full object-contain"
            muted
            autoPlay
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-zinc-600 text-sm">
            {segments.length === 0 ? 'Sem gravações nesta data' : 'Selecione um segmento'}
          </div>
        )}
      </div>

      {/* ── Bottom bar ─────────────────────────────────────────── */}
      <div className="shrink-0" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
        {/* Timeline */}
        <div className="px-3 pt-2 pb-1">
          <ModernTimeline
            segments={segments}
            currentTime={playbackSeg ? new Date(playbackSeg.started_at) : new Date()}
            onSeek={handleTimelineSeek}
            isLoading={loading}
            selectedDate={selDate}
            eventMarkers={[]}
          />
        </div>
      </div>
    </div>
  )
}
