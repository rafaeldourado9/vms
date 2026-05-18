import { useCallback, useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { recordingsService } from '@/services/recordings'
import { RecordingPlayer } from '@/components/camera/RecordingPlayer'
import { DayProgressTimeline, type DayInterval } from '@/components/camera/DayProgressTimeline'
import { useAuthStore } from '@/store/authStore'
import type { Camera } from '@/types'

function shiftDate(iso: string, days: number): string {
  const d = new Date(iso)
  d.setDate(d.getDate() + days)
  return d.toISOString().split('T')[0]
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

  const [selDate, setSelDate] = useState(today)
  const [loading, setLoading] = useState(false)
  const [hlsUrl, setHlsUrl] = useState<string | null>(null)
  const [windowStartMs, setWindowStartMs] = useState(0)
  const [windowEndMs, setWindowEndMs] = useState(0)
  const [intervals, setIntervals] = useState<DayInterval[]>([])
  const [playheadMs, setPlayheadMs] = useState(Date.now())
  const [seekToMs, setSeekToMs] = useState<number | undefined>(undefined)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
    if (!token) return
    setLoading(true)
    setError(null)
    setHlsUrl(null)

    recordingsService.getDayHls(camera.id, selDate)
      .then((res) => {
        const startMs = new Date(res.started_at).getTime()
        const endMs = new Date(res.ended_at).getTime()
        setWindowStartMs(startMs)
        setWindowEndMs(endMs)
        setIntervals(res.intervals)
        const sep = res.hls_url.includes('?') ? '&' : '?'
        setHlsUrl(`${res.hls_url}${sep}token=${encodeURIComponent(token)}`)
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
  }, [camera.id, selDate, token])

  const handleSeek = useCallback((ms: number) => {
    setPlayheadMs(ms)
    setSeekToMs(ms)
  }, [])

  const handleTogglePlay = useCallback(() => {
    const video = document.querySelector<HTMLVideoElement>('.tactical-modal-video video')
    if (!video) return
    if (video.paused) video.play().catch(() => {})
    else video.pause()
    setPlaying(!video.paused)
  }, [])

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
          <span className="text-[13px] font-medium text-white/90 truncate flex-1 tracking-tight">
            {camera.name}
          </span>

          {camera.location && (
            <span className="hidden lg:block text-[11px] truncate max-w-xs" style={{ color: '#3f3f46' }}>
              {camera.location}
            </span>
          )}

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
        <div className="flex-1 min-h-0 bg-black relative tactical-modal-video">
          {loading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div
                className="w-8 h-8 rounded-full border-t border-white/20 animate-spin"
                style={{ borderWidth: 1.5 }}
              />
            </div>
          ) : hlsUrl ? (
            <RecordingPlayer
              hlsUrl={hlsUrl}
              windowStartMs={windowStartMs}
              seekToMs={seekToMs}
              className="w-full h-full"
              onReady={() => { setLoading(false); setPlaying(true) }}
              onError={(msg) => setError(msg)}
              onTimeUpdate={(ms) => setPlayheadMs(ms)}
            />
          ) : (
            <div
              className="absolute inset-0 flex items-center justify-center text-[13px]"
              style={{ color: '#2a2a2a' }}
            >
              {error ?? 'Sem gravações nesta data'}
            </div>
          )}
        </div>

        {/* ── Bottom ─────────────────────────────────────────────────── */}
        <div
          className="shrink-0"
          style={{ borderTop: '1px solid rgba(255,255,255,0.04)', background: '#0a0a0a' }}
        >
          <div className="px-5 pt-4 pb-4">
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
                color: 'rgba(255,255,255,0.25)',
                fontSize: 12,
              }}>
                {loading ? 'Carregando gravações…' : 'Sem gravações neste dia.'}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
