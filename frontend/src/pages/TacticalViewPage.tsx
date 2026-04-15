import { useEffect, useMemo, useState } from 'react'
import { Cctv, MapPin, Search } from 'lucide-react'
import { clsx } from 'clsx'
import { camerasService } from '@/services/cameras'
import { useCameraStore } from '@/store/cameraStore'
import { TacticalTimelineModal } from '@/components/tactical/TacticalTimelineModal'
import type { Camera } from '@/types'

type Filter = 'all' | 'online' | 'offline'

function CameraCard({
  camera,
  isOnline,
  isActive,
  onSelect,
}: {
  camera: Camera
  isOnline: boolean
  isActive: boolean
  onSelect: () => void
}) {
  return (
    <div
      onClick={onSelect}
      className={clsx(
        'flex flex-col gap-2 p-3 rounded-xl cursor-pointer transition-all border',
        isActive
          ? 'border-accent bg-accent/10'
          : 'border-transparent hover:border-border hover:bg-elevated',
      )}
    >
      {/* Thumbnail placeholder */}
      <div
        className="w-full aspect-video rounded-lg flex items-center justify-center relative overflow-hidden"
        style={{ background: 'var(--elevated)' }}
      >
        <Cctv size={28} className="text-t3" />
        <span
          className={clsx(
            'absolute top-2 right-2 w-2 h-2 rounded-full',
            isOnline ? 'bg-emerald-500' : 'bg-red-500',
          )}
        />
      </div>

      {/* Info */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-t1 truncate">{camera.name}</p>
          {camera.location && (
            <p className="text-[10px] text-t3 truncate mt-0.5">{camera.location}</p>
          )}
        </div>
        <span
          className={clsx(
            'text-[9px] font-medium shrink-0 mt-0.5',
            isOnline ? 'text-emerald-500' : 'text-red-500',
          )}
        >
          {isOnline ? 'Online' : 'Offline'}
        </span>
      </div>
    </div>
  )
}

export function TacticalViewPage() {
  const [cameras, setCameras]               = useState<Camera[]>([])
  const [loading, setLoading]               = useState(true)
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null)
  const [search, setSearch]                 = useState('')
  const [filter, setFilter]                 = useState<Filter>('all')

  const { cameras: statusMap } = useCameraStore()

  useEffect(() => {
    camerasService.list({ page_size: 200 })
      .then(setCameras)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const onlineStatus = useMemo<Record<string, boolean>>(() => {
    const map: Record<string, boolean> = {}
    cameras.forEach((c) => {
      map[c.id] = statusMap[c.id]?.online ?? c.is_online
    })
    return map
  }, [cameras, statusMap])

  const onlineCount  = useMemo(() => Object.values(onlineStatus).filter(Boolean).length, [onlineStatus])
  const offlineCount = cameras.length - onlineCount

  const filtered = useMemo(() => {
    return cameras.filter((c) => {
      const matchSearch = !search || c.name.toLowerCase().includes(search.toLowerCase())
      const matchFilter =
        filter === 'all'    ? true :
        filter === 'online' ? (onlineStatus[c.id] ?? c.is_online) :
                              !(onlineStatus[c.id] ?? c.is_online)
      return matchSearch && matchFilter
    })
  }, [cameras, search, filter, onlineStatus])

  return (
    <div className="flex flex-col h-full">
      {/* ── Toolbar ───────────────────────────────────────────────────────── */}
      <div
        className="flex items-center gap-3 px-4 py-2.5 border-b shrink-0 flex-wrap"
        style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
      >
        <div className="flex items-center gap-2">
          <MapPin size={15} className="text-accent" />
          <span className="text-sm font-semibold text-t1">Visão Tática</span>
        </div>

        <div
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border"
          style={{ background: 'var(--elevated)', borderColor: 'var(--border)' }}
        >
          <Search size={13} className="text-t3 shrink-0" />
          <input
            type="text"
            placeholder="Buscar câmera..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-transparent text-xs text-t1 outline-none placeholder:text-t3 w-44"
          />
        </div>

        <div className="flex gap-1.5">
          {([
            ['all',     `Todas (${cameras.length})`],
            ['online',  `Online (${onlineCount})`],
            ['offline', `Offline (${offlineCount})`],
          ] as [Filter, string][]).map(([id, label]) => (
            <button
              key={id}
              onClick={() => setFilter(id)}
              className={clsx(
                'px-3 py-1 rounded text-xs font-medium transition-all',
                filter === id ? 'text-white' : 'text-t3 hover:text-t2',
              )}
              style={{
                background: filter === id ? 'var(--accent)' : 'var(--elevated)',
                border: '1px solid var(--border)',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-3 text-xs text-t3">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            {onlineCount} online
          </span>
          <span className="text-t3">·</span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-red-500" />
            {offlineCount} offline
          </span>
        </div>
      </div>

      {/* ── Grade de câmeras ──────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-4" style={{ scrollbarWidth: 'thin' }}>
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-8 h-8 border-2 border-t-accent border-zinc-700 rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-t3 text-center py-16">Nenhuma câmera encontrada</p>
        ) : (
          <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
            {filtered.map((camera) => (
              <CameraCard
                key={camera.id}
                camera={camera}
                isOnline={onlineStatus[camera.id] ?? camera.is_online}
                isActive={selectedCamera?.id === camera.id}
                onSelect={() => setSelectedCamera((prev) => prev?.id === camera.id ? null : camera)}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── Modal full-screen ao selecionar câmera ────────────────────────── */}
      {selectedCamera && (
        <TacticalTimelineModal
          camera={selectedCamera}
          onClose={() => setSelectedCamera(null)}
        />
      )}
    </div>
  )
}
