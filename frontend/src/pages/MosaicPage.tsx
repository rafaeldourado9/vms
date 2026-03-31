import { useEffect, useState } from 'react'
import { Plus, Maximize2 } from 'lucide-react'
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

interface Slot {
  cameraId: string | null
  streamUrl: string | null
  cameraName: string | null
}

const GRID_CLASS: Record<Layout, string> = {
  '1x1': 'grid-cols-1',
  '2x2': 'grid-cols-2',
  '3x3': 'grid-cols-3',
  '4x4': 'grid-cols-4',
}

const makeSlots = (n: number): Slot[] =>
  Array.from({ length: n }, () => ({ cameraId: null, streamUrl: null, cameraName: null }))

export function MosaicPage() {
  const [layout, setLayout]   = useState<Layout>('2x2')
  const [cameras, setCameras] = useState<Camera[]>([])
  const [slots, setSlots]     = useState<Slot[]>(makeSlots(4))
  const [streamCache, setStreamCache] = useState<Record<string, string>>({})

  useEffect(() => {
    camerasService.list({ page_size: 100 }).then(setCameras)
  }, [])

  const changeLayout = (l: Layout) => {
    setLayout(l)
    const n = LAYOUTS.find((x) => x.id === l)!.slots
    setSlots(makeSlots(n))
  }

  const assignCamera = async (slotIdx: number, camId: string) => {
    const cam = cameras.find((c) => c.id === camId)
    if (!cam) return

    let url = streamCache[camId]
    if (!url) {
      try {
        const s = await camerasService.streamUrls(camId)
        url = s.hls_url || ''
        setStreamCache((prev) => ({ ...prev, [camId]: url }))
      } catch { url = '' }
    }

    setSlots((prev) =>
      prev.map((s, i) =>
        i === slotIdx ? { cameraId: camId, streamUrl: url, cameraName: cam.name } : s,
      ),
    )
  }

  const clearSlot = (idx: number) => {
    setSlots((prev) => prev.map((s, i) => i === idx ? { cameraId: null, streamUrl: null, cameraName: null } : s))
  }

  return (
    <div className="h-full flex flex-col gap-3 animate-fade-in">
      {/* Toolbar */}
      <div className="flex items-center gap-3 shrink-0">
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
        <button
          className="btn btn-ghost ml-auto"
          onClick={() => document.documentElement.requestFullscreen?.()}
        >
          <Maximize2 size={15} />Tela Cheia
        </button>
      </div>

      {/* Mosaic grid */}
      <div className={clsx('flex-1 grid gap-2 min-h-0', GRID_CLASS[layout])}>
        {slots.map((slot, idx) => (
          <div key={idx} className="relative rounded-lg overflow-hidden bg-black group min-h-[120px]">
            {slot.streamUrl ? (
              <>
                <VideoPlayer src={slot.streamUrl} name={slot.cameraName ?? undefined} className="w-full h-full" />
                <button
                  className="absolute top-2 right-2 w-7 h-7 rounded-md bg-black/60 text-white opacity-0 group-hover:opacity-100 transition flex items-center justify-center text-lg"
                  onClick={() => clearSlot(idx)}
                >
                  ×
                </button>
              </>
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center gap-3">
                <Plus size={22} className="text-zinc-700" />
                <select
                  className="text-xs text-t2 rounded-lg px-3 py-1.5 cursor-pointer max-w-[160px]"
                  style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
                  value=""
                  onChange={(e) => assignCamera(idx, e.target.value)}
                >
                  <option value="" disabled>Selecionar câmera</option>
                  {cameras.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
