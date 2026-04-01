import { useState, useRef } from 'react'
import { Save, Palette, Upload } from 'lucide-react'
import { useThemeStore } from '@/store/themeStore'
import toast from 'react-hot-toast'

const ACCENT_PRESETS = [
  { label: 'Azul',    color: '#3B82F6' },
  { label: 'Violeta', color: '#8B5CF6' },
  { label: 'Verde',   color: '#22C55E' },
  { label: 'Roxo',    color: '#A855F7' },
  { label: 'Rosa',    color: '#EC4899' },
  { label: 'Laranja', color: '#F97316' },
  { label: 'Cyan',    color: '#06B6D4' },
  { label: 'Amarelo', color: '#EAB308' },
]

export function SettingsPage() {
  const { accentColor, systemName, logoUrl, setTheme } = useThemeStore()

  const [name, setName]         = useState(systemName)
  const [accent, setAccent]     = useState(accentColor)
  const [logo, setLogo]         = useState(logoUrl ?? '')
  const [saving, setSaving]     = useState(false)
  const fileInputRef            = useRef<HTMLInputElement>(null)

  const handleLogoFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => setLogo(ev.target?.result as string)
    reader.readAsDataURL(file)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      setTheme({ accentColor: accent, systemName: name, logoUrl: logo || null })
      toast.success('Configurações salvas')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-2xl space-y-6 animate-fade-in">
      <div>
        <p className="text-sm font-semibold text-t1 mb-1">Aparência do Sistema</p>
        <p className="text-xs text-t3">Personalize o nome, logo e cor do sistema</p>
      </div>

      {/* System name */}
      <div className="card p-5 space-y-4">
        <p className="text-xs font-semibold text-t2 uppercase tracking-wide">Identidade</p>

        <div>
          <label className="label">Nome do Sistema</label>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="VMS"
          />
        </div>

        <div>
          <label className="label">Logo (upload ou URL)</label>
          <div className="flex gap-2">
            <input
              className="input flex-1"
              value={logo}
              onChange={(e) => setLogo(e.target.value)}
              placeholder="https://exemplo.com/logo.png"
            />
            <button
              type="button"
              className="btn btn-ghost gap-1.5 shrink-0"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload size={14} />Upload
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleLogoFile}
            />
          </div>
        </div>

        {logo && (
          <div className="flex items-center gap-3">
            <p className="text-xs text-t3">Preview:</p>
            <img
              src={logo}
              alt="Logo preview"
              className="h-10 w-auto object-contain rounded"
              onError={() => toast.error('Logo inválido')}
            />
            <button
              type="button"
              className="text-xs text-danger hover:underline"
              onClick={() => setLogo('')}
            >
              Remover
            </button>
          </div>
        )}
      </div>

      {/* Accent color */}
      <div className="card p-5 space-y-4">
        <p className="text-xs font-semibold text-t2 uppercase tracking-wide flex items-center gap-2">
          <Palette size={14} />Cor de Destaque
        </p>

        <div className="flex flex-wrap gap-2">
          {ACCENT_PRESETS.map(({ label, color }) => (
            <button
              key={color}
              title={label}
              onClick={() => setAccent(color)}
              className="w-8 h-8 rounded-lg transition-all border-2"
              style={{
                background: color,
                borderColor: accent === color ? 'white' : 'transparent',
                transform: accent === color ? 'scale(1.15)' : 'scale(1)',
              }}
            />
          ))}
        </div>

        <div>
          <label className="label">Cor Personalizada</label>
          <div className="flex items-center gap-3">
            <input
              type="color"
              className="w-10 h-10 rounded-lg cursor-pointer border-0 p-0.5"
              style={{ background: 'var(--elevated)' }}
              value={accent}
              onChange={(e) => setAccent(e.target.value)}
            />
            <input
              className="input font-mono"
              value={accent}
              onChange={(e) => setAccent(e.target.value)}
              placeholder="#3B82F6"
            />
          </div>
        </div>

        {/* Preview */}
        <div className="flex items-center gap-3">
          <p className="text-xs text-t3">Preview:</p>
          <button
            className="btn text-white text-xs"
            style={{ background: accent }}
          >
            Botão Primário
          </button>
          <div
            className="w-6 h-6 rounded-md"
            style={{ background: accent }}
          />
        </div>
      </div>

      <button
        className="btn btn-primary gap-2"
        onClick={handleSave}
        disabled={saving}
      >
        <Save size={16} />{saving ? 'Salvando...' : 'Salvar Configurações'}
      </button>
    </div>
  )
}
