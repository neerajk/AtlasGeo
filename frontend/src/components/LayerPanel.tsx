import type { CogLayer } from '../types'

interface LayerPanelProps {
  layers: CogLayer[]
  onToggleLayer: (id: string) => void
  onOpacityChange: (id: string, opacity: number) => void
  onRemoveLayer: (id: string) => void
}

const BAND_COLOR: Record<string, string> = {
  visual:  '#c0c0c0',
  red:     '#e05050',
  nir:     '#9040d0',
  green:   '#3db060',
  blue:    '#4088e0',
  swir16:  '#e07830',
  swir22:  '#d05a20',
  flood:   '#30b8e8',
}

function bandColor(band: string): string {
  return BAND_COLOR[band] ?? '#6060a0'
}

export function LayerPanel({ layers, onToggleLayer, onOpacityChange, onRemoveLayer }: LayerPanelProps) {
  return (
    <div style={s.panel}>

      {/* ── Header toolbar ── */}
      <div style={s.toolbar}>
        <span style={s.toolbarTitle}>Layers</span>
        {layers.length > 0 && (
          <span style={s.count}>{layers.length}</span>
        )}
      </div>

      {layers.length === 0 ? (
        <div style={s.empty}>
          <span style={s.emptyText}>No layers loaded</span>
          <span style={s.emptyHint}>Click a scene footprint to load bands</span>
        </div>
      ) : (
        <div style={s.list}>
          {[...layers].reverse().map((layer) => (
            <LayerRow
              key={layer.id}
              layer={layer}
              onToggle={() => onToggleLayer(layer.id)}
              onOpacity={(v) => onOpacityChange(layer.id, v)}
              onRemove={() => onRemoveLayer(layer.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function LayerRow({
  layer, onToggle, onOpacity, onRemove,
}: {
  layer: CogLayer
  onToggle: () => void
  onOpacity: (v: number) => void
  onRemove: () => void
}) {
  const color = bandColor(layer.band)

  return (
    <div style={s.row}>
      {/* Left accent strip — colored by band type */}
      <div style={{ ...s.strip, background: layer.visible ? color : '#1e1e38' }} />

      {/* Visibility checkbox */}
      <button
        onClick={onToggle}
        style={s.checkbox}
        title={layer.visible ? 'Hide layer' : 'Show layer'}
      >
        <div style={{
          ...s.checkboxInner,
          background: layer.visible ? color : 'transparent',
          borderColor: layer.visible ? color : '#2a2a48',
        }}>
          {layer.visible && <span style={s.checkmark}>✓</span>}
        </div>
      </button>

      {/* Raster icon */}
      <div style={{ ...s.rasterIcon, color: layer.visible ? color : '#252548' }}>▦</div>

      {/* Name + meta */}
      <div style={s.info}>
        <span
          style={{ ...s.name, color: layer.visible ? '#b0b0d8' : '#40405a' }}
          title={layer.name}
        >
          {layer.name}
        </span>
        <div style={s.metaRow}>
          <span style={s.bandTag}>{layer.band}</span>
          <span style={s.sceneId} title={layer.sceneId}>
            {layer.sceneId.slice(0, 22)}…
          </span>
        </div>

        {/* Opacity bar */}
        <div style={s.opacityRow}>
          <span style={s.opacityLabel}>{Math.round(layer.opacity * 100)}%</span>
          <input
            type="range"
            min={0} max={1} step={0.01}
            value={layer.opacity}
            onChange={(e) => onOpacity(parseFloat(e.target.value))}
            style={{ ...s.slider, accentColor: color }}
            title={`Opacity: ${Math.round(layer.opacity * 100)}%`}
          />
        </div>
      </div>

      {/* Remove */}
      <button onClick={onRemove} style={s.removeBtn} title="Remove layer">×</button>
    </div>
  )
}

const s: Record<string, React.CSSProperties> = {
  panel: {
    background: '#0c0c18',
    borderTop: '1px solid #1a1a30',
    display: 'flex',
    flexDirection: 'column',
    maxHeight: 280,
  },
  toolbar: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '7px 12px',
    borderBottom: '1px solid #141428',
    flexShrink: 0,
    background: '#09090f',
  },
  toolbarTitle: {
    fontSize: 10,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.12em',
    color: '#35355a',
  },
  count: {
    fontSize: 10,
    background: '#18183a',
    color: '#50508a',
    borderRadius: 10,
    padding: '1px 7px',
    fontWeight: 700,
    border: '1px solid #252548',
  },
  list: {
    overflowY: 'auto',
    flex: 1,
  },
  row: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '8px 10px 8px 0',
    borderBottom: '1px solid #0f0f1e',
    position: 'relative',
  },
  strip: {
    width: 3,
    alignSelf: 'stretch',
    flexShrink: 0,
    borderRadius: '0 2px 2px 0',
    transition: 'background 0.2s',
  },
  checkbox: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: 0,
    flexShrink: 0,
    display: 'flex',
    alignItems: 'center',
  },
  checkboxInner: {
    width: 14,
    height: 14,
    border: '1.5px solid',
    borderRadius: 3,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.15s',
  },
  checkmark: {
    fontSize: 9,
    color: '#000',
    fontWeight: 900,
    lineHeight: 1,
  },
  rasterIcon: {
    fontSize: 13,
    flexShrink: 0,
    transition: 'color 0.2s',
    lineHeight: 1,
  },
  info: {
    flex: 1,
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
  },
  name: {
    fontSize: 12,
    fontWeight: 500,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    transition: 'color 0.2s',
    lineHeight: 1.3,
  },
  metaRow: {
    display: 'flex',
    gap: 6,
    alignItems: 'center',
  },
  bandTag: {
    fontSize: 9,
    fontFamily: 'monospace',
    color: '#30305a',
    background: '#111128',
    border: '1px solid #1c1c38',
    borderRadius: 3,
    padding: '0px 4px',
    flexShrink: 0,
  },
  sceneId: {
    fontSize: 9,
    color: '#25253a',
    fontFamily: 'monospace',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  opacityRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 5,
    marginTop: 1,
  },
  opacityLabel: {
    fontSize: 9,
    color: '#25253a',
    width: 26,
    flexShrink: 0,
    fontFamily: 'monospace',
  },
  slider: {
    flex: 1,
    height: 2,
    cursor: 'pointer',
  },
  removeBtn: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    color: '#25253a',
    fontSize: 18,
    lineHeight: 1,
    padding: '0 4px',
    flexShrink: 0,
    transition: 'color 0.15s',
  },
  empty: {
    padding: '14px 12px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 4,
  },
  emptyText: {
    fontSize: 11,
    color: '#25253a',
  },
  emptyHint: {
    fontSize: 10,
    color: '#1a1a30',
    fontStyle: 'italic',
  },
}
