import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Brain,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Film,
  Layers,
  MapPin,
  RefreshCw,
  Search,
  Wifi,
  WifiOff,
  X,
} from 'lucide-react'
import { GoogleMap, InfoWindow, Marker, useJsApiLoader } from '@react-google-maps/api'
import { clsx } from 'clsx'
import { camerasService } from '@/services/cameras'
import { recordingsService } from '@/services/recordings'
import { useAuthStore } from '@/store/authStore'
import { Thumbnail } from '@/components/camera/Thumbnail'
import { VideoPlayer } from '@/components/camera/VideoPlayer'
import type { Camera, RecordingSegment } from '@/types'

const GOOGLE_MAPS_KEY =
  import.meta.env.VITE_GOOGLE_MAPS_KEY ?? import.meta.env.VITE_GOOGLE_MAPS_API_KEY ?? ''

const MINUTES_IN_DAY = 1440

const MAP_STYLE_DARK: google.maps.MapTypeStyle[] = [
  { elementType: 'geometry', stylers: [{ color: '#0f0f18' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#0a0a12' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#5a6477' }] },
  {
    featureType: 'administrative.locality',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#8a93a5' }],
  },
  { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#1d1d28' }] },
  { featureType: 'road', elementType: 'geometry.stroke', stylers: [{ color: '#16161e' }] },
  { featureType: 'road', elementType: 'labels.text.fill', stylers: [{ color: '#6b7280' }] },
  { featureType: 'road.highway', elementType: 'geometry', stylers: [{ color: '#2a2a38' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#0a1320' }] },
  { featureType: 'water', elementType: 'labels.text.fill', stylers: [{ color: '#3e4a5f' }] },
  { featureType: 'poi', stylers: [{ visibility: 'off' }] },
  { featureType: 'transit', stylers: [{ visibility: 'off' }] },
]

type FilterStatus = 'all' | 'online' | 'offline' | 'ia'

const hasCoords = (c: Camera): c is Camera & { latitude: number; longitude: number } =>
  typeof c.latitude === 'number' && typeof c.longitude === 'number'

const createMarkerIcon = (online: boolean, iaEnabled: boolean): google.maps.Symbol => ({
  path: google.maps.SymbolPath.CIRCLE,
  scale: 11,
  fillColor: online ? (iaEnabled ? '#3B82F6' : '#22C55E') : '#EF4444',
  fillOpacity: 1,
  strokeColor: '#ffffff',
  strokeWeight: 2,
})

function shiftDate(iso: string, days: number): string {
  const d = new Date(iso + 'T00:00:00')
  d.setDate(d.getDate() + days)
  return d.toISOString().split('T')[0]
}

function formatDateShort(iso: string): string {
  return new Date(iso + 'T00:00:00').toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export function MapPage() {
  const navigate = useNavigate()
  const token = useAuthStore((s) => s.tokens?.access_token ?? '')
  const timelineRef = useRef<HTMLDivElement>(null)

  // ─── Cameras ────────────────────────────────────────────────────────────────
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Camera | null>(null)
  const [filter, setFilter] = useState<FilterStatus>('all')
  const [search, setSearch] = useState('')
  const [center, setCenter] = useState({ lat: -14.235, lng: -51.925 })
  const [map, setMap] = useState<google.maps.Map | null>(null)

  // ─── Timeline ───────────────────────────────────────────────────────────────
  const [selDate, setSelDate] = useState(() => new Date().toISOString().split('T')[0])
  const [segments, setSegments] = useState<RecordingSegment[]>([])
  const [loadingSegs, setLoadingSegs] = useState(false)

  // ─── VOD playback ───────────────────────────────────────────────────────────
  const [playbackSeg, setPlaybackSeg] = useState<RecordingSegment | null>(null)
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null)

  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: GOOGLE_MAPS_KEY,
    libraries: ['places'],
  })

  // ─── Load cameras ────────────────────────────────────────────────────────────
  const loadCameras = useCallback(() => {
    setLoading(true)
    camerasService
      .list({ page_size: 500 })
      .then((list) => {
        setCameras(list)
        const withCoords = list.filter(hasCoords)
        if (withCoords.length > 0) {
          const avgLat = withCoords.reduce((s, c) => s + c.latitude, 0) / withCoords.length
          const avgLng = withCoords.reduce((s, c) => s + c.longitude, 0) / withCoords.length
          setCenter({ lat: avgLat, lng: avgLng })
        }
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    loadCameras()
  }, [loadCameras])

  // ─── Load segments when camera or date changes ───────────────────────────────
  useEffect(() => {
    if (!selected) {
      setSegments([])
      return
    }
    setLoadingSegs(true)
    setPlaybackSeg(null)
    setPlaybackUrl(null)

    const start = new Date(selDate + 'T00:00:00').toISOString()
    const end = new Date(selDate + 'T23:59:59.999').toISOString()

    recordingsService
      .listSegments({
        camera_id: selected.id,
        started_after: start,
        started_before: end,
        page_size: 500,
      })
      .then((res) => setSegments(res.items ?? []))
      .catch(() => setSegments([]))
      .finally(() => setLoadingSegs(false))
  }, [selected, selDate])

  // ─── Helpers ─────────────────────────────────────────────────────────────────
  const counts = useMemo(
    () => ({
      all: cameras.length,
      online: cameras.filter((c) => c.is_online).length,
      offline: cameras.filter((c) => !c.is_online).length,
      ia: cameras.filter((c) => c.ia_enabled === true).length,
    }),
    [cameras],
  )

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase()
    return cameras.filter((c) => {
      if (filter === 'online' && !c.is_online) return false
      if (filter === 'offline' && c.is_online) return false
      if (filter === 'ia' && c.ia_enabled !== true) return false
      if (q) {
        const hay = `${c.name} ${c.location ?? ''} ${c.address ?? ''}`.toLowerCase()
        if (!hay.includes(q)) return false
      }
      return true
    })
  }, [cameras, filter, search])

  const visibleWithCoords = visible.filter(hasCoords)

  const focusCamera = useCallback(
    (cam: Camera) => {
      setSelected(cam)
      if (hasCoords(cam) && map) {
        map.panTo({ lat: cam.latitude, lng: cam.longitude })
        map.setZoom(Math.max(map.getZoom() ?? 14, 15))
      }
    },
    [map],
  )

  const segmentMinutes = useCallback((seg: RecordingSegment) => {
    const start = new Date(seg.started_at)
    const startMin = start.getHours() * 60 + start.getMinutes()
    const durMin = Math.max(1, Math.ceil(seg.duration_seconds / 60))
    return { startMin, durMin }
  }, [])

  const buildPlaybackUrl = useCallback(
    (seg: RecordingSegment): string | null => {
      if (!token) return null
      const url = new URL(seg.file_path, window.location.origin)
      url.searchParams.set('token', token)
      return url.toString()
    },
    [token],
  )

  const openSegment = useCallback(
    (seg: RecordingSegment) => {
      const url = buildPlaybackUrl(seg)
      if (url) {
        setPlaybackSeg(seg)
        setPlaybackUrl(url)
      }
    },
    [buildPlaybackUrl],
  )

  const handleTimelineClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!timelineRef.current) return
      const rect = timelineRef.current.getBoundingClientRect()
      const x = e.clientX - rect.left
      const minutes = Math.floor((x / rect.width) * MINUTES_IN_DAY)
      const hit = segments.find((s) => {
        const { startMin, durMin } = segmentMinutes(s)
        return minutes >= startMin && minutes <= startMin + durMin
      })
      if (hit) openSegment(hit)
    },
    [segments, segmentMinutes, openSegment],
  )

  const closePlayback = useCallback(() => {
    setPlaybackSeg(null)
    setPlaybackUrl(null)
  }, [])

  // ─── No API key fallback ─────────────────────────────────────────────────────
  if (!GOOGLE_MAPS_KEY) {
    return (
      <div className="-m-4 h-[calc(100vh-3.5rem)] flex items-center justify-center p-8">
        <div className="card max-w-md p-8 text-center space-y-3">
          <Layers size={40} className="text-t3 mx-auto" />
          <p className="text-t2 font-medium">Google Maps não configurado</p>
          <p className="text-xs text-t3">
            Defina <code className="text-accent">VITE_GOOGLE_MAPS_KEY</code> no{' '}
            <code>frontend/.env</code> e reconstrua o container frontend.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="-m-4 h-[calc(100vh-3.5rem)] relative overflow-hidden">
      {/* ── Map background ────────────────────────────────────────────────── */}
      <div className="absolute inset-0">
        {loadError ? (
          <div className="h-full w-full flex items-center justify-center text-sm text-t3">
            Erro ao carregar Google Maps
          </div>
        ) : !isLoaded ? (
          <div
            className="h-full w-full flex items-center justify-center text-sm text-t3"
            style={{ background: '#0f0f18' }}
          >
            Carregando mapa…
          </div>
        ) : (
          <GoogleMap
            mapContainerStyle={{ width: '100%', height: '100%' }}
            center={center}
            zoom={visibleWithCoords.length > 0 ? 13 : 5}
            options={{
              styles: MAP_STYLE_DARK,
              disableDefaultUI: false,
              zoomControl: true,
              zoomControlOptions: { position: google.maps.ControlPosition.LEFT_BOTTOM },
              mapTypeControl: false,
              streetViewControl: false,
              fullscreenControl: false,
              backgroundColor: '#0f0f18',
              gestureHandling: 'greedy',
            }}
            onLoad={(m) => setMap(m)}
            onUnmount={() => setMap(null)}
          >
            {visibleWithCoords.map((cam) => (
              <Marker
                key={cam.id}
                position={{ lat: cam.latitude, lng: cam.longitude }}
                icon={createMarkerIcon(cam.is_online, cam.ia_enabled === true)}
                onClick={() => focusCamera(cam)}
                title={cam.name}
              />
            ))}

            {selected && hasCoords(selected) && !playbackSeg && (
              <InfoWindow
                position={{ lat: selected.latitude, lng: selected.longitude }}
                onCloseClick={() => setSelected(null)}
              >
                <InfoWindowContent
                  cam={selected}
                  onNavigate={() => navigate(`/cameras/${selected.id}`)}
                />
              </InfoWindow>
            )}
          </GoogleMap>
        )}
      </div>

      {/* ── Top-left filter chips ─────────────────────────────────────────── */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
        <div
          className="flex items-center gap-1 p-1 rounded-xl shadow-xl backdrop-blur"
          style={{ background: 'rgba(17,17,24,0.85)', border: '1px solid var(--border)' }}
        >
          {(
            [
              { id: 'all', label: 'Todas', count: counts.all, icon: MapPin },
              { id: 'online', label: 'Online', count: counts.online, icon: Wifi },
              { id: 'offline', label: 'Offline', count: counts.offline, icon: WifiOff },
              { id: 'ia', label: 'Com IA', count: counts.ia, icon: Brain },
            ] as { id: FilterStatus; label: string; count: number; icon: React.ElementType }[]
          ).map(({ id, label, count, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setFilter(id)}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition',
                filter === id ? 'text-white' : 'text-t2 hover:text-t1 hover:bg-elevated',
              )}
              style={filter === id ? { background: 'var(--accent)' } : {}}
            >
              <Icon size={12} />
              <span>{label}</span>
              <span className="opacity-70 tabular-nums">{count}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── Bottom timeline panel (aparece quando câmera selecionada) ─────── */}
      {selected && (
        <div
          className="absolute bottom-4 left-4 z-10 rounded-2xl shadow-2xl backdrop-blur overflow-hidden"
          style={{
            right: 'calc(1rem + 20rem + 1rem)', // gap + sidebar width + right margin
            background: 'rgba(17,17,24,0.92)',
            border: '1px solid var(--border)',
          }}
        >
          {/* Timeline header */}
          <div
            className="flex items-center gap-3 px-4 py-2.5 border-b"
            style={{ borderColor: 'var(--border)' }}
          >
            <Film size={14} className="text-accent shrink-0" />
            <p className="text-xs font-semibold text-t1 truncate flex-1">{selected.name}</p>

            {/* Date navigation */}
            <div className="flex items-center gap-1 shrink-0">
              <button
                className="w-6 h-6 flex items-center justify-center rounded hover:bg-elevated transition text-t2"
                onClick={() => setSelDate((d) => shiftDate(d, -1))}
              >
                <ChevronLeft size={13} />
              </button>
              <div className="flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] text-t2 tabular-nums"
                style={{ background: 'var(--elevated)' }}>
                <Calendar size={10} className="text-t3" />
                {formatDateShort(selDate)}
              </div>
              <button
                className="w-6 h-6 flex items-center justify-center rounded hover:bg-elevated transition text-t2"
                onClick={() => setSelDate((d) => shiftDate(d, 1))}
                disabled={selDate >= new Date().toISOString().split('T')[0]}
              >
                <ChevronRight size={13} />
              </button>
            </div>

            <span className="text-[10px] text-t3 tabular-nums shrink-0">
              {loadingSegs ? '…' : `${segments.length} seg.`}
            </span>

            <button
              className="w-6 h-6 flex items-center justify-center rounded hover:bg-elevated transition text-t3 hover:text-t1 shrink-0"
              onClick={() => setSelected(null)}
            >
              <X size={13} />
            </button>
          </div>

          {/* 24h bar */}
          <div className="px-4 py-3 space-y-1.5">
            <div className="flex justify-between text-[9px] text-t3 tabular-nums select-none px-px">
              <span>00:00</span>
              <span>06:00</span>
              <span>12:00</span>
              <span>18:00</span>
              <span>24:00</span>
            </div>
            <div
              ref={timelineRef}
              className="relative h-7 rounded-lg overflow-hidden cursor-crosshair"
              style={{ background: 'var(--elevated)' }}
              onClick={handleTimelineClick}
            >
              {/* Hour ticks */}
              {Array.from({ length: 23 }, (_, i) => i + 1).map((h) => (
                <div
                  key={h}
                  className="absolute top-0 bottom-0 w-px opacity-30"
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
                    className="absolute top-1 bottom-1 rounded-sm cursor-pointer transition hover:opacity-100"
                    style={{
                      left: `${(startMin / MINUTES_IN_DAY) * 100}%`,
                      width: `${Math.max(0.2, (durMin / MINUTES_IN_DAY) * 100)}%`,
                      background: isActive ? '#10b981' : 'var(--accent)',
                      opacity: isActive ? 1 : 0.8,
                      boxShadow: isActive ? '0 0 0 1px #10b981' : undefined,
                    }}
                    onClick={(e) => {
                      e.stopPropagation()
                      openSegment(seg)
                    }}
                    title={`${new Date(seg.started_at).toLocaleTimeString('pt-BR')} · ${Math.round(seg.duration_seconds)}s`}
                  />
                )
              })}

              {segments.length === 0 && !loadingSegs && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-[10px] text-t3">Sem gravações neste dia</span>
                </div>
              )}

              {loadingSegs && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-[10px] text-t3 animate-pulse">Carregando…</span>
                </div>
              )}
            </div>

            {/* Hint */}
            {segments.length > 0 && !playbackSeg && (
              <p className="text-[9px] text-t3 text-center">
                Clique em um segmento para reproduzir
              </p>
            )}
            {playbackSeg && (
              <p className="text-[9px] text-accent text-center tabular-nums">
                Reproduzindo{' '}
                {new Date(playbackSeg.started_at).toLocaleTimeString('pt-BR', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
                {' — '}
                {new Date(playbackSeg.ended_at).toLocaleTimeString('pt-BR', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </p>
            )}
          </div>
        </div>
      )}

      {/* ── Right sidebar ─────────────────────────────────────────────────── */}
      <aside
        className="absolute top-4 right-4 bottom-4 w-80 rounded-2xl shadow-2xl flex flex-col overflow-hidden z-10 backdrop-blur"
        style={{
          background: 'rgba(17,17,24,0.92)',
          border: '1px solid var(--border)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-3 border-b shrink-0"
          style={{ borderColor: 'var(--border)' }}
        >
          <div>
            <p className="text-sm font-semibold text-t1">Câmeras</p>
            <p className="text-[10px] text-t3">
              {visible.length} de {cameras.length}
            </p>
          </div>
          <button
            className="btn btn-ghost w-8 h-8 p-0"
            onClick={loadCameras}
            title="Atualizar"
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        {/* Search */}
        <div className="px-4 py-2 border-b shrink-0" style={{ borderColor: 'var(--border)' }}>
          <div className="relative">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-t3" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar câmera…"
              className="input text-xs py-1.5 pl-7 w-full"
            />
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {loading && visible.length === 0 ? (
            <p className="text-xs text-t3 text-center py-8">Carregando…</p>
          ) : visible.length === 0 ? (
            <p className="text-xs text-t3 text-center py-8">Nenhuma câmera</p>
          ) : (
            <ul className="space-y-2 p-2">
              {visible.map((cam) => {
                const isActive = selected?.id === cam.id
                const coords = hasCoords(cam)
                return (
                  <li
                    key={cam.id}
                    className={clsx(
                      'rounded-xl cursor-pointer transition overflow-hidden border',
                      isActive
                        ? 'border-accent/40 bg-accent/10'
                        : 'border-transparent hover:border-white/10 hover:bg-elevated/60',
                    )}
                    onClick={() => focusCamera(cam)}
                  >
                    {/* Thumbnail */}
                    <div className="relative aspect-video bg-black">
                      <Thumbnail cameraId={cam.id} className="w-full h-full" />
                      <div
                        className={clsx(
                          'absolute top-1.5 right-1.5 w-2 h-2 rounded-full shadow',
                          cam.is_online
                            ? cam.ia_enabled
                              ? 'bg-blue-500'
                              : 'bg-green-500'
                            : 'bg-red-500',
                        )}
                      />
                      {!coords && (
                        <span
                          className="absolute top-1.5 left-1.5 text-[9px] px-1 rounded text-amber-500"
                          title="Sem coordenadas GPS"
                          style={{ background: 'rgba(245,158,11,0.18)' }}
                        >
                          sem GPS
                        </span>
                      )}
                      {isActive && (
                        <div
                          className="absolute bottom-0 left-0 right-0 h-0.5"
                          style={{ background: 'var(--accent)' }}
                        />
                      )}
                    </div>

                    {/* Info */}
                    <div className="px-2.5 py-2">
                      <p className="text-xs font-medium text-t1 truncate">{cam.name}</p>
                      {(cam.address || cam.location) && (
                        <p className="text-[10px] text-t3 truncate mt-0.5">
                          {cam.address ?? cam.location}
                        </p>
                      )}
                      <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                        <span
                          className={clsx(
                            'text-[9px] px-1.5 py-0.5 rounded font-medium',
                            cam.is_online
                              ? 'bg-green-900/50 text-green-400'
                              : 'bg-red-900/50 text-red-400',
                          )}
                        >
                          {cam.is_online ? 'Online' : 'Offline'}
                        </span>
                        {cam.ia_enabled && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded font-medium bg-blue-900/50 text-blue-400 flex items-center gap-0.5">
                            <Brain size={8} />
                            IA
                          </span>
                        )}
                        <span className="text-[9px] px-1.5 py-0.5 rounded font-medium bg-white/5 text-t3 ml-auto uppercase">
                          {cam.stream_protocol.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {/* Footer legend */}
        <div
          className="px-4 py-2 border-t text-[10px] flex items-center justify-between shrink-0"
          style={{ borderColor: 'var(--border)', color: 'var(--text-3)' }}
        >
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500" /> On
            </span>
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500" /> IA
            </span>
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500" /> Off
            </span>
          </div>
          {selected && (
            <span className="text-accent text-[9px]">
              {segments.length} gravações
            </span>
          )}
        </div>
      </aside>

      {/* ── VOD Popup (floating over map) ─────────────────────────────────── */}
      {playbackSeg && playbackUrl && (
        <div
          className="absolute inset-0 z-20 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(4px)' }}
          onClick={closePlayback}
        >
          <div
            className="rounded-2xl overflow-hidden shadow-2xl flex flex-col"
            style={{
              width: 'min(760px, calc(100vw - 24rem - 3rem))',
              background: 'rgba(17,17,24,0.97)',
              border: '1px solid var(--border)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Popup header */}
            <div
              className="flex items-center gap-3 px-4 py-3 border-b"
              style={{ borderColor: 'var(--border)' }}
            >
              <Film size={14} className="text-accent shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-t1 truncate">{selected?.name}</p>
                <p className="text-[10px] text-t3 tabular-nums">
                  {new Date(playbackSeg.started_at).toLocaleString('pt-BR', {
                    day: '2-digit', month: '2-digit', year: 'numeric',
                    hour: '2-digit', minute: '2-digit', second: '2-digit',
                  })}
                  {' — '}
                  {new Date(playbackSeg.ended_at).toLocaleTimeString('pt-BR', {
                    hour: '2-digit', minute: '2-digit', second: '2-digit',
                  })}
                  {' · '}
                  {Math.round(playbackSeg.duration_seconds)}s
                </p>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  className="text-xs text-accent hover:text-t1 transition"
                  onClick={() => selected && navigate(`/cameras/${selected.id}`)}
                >
                  Ver câmera →
                </button>
                <button
                  className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-elevated transition text-t3 hover:text-t1"
                  onClick={closePlayback}
                >
                  <X size={14} />
                </button>
              </div>
            </div>

            {/* Player */}
            <VideoPlayer
              src={playbackUrl}
              name={selected?.name}
              autoPlay
              muted={false}
              className="w-full aspect-video"
            />

            {/* Segment strip — click other segments */}
            {segments.length > 1 && (
              <div
                className="px-4 py-2 border-t flex items-center gap-2 overflow-x-auto"
                style={{ borderColor: 'var(--border)' }}
              >
                <span className="text-[9px] text-t3 shrink-0">Segmentos:</span>
                {segments
                  .slice()
                  .sort((a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime())
                  .map((seg) => {
                    const isActive = playbackSeg.id === seg.id
                    return (
                      <button
                        key={seg.id}
                        onClick={() => openSegment(seg)}
                        className={clsx(
                          'shrink-0 text-[9px] px-2 py-1 rounded-md tabular-nums transition',
                          isActive
                            ? 'text-white'
                            : 'text-t3 hover:text-t1 hover:bg-elevated',
                        )}
                        style={isActive ? { background: 'var(--accent)' } : {}}
                      >
                        {new Date(seg.started_at).toLocaleTimeString('pt-BR', {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </button>
                    )
                  })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── InfoWindow popup (map marker click) ───────────────────────────────────────

function InfoWindowContent({ cam, onNavigate }: { cam: Camera; onNavigate: () => void }) {
  return (
    <div
      style={{
        background: '#111118',
        color: '#e2e8f0',
        borderRadius: 8,
        padding: 12,
        minWidth: 240,
      }}
    >
      {/* Thumbnail */}
      <div
        style={{
          position: 'relative',
          aspectRatio: '16/9',
          borderRadius: 6,
          overflow: 'hidden',
          marginBottom: 10,
          background: '#000',
        }}
      >
        <Thumbnail cameraId={cam.id} className="w-full h-full" />
        <div
          style={{
            position: 'absolute',
            top: 6,
            right: 6,
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: cam.is_online ? '#22C55E' : '#EF4444',
            boxShadow: '0 0 4px rgba(0,0,0,0.5)',
          }}
        />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <strong style={{ fontSize: 13 }}>{cam.name}</strong>
      </div>
      {(cam.address || cam.location) && (
        <p style={{ fontSize: 11, color: '#94a3b8', marginBottom: 6 }}>
          {cam.address ?? cam.location}
        </p>
      )}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <span
          style={{
            fontSize: 10,
            padding: '2px 6px',
            borderRadius: 4,
            background: cam.is_online ? '#166534' : '#7f1d1d',
            color: cam.is_online ? '#4ade80' : '#f87171',
          }}
        >
          {cam.is_online ? 'Online' : 'Offline'}
        </span>
        {cam.ia_enabled && (
          <span
            style={{
              fontSize: 10,
              padding: '2px 6px',
              borderRadius: 4,
              background: '#1e3a5f',
              color: '#60a5fa',
            }}
          >
            IA Ativa
          </span>
        )}
        <span
          style={{
            fontSize: 10,
            padding: '2px 6px',
            borderRadius: 4,
            background: '#1a1a24',
            color: '#94a3b8',
          }}
        >
          {cam.stream_protocol.replace('_', ' ').toUpperCase()}
        </span>
      </div>
      <button
        style={{
          marginTop: 10,
          width: '100%',
          padding: '6px 12px',
          borderRadius: 6,
          background: '#3B82F6',
          color: '#fff',
          fontSize: 12,
          border: 'none',
          cursor: 'pointer',
        }}
        onClick={onNavigate}
      >
        Ver Câmera →
      </button>
    </div>
  )
}
