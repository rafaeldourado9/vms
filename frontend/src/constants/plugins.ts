/** Labels pt-BR canonicos para plugins de analytics. */
export const PLUGIN_NAMES: Record<string, string> = {
  fire_smoke:      'Incêndio/Fumaça',
  ppe_detection:   'EPIs',
  biker_detection: 'Capacete Moto',
  horse_cart:      'Cavalo/Carroça',
  intrusion:       'Intrusão',
  people_count:    'Pessoas',
  vehicle_count:   'Veículos',
  lpr:             'Placa (LPR)',
}

/** Cor hex por severidade de evento — usada em marcadores de timeline e chips. */
export const SEV_COLOR: Record<string, string> = {
  critical: '#ef4444',
  warning:  '#f59e0b',
  info:     '#60a5fa',
}

/** Estilo completo por severidade — background translúcido, texto e dot. */
export const SEV_STYLE: Record<string, { bg: string; text: string; dot: string }> = {
  critical: { bg: 'rgba(239,68,68,0.12)',  text: '#f87171', dot: SEV_COLOR.critical },
  warning:  { bg: 'rgba(245,158,11,0.12)', text: '#fbbf24', dot: SEV_COLOR.warning  },
  info:     { bg: 'rgba(96,165,250,0.12)', text: '#93c5fd', dot: SEV_COLOR.info     },
}
