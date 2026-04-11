import { useCallback, useEffect, useMemo, useState } from 'react'
import { Plus, Maximize2, X, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import { camerasService } from '@/services/cameras'
import { VideoPlayer } from '@/components/camera/VideoPlayer'
import type { Camera } from '@/types'

type Layout = '1x1' | '2x2' | '3x3' | '4x4'

const LAYOUTS: { id: Layout; label: string; slots: number }[] = [
  { id: '1x1', label: '1×1', slots: 1 },
  { id: '2x2', label: '2×2', slots: 4 },
  { id: '3x3', label: '3×3', slots: 9 },
  { id: '4x4', label: '4×4', slots: 16 },
]

const GRID_CLASS: Record<Layout, string> = {
  '1x1': 'grid-cols-1',
  '2x2': 'grid-cols-2',
  '3x3': 'grid-cols-3',
  '4x4': 'grid-cols-4',
}

const STORAGE_KEY_SELECTED = 'vms_mosaic_selected'
const STORAGE_KEY_LAYOUT = 'vms_mosaic_layout'

function loadSelectedIds(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_SELECTED)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

function loadLayout(): Layout {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_LAYOUT)
    if (raw && ['1x1','2x2','3x3','4x4'].includes(raw)) return raw as Layout
    return '2x2'
  } catch { return '2x2' }
}

// ─── Otimizações de banda por layout ─────────────────────────────────────
interface BandwidthConfig {
  maxBufferLength: number
  maxMaxBufferLength: number
  startLevel: number
  capLevelToPlayerSize: boolean
}

const BANDWIDTH_CONFIGS: Record<Layout, BandwidthConfig> = {
  '1x1': { maxBufferLength: 10, maxMaxBufferLength: 30, startLevel: -1, capLevelToPlayerSize: false },
  '2x2': { maxBufferLength: 6, maxMaxBufferLength: 15, startLevel: -1, capLevelToPlayerSize: true },
  '3x3': { maxBufferLength: 4, maxMaxBufferLength: 10, startLevel: 0, capLevelToPlayerSize: true },
  '4x4': { maxBufferLength: 2, maxMaxBufferLength: 6, startLevel: 0, capLevelToPlayerSize: true },
}

interface CameraSlot {
  cameraId: string
  cameraName: string
  streamUrl: string | null
  loading: boolean
}

function SkeletonSlot() {
  return (
    <div className="w-full h-full flex flex-col items-center justify-center gap-2 bg-zinc-900">
      <Loader2 size={24} className="text-zinc-600 animate-spin" />
      <span className="text-xs text-zinc-600">Conectando...</span>
    </div>
  )
}

