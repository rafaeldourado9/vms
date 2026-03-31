import { useEffect, useState } from 'react'
import { Plus, Search, LayoutGrid, List, Trash2, Settings } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { clsx } from 'clsx'
import { camerasService } from '@/services/cameras'
import { CameraCard } from '@/components/camera/CameraCard'
import { PageSpinner } from '@/components/ui/Spinner'
import { AddCameraWizard } from '@/components/wizard/AddCameraWizard'
import { usePermission } from '@/hooks/usePermission'
import toast from 'react-hot-toast'
import type { Camera } from '@/types'

type ViewMode = 'grid' | 'list'
type FilterStatus = 'all' | 'online' | 'offline'

export function CamerasPage() {
  const navigate = useNavigate()
  const { isAdmin } = usePermission()

  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch]   = useState('')
  const [view, setView]       = useState<ViewMode>('grid')
  const [filter, setFilter]   = useState<FilterStatus>('all')
  const [showAdd, setShowAdd] = useState(false)

  const load = () => {
    setLoading(true)
    camerasService.list({ page_size: 200 })
      .then(setCameras)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const filtered = cameras.filter((c) => {
    if (filter === 'online'  && !c.is_online) return false
    if (filter === 'offline' &&  c.is_online) return false
    if (search && !c.name.toLowerCase().includes(search.toLowerCase()) &&
        !(c.location ?? '').toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const handleDelete = async (cam: Camera) => {
    if (!confirm(`Remover câmera "${cam.name}"?`)) return
    try {
      await camerasService.del(cam.id)
      toast.success('Câmera removida')
      load()
    } catch { toast.error('Erro ao remover câmera') }
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-48">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-t3" />
          <input
            className="input pl-9"
            placeholder="Buscar câmeras..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div
          className="flex items-center gap-1 p-1 rounded-lg"
          style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
        >
          {(['all', 'online', 'offline'] as FilterStatus[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={clsx(
                'px-3 py-1 rounded-md text-xs font-medium transition-all capitalize',
                filter === f ? 'text-white' : 'text-t2 hover:text-t1',
              )}
              style={filter === f ? { background: 'var(--accent)' } : {}}
            >
              {f === 'all' ? 'Todas' : f === 'online' ? 'Online' : 'Offline'}
            </button>
          ))}
        </div>

        <div
          className="flex items-center gap-1 p-1 rounded-lg"
          style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
        >
          <button
            onClick={() => setView('grid')}
            className={clsx('p-1.5 rounded-md transition', view === 'grid' ? 'bg-elevated text-t1' : 'text-t3 hover:text-t1')}
          >
            <LayoutGrid size={16} />
          </button>
          <button
            onClick={() => setView('list')}
            className={clsx('p-1.5 rounded-md transition', view === 'list' ? 'bg-elevated text-t1' : 'text-t3 hover:text-t1')}
          >
            <List size={16} />
          </button>
        </div>

        {isAdmin && (
          <button onClick={() => setShowAdd(true)} className="btn btn-primary">
            <Plus size={16} />Nova Câmera
          </button>
        )}
      </div>

      {/* Stats row */}
      <div className="flex items-center gap-4 text-xs text-t3">
        <span>{cameras.length} câmeras</span>
        <span className="text-green-500">{cameras.filter((c) => c.is_online).length} online</span>
        <span className="text-red-500">{cameras.filter((c) => !c.is_online).length} offline</span>
      </div>

      {/* Content */}
      {loading ? <PageSpinner /> : (
        <>
          {view === 'grid' ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filtered.map((cam) => <CameraCard key={cam.id} camera={cam} />)}
              {filtered.length === 0 && (
                <div className="col-span-full text-center py-16 text-t3">
                  <p>Nenhuma câmera encontrada</p>
                </div>
              )}
            </div>
          ) : (
            <div className="card overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left" style={{ borderColor: 'var(--border)' }}>
                    {['Status', 'Nome', 'Localização', 'Protocolo', 'Retenção', ''].map((h) => (
                      <th key={h} className="px-4 py-3 text-xs font-medium text-t3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((cam) => (
                    <tr
                      key={cam.id}
                      className="border-b hover:bg-elevated transition cursor-pointer"
                      style={{ borderColor: 'var(--border)' }}
                      onClick={() => navigate(`/cameras/${cam.id}`)}
                    >
                      <td className="px-4 py-3">
                        <div className={clsx('w-2 h-2 rounded-full', cam.is_online ? 'bg-green-500' : 'bg-red-500')} />
                      </td>
                      <td className="px-4 py-3 font-medium text-t1">{cam.name}</td>
                      <td className="px-4 py-3 text-t2 max-w-xs truncate">{cam.location ?? '—'}</td>
                      <td className="px-4 py-3">
                        <span className="text-xs uppercase text-t3">{cam.stream_protocol.replace('_', ' ')}</span>
                      </td>
                      <td className="px-4 py-3 text-t2 text-xs">{cam.retention_days}d</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => navigate(`/cameras/${cam.id}/roi`)}
                            className="btn btn-ghost w-7 h-7 p-0 rounded-md"
                          >
                            <Settings size={14} />
                          </button>
                          {isAdmin && (
                            <button
                              onClick={() => handleDelete(cam)}
                              className="btn btn-ghost w-7 h-7 p-0 rounded-md text-danger hover:text-danger"
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-12 text-center text-t3 text-sm">
                        Nenhuma câmera encontrada
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <AddCameraWizard
        open={showAdd}
        onClose={() => setShowAdd(false)}
        onCreated={() => { setShowAdd(false); load() }}
      />
    </div>
  )
}
