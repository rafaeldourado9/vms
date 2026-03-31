import { useEffect, useState } from 'react'
import { Plus, UserX, Shield, Eye } from 'lucide-react'
import { format } from 'date-fns'
import { usersService } from '@/services/users'
import { PageSpinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import toast from 'react-hot-toast'
import type { User } from '@/types'

interface CreateForm {
  email: string
  password: string
  full_name: string
  role: string
}

const DEFAULT_FORM: CreateForm = { email: '', password: '', full_name: '', role: 'viewer' }

const ROLE_ICON: Record<string, React.ElementType> = {
  admin:    Shield,
  operator: Eye,
  viewer:   Eye,
}

const ROLE_BADGE: Record<string, 'danger' | 'warning' | 'default'> = {
  admin:    'danger',
  operator: 'warning',
  viewer:   'default',
}

export function UsersPage() {
  const [users, setUsers]         = useState<User[]>([])
  const [loading, setLoading]     = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating]   = useState(false)
  const [form, setForm]           = useState<CreateForm>(DEFAULT_FORM)

  const load = () => {
    usersService.list().then(setUsers).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    if (!form.email || !form.password || !form.full_name) return
    setCreating(true)
    try {
      await usersService.create(form)
      toast.success('Usuário criado')
      setShowCreate(false)
      setForm(DEFAULT_FORM)
      load()
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      toast.error(axiosErr.response?.data?.detail ?? 'Erro ao criar usuário')
    } finally {
      setCreating(false)
    }
  }

  const handleDeactivate = async (user: User) => {
    if (!confirm(`Desativar usuário "${user.full_name}"?`)) return
    try {
      await usersService.deactivate(user.id)
      toast.success('Usuário desativado')
      load()
    } catch { toast.error('Erro ao desativar usuário') }
  }

  if (loading) return <PageSpinner />

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <p className="text-xs text-t3">{users.length} usuários cadastrados</p>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={16} />Novo Usuário
        </button>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left" style={{ borderColor: 'var(--border)' }}>
              {['Nome', 'Email', 'Papel', 'Status', 'Criado em', ''].map((h) => (
                <th key={h} className="px-4 py-3 text-xs font-medium text-t3">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.map((user) => {
              const Icon = ROLE_ICON[user.role] ?? Eye
              return (
                <tr key={user.id} className="border-b hover:bg-elevated transition" style={{ borderColor: 'var(--border)' }}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-semibold shrink-0"
                        style={{ background: 'var(--accent)' }}
                      >
                        {user.full_name.charAt(0).toUpperCase()}
                      </div>
                      <span className="font-medium text-t1">{user.full_name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-t2 text-xs">{user.email}</td>
                  <td className="px-4 py-3">
                    <Badge variant={ROLE_BADGE[user.role] ?? 'default'}>
                      <Icon size={10} />
                      {user.role}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={user.is_active ? 'success' : 'danger'} dot>
                      {user.is_active ? 'Ativo' : 'Inativo'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-t3 text-xs">
                    {format(new Date(user.created_at), 'dd/MM/yyyy')}
                  </td>
                  <td className="px-4 py-3">
                    {user.is_active && (
                      <button
                        className="btn btn-ghost w-7 h-7 p-0 rounded-md text-danger"
                        onClick={() => handleDeactivate(user)}
                        title="Desativar usuário"
                      >
                        <UserX size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
            {users.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-t3 text-sm">
                  Nenhum usuário encontrado
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Create modal */}
      <Modal
        open={showCreate}
        onClose={() => { setShowCreate(false); setForm(DEFAULT_FORM) }}
        title="Novo Usuário"
        size="sm"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setShowCreate(false)}>Cancelar</button>
            <button
              className="btn btn-primary"
              onClick={handleCreate}
              disabled={creating || !form.email || !form.password || !form.full_name}
            >
              {creating ? 'Criando...' : 'Criar'}
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="label">Nome Completo *</label>
            <input
              className="input"
              placeholder="João Silva"
              value={form.full_name}
              onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
            />
          </div>
          <div>
            <label className="label">Email *</label>
            <input
              type="email"
              className="input"
              placeholder="joao@empresa.com"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            />
          </div>
          <div>
            <label className="label">Senha *</label>
            <input
              type="password"
              className="input"
              placeholder="Mínimo 8 caracteres"
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
            />
          </div>
          <div>
            <label className="label">Papel</label>
            <select
              className="input"
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
            >
              <option value="viewer">Viewer — Apenas visualização</option>
              <option value="operator">Operator — Pode criar clips e eventos</option>
              <option value="admin">Admin — Acesso total</option>
            </select>
          </div>
        </div>
      </Modal>
    </div>
  )
}
