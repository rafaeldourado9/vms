import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Calendar, ChevronLeft, ChevronRight, Film, Play, VideoOff } from 'lucide-react'
import { clsx } from 'clsx'
import { camerasService } from '@/services/cameras'
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

function fmtDate(iso: string) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('pt-BR', {
    day: '2-digit', month: 'short', year: 'numeric',
  })
}

function fmtDuration(seconds: number) {
  if (seconds < 60) return `${Math.round(seconds)}s`
  return `${Math.round(seconds / 60)}min`
}

export function RecordingsPage() {
  const token = useAuthStore((s) => s.tokens?.access_token ?? '')

  const [cameras, setCameras]     = useState<Camera[]>([])
  const [selCam, setSelCam]       = useState<Camera | null>(null)
  const [selDate, setSelDate]     = useState(() => new Date().toISOString().split('T')[0])
  const [segments, setSegments]   = useState<RecordingSegment[]>([])
  const [loading, setLoading]     = useState(false)
  const [playbackSeg, setPlaybackSeg] = useState<RecordingSegment | null>(null)
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  // Load cameras once
  useEffect(() => {
    camerasService.list({ page_size: 200 }).then((list) => {
      setCameras(list)
      if (list.length > 0) setSelCam(list[0])
    })
  }, [])

  // Load segments when camera or date changes
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
          (a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime()
        )
        setSegments(sorted)
        // Auto-play last segment (most recent)
        if (sorted.length > 0) playSeg(sorted[sorted.length - 1])
      })
      .catch(() => setSegments([]))
      .finally(() => setLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selCam, selDate])

  const playSeg = useCallback((seg: RecordingSegment) => {
    if (!token) return
    const url = new URL(seg.file_path, window.location.origin)
    url.searchParams.set('token', token)
    setPlaybackSeg(seg)
    setPlaybackUrl(url.toString())
    // Scroll segment into view in the list
    setTimeout(() => {
      const el = listRef.current?.querySelector(`[data-seg="${seg.id}"]`)
      el?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
    }, 50)
  }, [token])

  const handleTimelineSeek = useCallback((time: Date) => {
    const hit = segments.find((s) => {
      const s0 = new Date(s.started_at).getTime()
      const s1 = new Date(s.ended_at).getTime()
      return time.getTime() >= s0 && time.getTime() <= s1
    })
    if (hit) playSeg(hit)
  }, [segments, playSeg])

  const totalMin = useMemo(
    () => Math.round(segments.reduce((a, s) => a + s.duration_seconds, 0) / 60),
    [segments],
  )

  const today = new Date().toISOString().split('T')[0]

  return (
    <div className="-m-4 flex flex-col h-[calc(100vh-3.5rem)]">

      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <div
        className="flex items-center gap-3 px-4 py-2.5 border-b shrink-0 flex-wrap"
        style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
      >
        {/* Camera */}
        <select
          className="select"
          style={{ width: 'auto', minWidth: 160, maxWidth: 260 }}
          value={selCam?.id ?? ''}
          onChange={(e) => setSelCam(cameras.find((c) => c.id === e.target.value) ?? null)}
        >
          {cameras.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>

        {/* Date nav */}
        <div className="flex items-center gap-1">
          <button className="btn btn-ghost w-8 h-8 p-0" onClick={() => setSelDate((d) => shiftDate(d, -1))}>
            <ChevronLeft size={16} />
          </button>
          <label
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium cursor-pointer"
            style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
          >
            <Calendar size={14} className="text-t3" />
            <span>{fmtDate(selDate)}</span>
            <input
              type="date"
              className="sr-only"
              value={selDate}
              max={today}
              onChange={(e) => e.target.value && setSelDate(e.target.value)}
            />
          </label>
          <button
            className="btn btn-ghost w-8 h-8 p-0"
            onClick={() => setSelDate((d) => shiftDate(d, 1))}
            disabled={selDate >= today}
          >
            <ChevronRight size={16} />
          </button>
        </div>

        {/* Stats */}
        <div className="ml-auto flex items-center gap-2 text-xs text-t3 tabular-nums">
          {loading ? (
            <span>Carregando…</span>
          ) : (
            <>
              <Film size={13} />
              <span>{segments.length} segmentos · {totalMin}min</span>
            </>
          )}
        </div>
      </div>

      {/* ── Main area ───────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden">

        {/* Player */}
        <div className="flex-1 min-h-0 relative bg-black flex items-center justify-center">
          {loading ? (
            <div className="text-t3 text-sm flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-t-accent border-zinc-700 rounded-full animate-spin" />
              Carregando gravações…
            </div>
          ) : playbackUrl && playbackSeg ? (
            <VideoPlayer
              src={playbackUrl}
              name={`${selCam?.name} · ${fmtTime(playbackSeg.started_at)}`}
              className="w-full h-full object-contain"
              muted
              autoPlay
            />
          ) : (
            <div className="flex flex-col items-center gap-3 text-t3">
              {segments.length === 0 ? (
                <>
                  <VideoOff size={48} strokeWidth={1} />
                  <p className="text-sm">Nenhuma gravação em {fmtDate(selDate)}</p>
                </>
              ) : (
                <>
                  <Film size={48} strokeWidth={1} />
                  <p className="text-sm">Selecione um segmento para reproduzir</p>
                </>
              )}
            </div>
          )}

          {/* Active segment badge */}
          {playbackSeg && (
            <div
              className="absolute top-3 left-3 flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium"
              style={{ background: 'rgba(0,0,0,0.7)', color: '#fff', backdropFilter: 'blur(4px)' }}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
              {fmtTime(playbackSeg.started_at)} — {fmtTime(playbackSeg.ended_at)}
              <span className="text-zinc-400 ml-1">{fmtDuration(playbackSeg.duration_seconds)}</span>
            </div>
          )}
        </div>

        {/* ── Bottom panel ────────────────────────────────────────────── */}
        <div
          className="shrink-0 border-t"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
        >
          {/* Timeline scrubber */}
          {segments.length > 0 && (
            <div className="px-4 pt-3 pb-1">
              <ModernTimeline
                segments={segments}
                currentTime={playbackSeg ? new Date(playbackSeg.started_at) : new Date()}
                onSeek={handleTimelineSeek}
                isLoading={false}
                selectedDate={selDate}
              />
            </div>
          )}

          {/* Segment strip */}
          <div
            ref={listRef}
            className="flex gap-2 px-4 py-2.5 overflow-x-auto"
            style={{ scrollbarWidth: 'thin' }}
          >
            {segments.length === 0 && !loading && (
              <p className="text-xs text-t3 py-1">Nenhum segmento</p>
            )}
            {segments.map((seg) => {
              const isActive = playbackSeg?.id === seg.id
              const isMotion = seg.event_type === 'motion'
              const isEvent  = seg.event_type === 'event'
              const color    = isMotion ? '#d97706' : isEvent ? '#dc2626' : 'var(--accent)'
              return (
                <button
                  key={seg.id}
                  data-seg={seg.id}
                  onClick={() => playSeg(seg)}
                  className={clsx(
                    'shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition border',
                    isActive
                      ? 'text-white'
                      : 'text-t2 hover:text-t1 hover:border-zinc-600',
                  )}
                  style={{
                    background:   isActive ? 'rgba(59,130,246,0.15)' : 'var(--elevated)',
                    borderColor:  isActive ? 'var(--accent)' : 'var(--border)',
                  }}
                >
                  {isActive
                    ? <Play size={11} style={{ color }} />
                    : <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: color }} />
                  }
                  <span className="tabular-nums font-medium">{fmtTime(seg.started_at)}</span>
                  <span className="text-t3">{fmtDuration(seg.duration_seconds)}</span>
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
