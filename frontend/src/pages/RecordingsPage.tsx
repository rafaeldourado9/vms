import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Calendar, ChevronLeft, ChevronRight, Download, Scissors } from 'lucide-react'
import { clsx } from 'clsx'
import { camerasService } from '@/services/cameras'
import { recordingsService } from '@/services/recordings'
import { VideoPlayer } from '@/components/camera/VideoPlayer'
import { PageSpinner } from '@/components/ui/Spinner'
import { Modal } from '@/components/ui/Modal'
import { useAuthStore } from '@/store/authStore'
import type { Camera, RecordingSegment } from '@/types'
import toast from 'react-hot-toast'

const MINUTES_IN_DAY = 1440

function minutesToTime(m: number): string {
  const h = Math.floor(m / 60).toString().padStart(2, '0')
  const min = Math.floor(m % 60).toString().padStart(2, '0')
  return `${h}:${min}`
}

function timeToMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number)
  return h * 60 + m
}

function shiftDate(iso: string, days: number): string {
  const d = new Date(iso)
  d.setDate(d.getDate() + days)
  return d.toISOString().split('T')[0]
}

function formatDateLong(iso: string): string {
  return new Date(iso + 'T00:00:00').toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  })
}

export function RecordingsPage() {
  const token = useAuthStore((s) => s.tokens?.access_token ?? '')
  const timelineRef = useRef<HTMLDivElement>(null)

  const [cameras, setCameras] = useState<Camera[]>([])
  const [selCam, setSelCam] = useState<Camera | null>(null)
  const [selDate, setSelDate] = useState(() => new Date().toISOString().split('T')[0])
  const [segments, setSegments] = useState<RecordingSegment[]>([])
  const [loading, setLoading] = useState(false)

  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null)
  const [playbackSeg, setPlaybackSeg] = useState<RecordingSegment | null>(null)

  const [clipModal, setClipModal] = useState(false)
  const [clipName, setClipName] = useState('')
  const [clipRange, setClipRange] = useState<[number, number]>([0, 60])

  useEffect(() => {
    camerasService.list({ page_size: 200 }).then((list) => {
      setCameras(list)
      if (list.length > 0) setSelCam(list[0])
    })
  }, [])

  useEffect(() => {
    if (!selCam) {
      setSegments([])
      return
    }
    setLoading(true)
    setPlaybackUrl(null)
    setPlaybackSeg(null)

    const start = new Date(selDate + 'T00:00:00')
    const end = new Date(selDate + 'T23:59:59.999')

    recordingsService
      .listSegments({
        camera_id: selCam.id,
        started_after: start.toISOString(),
        started_before: end.toISOString(),
        page_size: 500,
      })
      .then((res) => setSegments(res.items ?? []))
      .catch(() => setSegments([]))
      .finally(() => setLoading(false))
  }, [selCam, selDate])

  const buildPlaybackUrl = useCallback(
    (seg: RecordingSegment): string | null => {
      if (!token) return null
      const url = new URL(seg.file_path, window.location.origin)
      url.searchParams.set('token', token)
      return url.toString()
    },
    [token],
  )

  const handleSegmentClick = useCallback(
    (seg: RecordingSegment) => {
      const url = buildPlaybackUrl(seg)
      if (url) {
        setPlaybackUrl(url)
        setPlaybackSeg(seg)
      }
    },
    [buildPlaybackUrl],
  )

  const handleDownload = useCallback(
    (seg: RecordingSegment) => {
      const url = buildPlaybackUrl(seg)
      if (!url) return
      const a = document.createElement('a')
      a.href = url
      a.download = `recording_${seg.camera_id}_${seg.started_at}.mp4`
      a.click()
    },
    [buildPlaybackUrl],
  )

  const segmentMinutes = useCallback((seg: RecordingSegment) => {
    const start = new Date(seg.started_at)
    const startMin = start.getHours() * 60 + start.getMinutes()
    const durMin = Math.max(1, Math.ceil(seg.duration_seconds / 60))
    return { startMin, durMin }
  }, [])

  const handleTimelineClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!timelineRef.current) return
      const rect = timelineRef.current.getBoundingClientRect()
      const x = e.clientX - rect.left
      const minutes = Math.floor((x / rect.width) * MINUTES_IN_DAY)

      // Try to play a segment under the click
      const hit = segments.find((s) => {
        const { startMin, durMin } = segmentMinutes(s)
        return minutes >= startMin && minutes <= startMin + durMin
      })
      if (hit) {
        handleSegmentClick(hit)
      }

      // Pre-select ±5min range for clip creation
      setClipRange([Math.max(0, minutes - 5), Math.min(MINUTES_IN_DAY, minutes + 5)])
    },
    [segments, segmentMinutes, handleSegmentClick],
  )

  const totalDurationMin = useMemo(
    () => segments.reduce((a, s) => a + s.duration_seconds / 60, 0),
    [segments],
  )

  const handleCreateClip = useCallback(async () => {
    if (!selCam) return
    const base = new Date(selDate + 'T00:00:00')
    const startsAt = new Date(base.getTime() + clipRange[0] * 60_000).toISOString()
    const endsAt = new Date(base.getTime() + clipRange[1] * 60_000).toISOString()
    try {
      await recordingsService.createClip({
        camera_id: selCam.id,
        starts_at: startsAt,
        ends_at: endsAt,
      })
      toast.success('Clipe solicitado! Processando em background…')
      setClipModal(false)
      setClipName('')
    } catch {
      toast.error('Erro ao criar clipe')
    }
  }, [selCam, selDate, clipRange])

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Controls row */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          className="input max-w-xs"
          value={selCam?.id ?? ''}
          onChange={(e) => {
            const cam = cameras.find((c) => c.id === e.target.value)
            setSelCam(cam ?? null)
          }}
        >
          {cameras.length === 0 && <option value="">Sem câmeras</option>}
          {cameras.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>

        <div className="flex items-center gap-1">
          <button
            className="btn btn-ghost w-8 h-8 p-0"
            onClick={() => setSelDate((d) => shiftDate(d, -1))}
            title="Dia anterior"
          >
            <ChevronLeft size={16} />
          </button>
          <div
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          >
            <Calendar size={14} className="text-t3" />
            {formatDateLong(selDate)}
          </div>
          <button
            className="btn btn-ghost w-8 h-8 p-0"
            onClick={() => setSelDate((d) => shiftDate(d, 1))}
            disabled={selDate >= new Date().toISOString().split('T')[0]}
            title="Próximo dia"
          >
            <ChevronRight size={16} />
          </button>
        </div>

        <input
          type="date"
          className="input max-w-[160px]"
          value={selDate}
          max={new Date().toISOString().split('T')[0]}
          onChange={(e) => setSelDate(e.target.value)}
        />

        {selCam && (
          <span className="text-xs text-t3 ml-auto tabular-nums">
            {segments.length} segmento(s) · {Math.round(totalDurationMin)}min gravado(s)
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Player */}
        <div className="lg:col-span-3 space-y-3">
          <div
            className="rounded-xl border overflow-hidden"
            style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
          >
            {playbackUrl && playbackSeg ? (
              <>
                <VideoPlayer
                  src={playbackUrl}
                  name={`Gravação ${new Date(playbackSeg.started_at).toLocaleTimeString('pt-BR')}`}
                  className="w-full aspect-video"
                  muted
                  autoPlay
                />
                <div
                  className="flex items-center justify-between px-4 py-2 border-t text-xs"
                  style={{ borderColor: 'var(--border)' }}
                >
                  <span className="text-t2 tabular-nums">
                    {new Date(playbackSeg.started_at).toLocaleTimeString('pt-BR')} —{' '}
                    {new Date(playbackSeg.ended_at).toLocaleTimeString('pt-BR')}
                  </span>
                  <button
                    onClick={() => {
                      setPlaybackUrl(null)
                      setPlaybackSeg(null)
                    }}
                    className="text-t3 hover:text-t1 transition"
                  >
                    Fechar
                  </button>
                </div>
              </>
            ) : (
              <div className="aspect-video flex flex-col items-center justify-center text-t3 gap-3">
                <Calendar size={40} className="text-t3/50" />
                <p className="text-sm">Clique na timeline ou em um segmento para reproduzir</p>
              </div>
            )}
          </div>

          <button
            className="btn btn-primary w-full gap-2"
            disabled={!selCam || segments.length === 0}
            onClick={() => setClipModal(true)}
          >
            <Scissors size={15} />
            Criar clipe do período
          </button>
        </div>

        {/* Timeline + list */}
        <div
          className="lg:col-span-2 rounded-xl border p-4 space-y-4"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
        >
          <div>
            <p className="text-sm font-semibold text-t1">Timeline — {formatDateLong(selDate)}</p>
            <p className="text-xs text-t3 mt-0.5">
              {loading ? 'Carregando…' : `${segments.length} segmentos gravados`}
            </p>
          </div>

          {loading ? (
            <PageSpinner />
          ) : (
            <>
              {/* 24h bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-[10px] text-t3 tabular-nums">
                  <span>00:00</span>
                  <span>06:00</span>
                  <span>12:00</span>
                  <span>18:00</span>
                  <span>24:00</span>
                </div>
                <div
                  ref={timelineRef}
                  className="relative h-9 rounded-lg overflow-hidden cursor-crosshair"
                  style={{ background: 'var(--elevated)' }}
                  onClick={handleTimelineClick}
                >
                  {/* Hour ticks */}
                  {Array.from({ length: 23 }, (_, i) => i + 1).map((h) => (
                    <div
                      key={h}
                      className="absolute top-0 bottom-0 w-px opacity-40"
                      style={{ left: `${(h / 24) * 100}%`, background: 'var(--border)' }}
                    />
                  ))}

                  {/* Segments */}
                  {segments.map((seg) => {
                    const { startMin, durMin } = segmentMinutes(seg)
                    const isActive = playbackSeg?.id === seg.id
                    return (
                      <div
                        key={seg.id}
                        className="absolute top-1 bottom-1 rounded-sm transition"
                        style={{
                          left: `${(startMin / MINUTES_IN_DAY) * 100}%`,
                          width: `${Math.max(0.15, (durMin / MINUTES_IN_DAY) * 100)}%`,
                          background: isActive ? '#10b981' : 'var(--accent)',
                          opacity: isActive ? 1 : 0.85,
                          boxShadow: isActive ? '0 0 0 1px #10b981' : undefined,
                        }}
                        onClick={(e) => {
                          e.stopPropagation()
                          handleSegmentClick(seg)
                        }}
                        title={`${new Date(seg.started_at).toLocaleTimeString('pt-BR')} · ${Math.round(
                          seg.duration_seconds,
                        )}s`}
                      />
                    )
                  })}

                  {/* Clip range highlight */}
                  <div
                    className="absolute top-0 bottom-0 opacity-30 pointer-events-none"
                    style={{
                      left: `${(clipRange[0] / MINUTES_IN_DAY) * 100}%`,
                      width: `${((clipRange[1] - clipRange[0]) / MINUTES_IN_DAY) * 100}%`,
                      background: '#F59E0B',
                      borderLeft: '1px solid #F59E0B',
                      borderRight: '1px solid #F59E0B',
                    }}
                  />
                </div>
              </div>

              {/* Segment list */}
              <div className="space-y-1 max-h-[420px] overflow-y-auto pr-1">
                {segments.length === 0 ? (
                  <p className="text-xs text-t3 text-center py-6">Nenhuma gravação neste dia</p>
                ) : (
                  segments
                    .slice()
                    .sort(
                      (a, b) =>
                        new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
                    )
                    .map((seg) => {
                      const isActive = playbackSeg?.id === seg.id
                      return (
                        <div
                          key={seg.id}
                          className={clsx(
                            'flex items-center gap-2 px-3 py-2 rounded-lg text-xs cursor-pointer transition',
                            isActive ? 'bg-emerald-500/10' : 'hover:bg-elevated',
                          )}
                          onClick={() => handleSegmentClick(seg)}
                        >
                          <div
                            className={clsx(
                              'w-1.5 h-1.5 rounded-full shrink-0',
                              isActive ? 'bg-emerald-500' : 'bg-accent',
                            )}
                          />
                          <span className="text-t1 font-medium tabular-nums">
                            {new Date(seg.started_at).toLocaleTimeString('pt-BR', {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                            {' — '}
                            {new Date(seg.ended_at).toLocaleTimeString('pt-BR', {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </span>
                          <span className="text-t3 ml-auto tabular-nums">
                            {Math.round(seg.duration_seconds / 60)}min
                          </span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleDownload(seg)
                            }}
                            className="p-1 rounded text-t3 hover:text-t1 transition"
                            title="Download"
                          >
                            <Download size={12} />
                          </button>
                        </div>
                      )
                    })
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Clip modal */}
      <Modal
        open={clipModal}
        onClose={() => setClipModal(false)}
        title="Criar clipe"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setClipModal(false)}>
              Cancelar
            </button>
            <button
              className="btn btn-primary gap-1.5"
              onClick={handleCreateClip}
              disabled={clipRange[1] <= clipRange[0]}
            >
              <Scissors size={14} />
              Criar clipe
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="label">Nome do clipe (opcional)</label>
            <input
              className="input"
              placeholder={`clip_${selDate}`}
              value={clipName}
              onChange={(e) => setClipName(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Início</label>
              <input
                type="time"
                className="input"
                value={minutesToTime(clipRange[0])}
                onChange={(e) => setClipRange((r) => [timeToMinutes(e.target.value), r[1]])}
              />
            </div>
            <div>
              <label className="label">Fim</label>
              <input
                type="time"
                className="input"
                value={minutesToTime(clipRange[1])}
                onChange={(e) => setClipRange((r) => [r[0], timeToMinutes(e.target.value)])}
              />
            </div>
          </div>
          <p className="text-xs text-t3">
            Câmera: <strong className="text-t2">{selCam?.name ?? '—'}</strong> · Data:{' '}
            <strong className="text-t2">{selDate}</strong> · Duração:{' '}
            <strong className="text-t2">{Math.max(0, clipRange[1] - clipRange[0])}min</strong>
          </p>
        </div>
      </Modal>
    </div>
  )
}
