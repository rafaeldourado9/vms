import { useCallback, useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'
import { Loader2, Play, Pause, SkipBack, SkipForward } from 'lucide-react'
import { clsx } from 'clsx'
import { vodService } from '@/services/vod'

interface RecordingPlayerProps {
  segmentIds: string[]
  cameraId: string
  startsAt: string
  endsAt: string
  className?: string
  onReady?: () => void
  onError?: (error: string) => void
}

export function RecordingPlayer({
  segmentIds,
  cameraId,
  startsAt,
  endsAt,
  className,
  onReady,
  onError,
}: RecordingPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const hlsRef = useRef<Hls | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const [streamUrl, setStreamUrl] = useState<string | null>(null)
  const [streamStatus, setStreamStatus] = useState<'creating' | 'generating' | 'ready' | 'failed'>('creating')
  const [error, setError] = useState<string | null>(null)
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(true)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  // Cria stream VOD
  useEffect(() => {
    let cancelled = false

    const createStream = async () => {
      try {
        setStreamStatus('creating')
        setError(null)

        // Cria stream VOD
        const stream = await vodService.createStream({
          camera_id: cameraId,
          segment_ids: segmentIds,
          starts_at: startsAt,
          ends_at: endsAt,
        })

        if (cancelled) return

        // Aguarda ficar pronto
        setStreamStatus('generating')
        const playlistUrl = await vodService.waitForReady(stream.id, 60000)

        if (cancelled) return

        setStreamUrl(playlistUrl)
        setStreamStatus('ready')
      } catch (err) {
        if (cancelled) return

        const errorMsg = err instanceof Error ? err.message : 'Erro ao criar stream VOD'
        setError(errorMsg)
        setStreamStatus('failed')
        onError?.(errorMsg)
      }
    }

    createStream()

    return () => {
      cancelled = true
    }
  }, [segmentIds, cameraId, startsAt, endsAt, onError])

  // Inicializa HLS quando streamUrl estiver disponível
  useEffect(() => {
    const video = videoRef.current
    if (!streamUrl || !video) return

    setLoading(true)

    // Cleanup HLS anterior
    if (hlsRef.current) {
      hlsRef.current.destroy()
      hlsRef.current = null
    }

    if (Hls.isSupported()) {
      const hls = new Hls({
        lowLatencyMode: false,
        maxBufferLength: 30,
        maxMaxBufferLength: 60,
        startLevel: -1,
        capLevelToPlayerSize: true,
        maxBufferSize: 60 * 1024 * 1024,
      })

      hlsRef.current = hls
      hls.loadSource(streamUrl)
      hls.attachMedia(video)

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        video.play().catch(() => {
          // Autoplay falhou, usuário precisa interagir
        })
      })

      hls.on(Hls.Events.ERROR, (_, data) => {
        if (data.fatal) {
          setError('Erro ao carregar stream HLS')
          onError?.('Erro ao carregar stream HLS')
        }
      })
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari nativo
      video.src = streamUrl
      video.addEventListener('loadedmetadata', () => {
        video.play().catch(() => {})
      })
    } else {
      setError('Seu navegador não suporta playback HLS')
    }

    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy()
        hlsRef.current = null
      }
    }
  }, [streamUrl, onError])

  // Atualiza tempo atual
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const updateTime = () => setCurrentTime(video.currentTime)
    const updateDuration = () => setDuration(video.duration)
    const handlePlaying = () => {
      setPlaying(true)
      setLoading(false)
      onReady?.()
    }
    const handlePause = () => setPlaying(false)
    const handleWaiting = () => setLoading(true)

    video.addEventListener('timeupdate', updateTime)
    video.addEventListener('loadedmetadata', updateDuration)
    video.addEventListener('playing', handlePlaying)
    video.addEventListener('pause', handlePause)
    video.addEventListener('waiting', handleWaiting)

    return () => {
      video.removeEventListener('timeupdate', updateTime)
      video.removeEventListener('loadedmetadata', updateDuration)
      video.removeEventListener('playing', handlePlaying)
      video.removeEventListener('pause', handlePause)
      video.removeEventListener('waiting', handleWaiting)
    }
  }, [onReady])

  const togglePlay = useCallback(() => {
    const video = videoRef.current
    if (!video) return

    if (video.paused) {
      video.play().catch(() => {})
    } else {
      video.pause()
    }
  }, [])

  const seekBy = useCallback((seconds: number) => {
    const video = videoRef.current
    if (!video || !duration) return

    const newTime = Math.max(0, Math.min(duration, video.currentTime + seconds))
    video.currentTime = newTime
  }, [duration])

  const formatTime = (seconds: number): string => {
    if (!seconds || !isFinite(seconds)) return '0:00'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  // Estado de loading/erro
  if (streamStatus === 'creating' || streamStatus === 'generating') {
    return (
      <div className={clsx('relative bg-black rounded-lg overflow-hidden', className)}>
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
          <Loader2 size={40} className="animate-spin text-blue-500" />
          <p className="text-sm text-zinc-400">
            {streamStatus === 'creating' ? 'Criando stream VOD...' : 'Gerando playlist HLS...'}
          </p>
          <p className="text-xs text-zinc-600">
            Isso pode levar alguns segundos
          </p>
        </div>
      </div>
    )
  }

  if (streamStatus === 'failed' || error) {
    return (
      <div className={clsx('relative bg-black rounded-lg overflow-hidden', className)}>
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
          <p className="text-sm text-red-400">Erro: {error || 'Falha ao criar stream'}</p>
          <button
            className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
            onClick={() => window.location.reload()}
          >
            Tentar novamente
          </button>
        </div>
      </div>
    )
  }

  // Player
  return (
    <div
      ref={containerRef}
      className={clsx('relative bg-black rounded-lg overflow-hidden group', className)}
    >
      <video
        ref={videoRef}
        className="w-full h-full object-contain"
        playsInline
      />

      {loading && !playing && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/60">
          <Loader2 size={32} className="animate-spin text-white/70" />
        </div>
      )}

      {/* Controles */}
      <div className="absolute bottom-0 left-0 right-0 flex items-center gap-3 px-4 py-3 bg-gradient-to-t from-black/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={() => seekBy(-10)}
          className="text-white hover:text-zinc-300 transition-colors"
          title="Voltar 10s"
        >
          <SkipBack size={18} />
        </button>

        <button
          onClick={togglePlay}
          className="text-white hover:text-zinc-300 transition-colors"
        >
          {playing ? <Pause size={20} /> : <Play size={20} />}
        </button>

        <button
          onClick={() => seekBy(10)}
          className="text-white hover:text-zinc-300 transition-colors"
          title="Avançar 10s"
        >
          <SkipForward size={18} />
        </button>

        {/* Timeline */}
        <div className="flex-1 flex items-center gap-2">
          <span className="text-xs text-white tabular-nums">
            {formatTime(currentTime)}
          </span>
          <input
            type="range"
            min={0}
            max={duration || 0}
            value={currentTime}
            onChange={(e) => {
              const video = videoRef.current
              if (video) {
                video.currentTime = Number(e.target.value)
              }
            }}
            className="flex-1 h-1 bg-zinc-600 rounded-full appearance-none cursor-pointer
                      [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 
                      [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full 
                      [&::-webkit-slider-thumb]:bg-blue-500"
          />
          <span className="text-xs text-white tabular-nums">
            {formatTime(duration)}
          </span>
        </div>
      </div>
    </div>
  )
}