export function MosaicPage() {
  const [camerasLoading, setCamerasLoading] = useState(true)
  const [layout, setLayout]       = useState<Layout>(loadLayout())
  const [cameras, setCameras]     = useState<Camera[]>([])
  const [selectedIds, setSelectedIds] = useState<string[]>(loadSelectedIds())
  const [streamCache, setStreamCache] = useState<Record<string, string | null>>({})
  const [loadingUrls, setLoadingUrls] = useState<Set<string>>(new Set())

  const slotsCount = LAYOUTS.find((l) => l.id === layout)!.slots

  // Câmeras selecionadas disponíveis no banco
  const selectedCameras = useMemo(
    () => cameras.filter((c) => selectedIds.includes(c.id)),
    [cameras, selectedIds],
  )

  // Auto-resolve stream URLs para câmeras selecionadas
  useEffect(() => {
    selectedCameras.forEach((cam) => {
      if (streamCache[cam.id] === undefined && !loadingUrls.has(cam.id)) {
        setLoadingUrls((prev) => new Set(prev).add(cam.id))
        camerasService.streamUrls(cam.id)
          .then((s) => {
            setStreamCache((prev) => ({ ...prev, [cam.id]: s.hls_url || null }))
          })
          .catch(() => {
            setStreamCache((prev) => ({ ...prev, [cam.id]: null }))
          })
          .finally(() => {
            setLoadingUrls((prev) => {
              const next = new Set(prev)
              next.delete(cam.id)
              return next
            })
          })
      }
    })
  }, [selectedCameras])

  // Monta slots: preenchidos com câmeras selecionadas, vazios se sobrar
  const slots: (CameraSlot | null)[] = useMemo(() => {
    const result: (CameraSlot | null)[] = []
    for (let i = 0; i < slotsCount; i++) {
      if (i < selectedCameras.length) {
        const cam = selectedCameras[i]
        const isLoading = loadingUrls.has(cam.id) || streamCache[cam.id] === undefined
        result.push({
          cameraId: cam.id,
          cameraName: cam.name,
          streamUrl: streamCache[cam.id] ?? null,
          loading: isLoading,
        })
      } else {
        result.push(null)
      }
    }
    return result
  }, [selectedCameras, slotsCount, streamCache, loadingUrls])

  // Câmeras não selecionadas (disponíveis no dropdown)
  const availableCameras = useMemo(
    () => cameras.filter((c) => !selectedIds.includes(c.id)),
    [cameras, selectedIds],
  )

  useEffect(() => {
    camerasService.list({ page_size: 100 })
      .then(setCameras)
      .finally(() => setCamerasLoading(false))
  }, [])

  // Persist selected IDs
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_SELECTED, JSON.stringify(selectedIds))
  }, [selectedIds])

  // Persist layout
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_LAYOUT, layout)
  }, [layout])

  const changeLayout = (l: Layout) => setLayout(l)

  const addCamera = useCallback(async (camId: string) => {
    const cam = cameras.find((c) => c.id === camId)
    if (!cam || selectedIds.includes(camId)) return
    if (selectedIds.length >= 16) return

    // Se URL já está em cache, adiciona direto
    if (streamCache[camId] !== undefined) {
      setSelectedIds((prev) => [...prev, camId])
      return
    }

    // Resolve stream URL
    setLoadingUrls((prev) => new Set(prev).add(camId))
    try {
      const s = await camerasService.streamUrls(camId)
      setStreamCache((prev) => ({ ...prev, [camId]: s.hls_url || null }))
    } catch {
      setStreamCache((prev) => ({ ...prev, [camId]: null }))
    } finally {
      setLoadingUrls((prev) => {
        const next = new Set(prev)
        next.delete(camId)
        return next
      })
    }

    setSelectedIds((prev) => [...prev, camId])
  }, [cameras, selectedIds, streamCache])

  const removeCamera = useCallback((camId: string) => {
    setSelectedIds((prev) => prev.filter((id) => id !== camId))
  }, [])

  // Configurações de banda para o layout atual
  const bwConfig = BANDWIDTH_CONFIGS[layout]

  // Loading inicial
  if (camerasLoading) {
    return (
      <div className="h-full flex flex-col gap-3 animate-fade-in">
        <div className="flex items-center gap-3 shrink-0">
          <div className="h-8 w-32 rounded-lg animate-pulse" style={{ background: 'var(--surface)' }} />
          <div className="ml-auto h-6 w-48 rounded animate-pulse" style={{ background: 'var(--surface)' }} />
        </div>
        <div className={clsx('grid gap-2', GRID_CLASS[layout])} style={{ height: 'calc(100vh - 120px)' }}>
          {Array.from({ length: slotsCount }).map((_, i) => (
            <div key={i} className="rounded-lg overflow-hidden bg-zinc-900 flex items-center justify-center">
              <Loader2 size={28} className="text-zinc-700 animate-spin" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col gap-3 animate-fade-in">
      {/* Toolbar */}
      <div className="flex items-center gap-3 shrink-0 flex-wrap">
        {/* Layout selector */}
        <div
          className="flex items-center gap-1 p-1 rounded-lg"
          style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
        >
          {LAYOUTS.map((l) => (
            <button
              key={l.id}
              onClick={() => changeLayout(l.id)}
              className={clsx(
                'px-3 py-1 rounded-md text-xs font-medium transition',
                layout === l.id ? 'text-white' : 'text-t2 hover:text-t1',
              )}
              style={layout === l.id ? { background: 'var(--accent)' } : {}}
            >
              {l.label}
            </button>
          ))}
        </div>

        {/* Add camera selector */}
        {availableCameras.length > 0 && (
          <select
            className="text-xs rounded-lg px-3 py-1.5 cursor-pointer max-w-[200px]"
            style={{ background: 'var(--elevated)', border: '1px solid var(--border)', color: 'var(--t2)' }}
            value=""
            onChange={(e) => { if (e.target.value) addCamera(e.target.value) }}
          >
            <option value="" disabled>+ Adicionar câmera</option>
            {availableCameras.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        )}

        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs text-t2">
            {selectedIds.length} câmera(s) selecionada(s) · {slotsCount} slots ({layout})
          </span>
          <button
            className="btn btn-ghost"
            onClick={() => document.documentElement.requestFullscreen?.()}
          >
            <Maximize2 size={15} />Tela Cheia
          </button>
        </div>
      </div>

      {/* Mosaic grid - altura fixa baseada no viewport */}
      <div
        className={clsx('grid gap-2', GRID_CLASS[layout])}
        style={{
          height: 'calc(100vh - 120px)',
          gridTemplateRows: `repeat(${Math.sqrt(slotsCount)}, 1fr)`,
        }}
      >
        {slots.map((slot, idx) => (
          <div
            key={slot ? slot.cameraId : `empty-${idx}`}
            className="relative rounded-lg overflow-hidden bg-black group"
          >
            {slot ? (
              <>
                {/* Skeleton loading */}
                {slot.loading && <SkeletonSlot />}

                {/* Video player (só mostra quando URL está pronta) */}
                {!slot.loading && slot.streamUrl && (
                  <VideoPlayer
                    src={slot.streamUrl}
                    name={slot.cameraName}
                    className="w-full h-full"
                    muted
                    autoPlay
                    bandwidthConfig={bwConfig}
                  />
                )}

                {/* Erro: URL resolvida mas nula */}
                {!slot.loading && !slot.streamUrl && (
                  <div className="w-full h-full flex flex-col items-center justify-center gap-2 bg-zinc-900">
                    <X size={22} className="text-red-500/50" />
                    <span className="text-xs text-zinc-600">Sem sinal</span>
                    <span className="text-[10px] text-zinc-700">{slot.cameraName}</span>
                  </div>
                )}

                <button
                  className="absolute top-2 right-2 w-7 h-7 rounded-md bg-black/60 text-white opacity-0 group-hover:opacity-100 transition flex items-center justify-center text-lg z-20"
                  onClick={() => removeCamera(slot.cameraId)}
                  title="Remover câmera"
                >
                  <X size={14} />
                </button>
              </>
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center gap-2 bg-zinc-900/50">
                <Plus size={22} className="text-zinc-700" />
                <span className="text-xs text-zinc-600">Slot {idx + 1}</span>
                {availableCameras.length > 0 ? (
                  <select
                    className="text-xs text-t2 rounded-lg px-3 py-1.5 cursor-pointer max-w-[160px]"
                    style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
                    value=""
                    onChange={(e) => { if (e.target.value) addCamera(e.target.value) }}
                  >
                    <option value="" disabled>Selecionar</option>
                    {availableCameras.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                ) : (
                  <span className="text-xs text-zinc-600">Nenhuma disponível</span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
