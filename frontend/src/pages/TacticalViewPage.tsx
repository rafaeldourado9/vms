import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import { createPortal } from 'react-dom'
import {
  MapContainer, TileLayer, Marker, useMap,
} from 'react-leaflet'
import L from 'leaflet'
import type { LeafletMouseEvent } from 'leaflet'
import 'leaflet/dist/leaflet.css'
import {
  Cctv, MapPin, Search, X, RefreshCw,
  Wifi, WifiOff, Filter,
} from 'lucide-react'
import { camerasService } from '@/services/cameras'
import { useCameraStore } from '@/store/cameraStore'
import { TacticalTimelineModal } from '@/components/tactical/TacticalTimelineModal'
import { Thumbnail } from '@/components/camera/Thumbnail'
import { Link } from 'react-router-dom'
import type { Camera } from '@/types'

// ── Leaflet icon fix ──────────────────────────────────────────────────────────
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
L.Icon.Default.mergeOptions({ iconRetinaUrl: '', iconUrl: '', shadowUrl: '' })

function makeCameraIcon(online: boolean, active: boolean): L.DivIcon {
  const fill   = online ? '#22C55E' : '#EF4444'
  const border = active ? '#3B82F6' : 'rgba(255,255,255,0.75)'
  const bw     = active ? 2.5 : 1.5
  const ring   = online
    ? `<div style="position:absolute;inset:-5px;border-radius:50%;border:2px solid #22C55E40;animation:ping 2s cubic-bezier(0,0,0.2,1) infinite;pointer-events:none"></div>`
    : ''
  const html = `
    <div style="position:relative;width:32px;height:32px">
      ${ring}
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="16" cy="16" r="11" fill="#0A0A0F" fill-opacity="0.85"/>
        <circle cx="16" cy="16" r="9" fill="${fill}" stroke="${border}" stroke-width="${bw}"/>
        <rect x="11" y="13" width="7" height="5" rx="1" fill="white" opacity="0.92"/>
        <path d="M19 13.8L22.5 12.5V19.5L19 18.2V13.8Z" fill="white" opacity="0.92"/>
      </svg>
    </div>`
  return L.divIcon({ html, className: '', iconSize: [32, 32], iconAnchor: [16, 16], popupAnchor: [0, -20] })
}

// ── Hover preview state ───────────────────────────────────────────────────────
interface HoverState {
  camera: Camera
  x: number
  y: number
}

