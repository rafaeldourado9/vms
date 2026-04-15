import { PLUGIN_CONFIG_SCHEMA } from '@/constants/pluginConfigs'

interface Props {
  pluginId: string
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
  disabled?: boolean
}

export function PluginConfigForm({ pluginId, config, onChange, disabled }: Props) {
  const fields = PLUGIN_CONFIG_SCHEMA[pluginId] ?? []

  if (fields.length === 0) {
    return (
      <p className="text-xs text-t3 py-2">
        Nenhuma configuracao adicional para este plugin.
      </p>
    )
  }

  const handleChange = (key: string, value: number | string) => {
    onChange({ ...config, [key]: value })
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {fields.map((f) => (
        <div key={f.key}>
          <label className="text-xs text-t3 mb-1 block">{f.label}</label>
          <input
            type={f.type === 'number' ? 'number' : 'text'}
            value={config[f.key] != null ? String(config[f.key]) : String(f.default)}
            min={f.min}
            max={f.max}
            step={f.step}
            disabled={disabled}
            onChange={(e) => {
              const val = f.type === 'number' ? parseFloat(e.target.value) || 0 : e.target.value
              handleChange(f.key, val)
            }}
            className="w-full px-3 py-1.5 rounded-lg border text-sm text-t1 outline-none focus:border-accent/60 transition"
            style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
          />
        </div>
      ))}
    </div>
  )
}