// ── Floating hover card (portal, pointer-events: none) ───────────────────────
function HoverCard({ hover, isOnline }: { hover: HoverState; isOnline: boolean }) {
  const CARD_W = 220
  const CARD_H = 160  // approx

  // Smart positioning: flip left if near right edge, flip down if near top
  const vw = window.innerWidth
  const offsetX = 18
  const offsetY = -CARD_H - 18

  const rawX = hover.x + offsetX
  const rawY = hover.y + offsetY

  const left = rawX + CARD_W > vw ? hover.x - CARD_W - offsetX : rawX
  const top  = rawY < 0 ? hover.y + 20 : rawY

  return createPortal(
    <div
      style={{
        position: 'fixed',
        left,
        top,
        width: CARD_W,
        zIndex: 9999,
        pointerEvents: 'none',
        fontFamily: 'Inter, system-ui, sans-serif',
        animation: 'hoverCardIn 0.12s ease-out',
      }}
    >
      <div
        style={{
          background: 'rgba(10,10,16,0.97)',
          border: '1px solid rgba(255,255,255,0.10)',
          borderRadius: 12,
          overflow: 'hidden',
          boxShadow: '0 20px 60px rgba(0,0,0,0.85), 0 0 0 1px rgba(255,255,255,0.04)',
        }}
      >
        {/* Thumbnail 16:9 */}
        <div style={{ position: 'relative', width: '100%', aspectRatio: '16/9', background: '#05050a' }}>
          <Thumbnail cameraId={hover.camera.id} />

          {/* Status badge overlay */}
          <div
            style={{
              position: 'absolute', top: 6, left: 6,
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '2px 7px', borderRadius: 20,
              background: 'rgba(5,5,10,0.75)',
              border: '1px solid rgba(255,255,255,0.08)',
              backdropFilter: 'blur(6px)',
            }}
          >
            <span
              style={{
                width: 6, height: 6, borderRadius: '50%',
                background: isOnline ? '#22C55E' : '#EF4444',
                boxShadow: isOnline ? '0 0 5px #22C55E' : undefined,
                flexShrink: 0,
              }}
            />
            <span style={{ fontSize: 9, fontWeight: 600, color: isOnline ? '#4ade80' : '#f87171', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              {isOnline ? 'Live' : 'Offline'}
            </span>
          </div>

          {/* IA badge */}
          {hover.camera.ia_enabled && (
            <div
              style={{
                position: 'absolute', top: 6, right: 6,
                padding: '2px 6px', borderRadius: 4,
                background: 'rgba(139,92,246,0.15)',
                border: '1px solid rgba(139,92,246,0.25)',
              }}
            >
              <span style={{ fontSize: 9, fontWeight: 700, color: '#A78BFA', textTransform: 'uppercase', letterSpacing: '0.05em' }}>IA</span>
            </div>
          )}
        </div>

        {/* Meta */}
        <div style={{ padding: '8px 10px 10px' }}>
          <p style={{ fontSize: 12, fontWeight: 600, color: '#F4F4F5', margin: 0, lineHeight: 1.3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {hover.camera.name}
          </p>
          {hover.camera.location && (
            <p style={{ fontSize: 10, color: '#52525B', margin: '2px 0 0', lineHeight: 1.4, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {hover.camera.location}
            </p>
          )}
          <p style={{ fontSize: 9, color: 'rgba(255,255,255,0.2)', margin: '6px 0 0', textAlign: 'center' }}>
            Duplo clique para abrir timeline
          </p>
        </div>
      </div>
    </div>,
    document.body,
  )
}

// ── Fit map to cameras ────────────────────────────────────────────────────────
function FitBounds({ cameras }: { cameras: Camera[] }) {
  const map = useMap()
  const fitted = useRef(false)

  useEffect(() => {
    if (fitted.current || cameras.length === 0) return
    const pts = cameras.filter((c) => c.latitude && c.longitude)
    if (pts.length === 0) return
    fitted.current = true
    if (pts.length === 1) {
      map.setView([pts[0].latitude!, pts[0].longitude!], 15)
      return
    }
    const bounds = L.latLngBounds(pts.map((c) => [c.latitude!, c.longitude!]))
    map.fitBounds(bounds, { padding: [48, 48] })
  }, [map, cameras])

  return null
}

// ── Fly to camera ─────────────────────────────────────────────────────────────
function FlyTo({ target }: { target: Camera | null }) {
  const map = useMap()
  useEffect(() => {
    if (!target?.latitude || !target?.longitude) return
    map.flyTo([target.latitude, target.longitude], Math.max(map.getZoom(), 16), { duration: 0.8 })
  }, [map, target])
  return null
}

// ── Sidebar camera card ────────────────────────────────────────────────────────
function CameraCard({
  camera, isOnline, isActive, hasCoords, onClick, onDoubleClick,
}: {
  camera: Camera; isOnline: boolean; isActive: boolean; hasCoords: boolean
  onClick: () => void
  onDoubleClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      onDoubleClick={(e) => { e.stopPropagation(); onDoubleClick() }}
      className="w-full relative overflow-hidden rounded-xl transition-all shrink-0"
      style={{
        height: 92,
        background: '#08080f',
        border: `1.5px solid ${isActive ? 'rgba(59,130,246,0.55)' : 'rgba(255,255,255,0.07)'}`,
        boxShadow: isActive ? '0 0 0 3px rgba(59,130,246,0.15)' : undefined,
      }}
    >
      {/* Thumbnail full cover */}
      <div className="absolute inset-0">
        <Thumbnail cameraId={camera.id} />
      </div>

      {/* Darkening gradient from bottom */}
      <div
        className="absolute inset-0"
        style={{ background: 'linear-gradient(to bottom, rgba(0,0,0,0.08) 0%, rgba(0,0,0,0.82) 100%)' }}
      />

      {/* Top-right badges */}
      <div className="absolute top-2 right-2 flex items-center gap-1">
        {camera.ia_enabled && (
          <span style={{
            fontSize: 8, fontWeight: 700, padding: '1px 5px', borderRadius: 3,
            background: 'rgba(139,92,246,0.3)', color: '#C4B5FD',
            border: '1px solid rgba(139,92,246,0.4)', letterSpacing: '0.05em',
            textTransform: 'uppercase',
          }}>IA</span>
        )}
        {!hasCoords && (
          <MapPin size={8} style={{ color: 'rgba(255,255,255,0.25)' }} />
        )}
      </div>

      {/* Bottom info */}
      <div className="absolute bottom-0 left-0 right-0 px-2.5 pb-2">
        <div className="flex items-center gap-1.5">
          <span style={{
            width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
            background: isOnline ? '#22C55E' : '#EF4444',
            boxShadow: isOnline ? '0 0 5px #22C55E88' : undefined,
          }} />
          <p className="text-[11px] font-semibold text-white truncate leading-tight flex-1 text-left">{camera.name}</p>
        </div>
        {camera.location && (
          <p className="text-[9px] truncate mt-0.5 text-left" style={{ color: 'rgba(255,255,255,0.45)' }}>{camera.location}</p>
        )}
        <p className="text-[8px] mt-1 text-left" style={{ color: 'rgba(255,255,255,0.18)' }}>duplo clique → timeline</p>
      </div>
    </button>
  )
}

// ── No-coords empty state ─────────────────────────────────────────────────────
function NoMapState({ count }: { count: number }) {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center" style={{ background: '#05050a' }}>
      <div
        className="rounded-2xl px-8 py-8 text-center"
        style={{
          background: 'rgba(8,8,14,0.9)', border: '1px solid rgba(255,255,255,0.07)',
          backdropFilter: 'blur(20px)', maxWidth: 340,
        }}
      >
        <MapPin size={28} style={{ color: '#3f3f46', margin: '0 auto 10px' }} />
        <p className="text-sm font-semibold text-t1 mb-2">Nenhuma câmera com GPS</p>
        <p className="text-xs text-t3 leading-relaxed">
          {count > 0
            ? `${count} câmera${count > 1 ? 's' : ''} sem coordenadas. Configure latitude/longitude nas câmeras para visualizá-las no mapa.`
            : 'Nenhuma câmera cadastrada.'}
        </p>
        <Link
          to="/cameras"
          className="inline-flex items-center gap-1.5 mt-4 px-4 py-2 rounded-lg text-xs font-medium"
          style={{ background: 'rgba(59,130,246,0.15)', color: '#60a5fa', border: '1px solid rgba(59,130,246,0.25)' }}
        >
          <Cctv size={12} />
          Gerenciar câmeras
        </Link>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
type FilterType = 'all' | 'online' | 'offline'

export function TacticalViewPage() {
  const [cameras, setCameras]               = useState<Camera[]>([])
  const [loading, setLoading]               = useState(true)
  const [flyTarget, setFlyTarget]           = useState<Camera | null>(null)
  const [activeId, setActiveId]             = useState<string | null>(null)
  const [timelineCamera, setTimelineCamera] = useState<Camera | null>(null)
  const [search, setSearch]                 = useState('')
  const [filter, setFilter]                 = useState<FilterType>('all')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [hoverPreview, setHoverPreview]     = useState<HoverState | null>(null)
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { cameras: statusMap } = useCameraStore()

  const load = useCallback(() => {
    setLoading(true)
    camerasService.list({ page_size: 200 })
      .then(setCameras).catch(() => {}).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const onlineStatus = useMemo<Record<string, boolean>>(() => {
    const map: Record<string, boolean> = {}
    cameras.forEach((c) => { map[c.id] = statusMap[c.id]?.online ?? c.is_online })
    return map
  }, [cameras, statusMap])

  const onlineCount  = useMemo(() => Object.values(onlineStatus).filter(Boolean).length, [onlineStatus])
  const offlineCount = cameras.length - onlineCount

  const filtered = useMemo(() => cameras.filter((c) => {
    const q = search.toLowerCase()
    const matchSearch = !q || c.name.toLowerCase().includes(q) || (c.location ?? '').toLowerCase().includes(q)
    const isOnline    = onlineStatus[c.id] ?? c.is_online
    const matchFilter = filter === 'all' ? true : filter === 'online' ? isOnline : !isOnline
    return matchSearch && matchFilter
  }), [cameras, search, filter, onlineStatus])

  const withCoords    = useMemo(() => filtered.filter((c) => c.latitude && c.longitude), [filtered])
  const noCoords      = useMemo(() => filtered.filter((c) => !c.latitude || !c.longitude), [filtered])
  const allWithCoords = useMemo(() => cameras.filter((c) => c.latitude && c.longitude), [cameras])

  const showHover = useCallback((cam: Camera, x: number, y: number) => {
    if (hideTimer.current) clearTimeout(hideTimer.current)
    setHoverPreview({ camera: cam, x, y })
  }, [])

  const hideHover = useCallback(() => {
    hideTimer.current = setTimeout(() => setHoverPreview(null), 80)
  }, [])

  const handleCameraClick = useCallback((cam: Camera) => {
    setActiveId(cam.id)
    if (cam.latitude && cam.longitude) setFlyTarget(cam)
  }, [])

  const handleCameraDoubleClick = useCallback((cam: Camera) => {
    setActiveId(cam.id)
    setTimelineCamera(cam)
    if (cam.latitude && cam.longitude) setFlyTarget(cam)
  }, [])

  const SIDEBAR_W = sidebarCollapsed ? 48 : 304

  return (
    <div className="relative w-full h-full overflow-hidden" style={{ background: '#05050a' }}>

      {/* ── Map ──────────────────────────────────────────────────────── */}
      <div className="absolute inset-0" style={{ right: SIDEBAR_W }}>
        {loading ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-7 h-7 border-2 border-t-accent border-zinc-800 rounded-full animate-spin" />
          </div>
        ) : allWithCoords.length === 0 ? (
          <NoMapState count={cameras.length} />
        ) : (
          <MapContainer
            center={[-14.235, -51.925]}
            zoom={5}
            style={{ width: '100%', height: '100%' }}
            zoomControl={false}
            doubleClickZoom={false}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com">CARTO</a>'
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            />
            <FitBounds cameras={allWithCoords} />
            <FlyTo target={flyTarget} />

            {withCoords.map((cam) => {
              const isOnline = onlineStatus[cam.id] ?? cam.is_online
              const isActive = activeId === cam.id
              return (
                <Marker
                  key={cam.id}
                  position={[cam.latitude!, cam.longitude!]}
                  icon={makeCameraIcon(isOnline, isActive)}
                  eventHandlers={{
                    mouseover: (e: LeafletMouseEvent) => {
                      const oe = e.originalEvent as MouseEvent
                      showHover(cam, oe.clientX, oe.clientY)
                    },
                    mousemove: (e: LeafletMouseEvent) => {
                      const oe = e.originalEvent as MouseEvent
                      setHoverPreview((prev) =>
                        prev?.camera.id === cam.id
                          ? { ...prev, x: oe.clientX, y: oe.clientY }
                          : prev
                      )
                    },
                    mouseout: hideHover,
                    click: () => {
                      setHoverPreview(null)
                      setActiveId((p) => p === cam.id ? null : cam.id)
                      setFlyTarget(cam)
                    },
                    dblclick: () => {
                      setHoverPreview(null)
                      handleCameraDoubleClick(cam)
                    },
                  }}
                />
              )
            })}
          </MapContainer>
        )}
      </div>

      {/* ── Hover preview portal ──────────────────────────────────────── */}
      {hoverPreview && (
        <HoverCard
          hover={hoverPreview}
          isOnline={onlineStatus[hoverPreview.camera.id] ?? hoverPreview.camera.is_online}
        />
      )}

      {/* ── Status bar ───────────────────────────────────────────────── */}
      {!loading && (
        <div
          className="absolute top-3 left-3 z-[1000] flex items-center gap-3"
          style={{
            background: 'rgba(8,8,14,0.88)', backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255,255,255,0.07)', borderRadius: 10, padding: '6px 14px',
          }}
        >
          <span className="text-[12px] font-semibold text-t1">Visão Tática</span>
          <div className="w-px h-3.5 bg-white/10" />
          <div className="flex items-center gap-1.5">
            <Wifi size={11} style={{ color: '#22C55E' }} />
            <span className="text-[11px] font-medium tabular-nums" style={{ color: '#22C55E' }}>{onlineCount}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <WifiOff size={11} style={{ color: '#EF4444' }} />
            <span className="text-[11px] font-medium tabular-nums" style={{ color: '#EF4444' }}>{offlineCount}</span>
          </div>
          <div className="w-px h-3.5 bg-white/10" />
          <button onClick={load} className="flex items-center gap-1 text-[11px] text-t3 hover:text-t1 transition-colors">
            <RefreshCw size={10} />
            Atualizar
          </button>
        </div>
      )}

      {/* ── Sidebar ──────────────────────────────────────────────────── */}
      <aside
        className="absolute right-0 top-0 bottom-0 z-[1000] flex flex-col transition-all duration-200"
        style={{
          width: SIDEBAR_W,
          background: 'rgba(6,6,12,0.92)',
          backdropFilter: 'blur(20px)',
          borderLeft: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        {sidebarCollapsed ? (
          <div className="flex flex-col items-center py-4 gap-3 flex-1">
            <button
              onClick={() => setSidebarCollapsed(false)}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-t3 hover:text-t1 hover:bg-white/[0.06] transition-all"
              title="Expandir"
            >
              <Cctv size={14} />
            </button>
            <div className="flex flex-col items-center gap-1.5 pt-1 flex-1">
              {cameras.slice(0, 14).map((cam) => {
                const isOnline = onlineStatus[cam.id] ?? cam.is_online
                return (
                  <button
                    key={cam.id}
                    onClick={() => handleCameraClick(cam)}
                    className="w-2.5 h-2.5 rounded-full transition-all hover:scale-125"
                    style={{ background: isOnline ? '#22C55E' : '#EF4444' }}
                    title={cam.name}
                  />
                )
              })}
              {cameras.length > 14 && (
                <span className="text-[8px] text-t3/40 mt-1">+{cameras.length - 14}</span>
              )}
            </div>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="flex items-center gap-2 px-3 py-3 shrink-0" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
              <Cctv size={13} className="text-t3/70 shrink-0" />
              <span className="text-xs font-semibold text-t2 flex-1">
                Câmeras
                <span className="ml-1.5 text-[10px] text-t3/50 font-normal tabular-nums">({filtered.length})</span>
              </span>
              <button
                onClick={() => setSidebarCollapsed(true)}
                className="w-6 h-6 flex items-center justify-center rounded text-t3/40 hover:text-t3 transition-colors"
              >
                <X size={12} />
              </button>
            </div>

            {/* Search */}
            <div className="px-3 py-2 shrink-0">
              <div
                className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg"
                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}
              >
                <Search size={11} className="text-t3/50 shrink-0" />
                <input
                  type="text"
                  placeholder="Buscar câmera..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="bg-transparent text-[11px] text-t1 outline-none placeholder:text-t3/40 w-full"
                />
                {search && (
                  <button onClick={() => setSearch('')} className="text-t3/40 hover:text-t3"><X size={10} /></button>
                )}
              </div>
            </div>

            {/* Filter tabs */}
            <div className="px-3 pb-2 shrink-0">
              <div
                className="flex rounded-lg overflow-hidden"
                style={{ border: '1px solid rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.03)' }}
              >
                {([
                  ['all',     'Todas',   cameras.length],
                  ['online',  'Online',  onlineCount],
                  ['offline', 'Offline', offlineCount],
                ] as [FilterType, string, number][]).map(([id, label, count]) => (
                  <button
                    key={id}
                    onClick={() => setFilter(id)}
                    className="flex-1 py-1.5 text-[10px] font-medium transition-all tabular-nums"
                    style={{
                      background: filter === id
                        ? id === 'online' ? 'rgba(34,197,94,0.15)' : id === 'offline' ? 'rgba(239,68,68,0.15)' : 'rgba(59,130,246,0.15)'
                        : 'transparent',
                      color: filter === id
                        ? id === 'online' ? '#22C55E' : id === 'offline' ? '#EF4444' : '#60A5FA'
                        : 'rgba(255,255,255,0.35)',
                    }}
                  >
                    {label} {count}
                  </button>
                ))}
              </div>
            </div>

            {/* Camera list */}
            <div
              className="flex-1 overflow-y-auto px-2 pb-3 flex flex-col gap-2"
              style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.06) transparent' }}
            >
              {loading ? (
                <div className="flex justify-center py-8">
                  <div className="w-5 h-5 border-2 border-t-accent border-zinc-800 rounded-full animate-spin" />
                </div>
              ) : filtered.length === 0 ? (
                <div className="flex flex-col items-center py-8">
                  <Filter size={18} className="text-t3/20 mb-2" />
                  <p className="text-[11px] text-t3/40">Nenhuma câmera</p>
                </div>
              ) : (
                <>
                  {withCoords.map((cam) => (
                    <CameraCard
                      key={cam.id}
                      camera={cam}
                      isOnline={onlineStatus[cam.id] ?? cam.is_online}
                      isActive={activeId === cam.id}
                      hasCoords
                      onClick={() => handleCameraClick(cam)}
                      onDoubleClick={() => handleCameraDoubleClick(cam)}
                    />
                  ))}

                  {noCoords.length > 0 && (
                    <>
                      {withCoords.length > 0 && (
                        <div className="flex items-center gap-2 px-1 py-1">
                          <div className="h-px flex-1" style={{ background: 'rgba(255,255,255,0.04)' }} />
                          <span className="text-[9px] text-t3/30 uppercase tracking-wider font-medium">Sem GPS</span>
                          <div className="h-px flex-1" style={{ background: 'rgba(255,255,255,0.04)' }} />
                        </div>
                      )}
                      {noCoords.map((cam) => (
                        <CameraCard
                          key={cam.id}
                          camera={cam}
                          isOnline={onlineStatus[cam.id] ?? cam.is_online}
                          isActive={timelineCamera?.id === cam.id}
                          hasCoords={false}
                          onClick={() => handleCameraClick(cam)}
                          onDoubleClick={() => handleCameraDoubleClick(cam)}
                        />
                      ))}
                    </>
                  )}
                </>
              )}
            </div>
          </>
        )}
      </aside>

      {/* ── Timeline modal ────────────────────────────────────────────── */}
      {timelineCamera && (
        <TacticalTimelineModal
          camera={timelineCamera}
          onClose={() => setTimelineCamera(null)}
        />
      )}
    </div>
  )
}
