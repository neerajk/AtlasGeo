import type { GeoJsonFeature, CogLayer } from '../types'

const TITILER_URL = import.meta.env.VITE_TITILER_URL ?? 'http://localhost:8001'

const BANDS: { key: string; label: string; rescale: string }[] = [
  { key: 'visual',   label: 'True Color',  rescale: '0,3000' },
  { key: 'B04',      label: 'Red (B04)',   rescale: '0,3000' },
  { key: 'B08',      label: 'NIR (B08)',   rescale: '0,5000' },
  { key: 'B03',      label: 'Green (B03)', rescale: '0,3000' },
  { key: 'B02',      label: 'Blue (B02)',  rescale: '0,3000' },
]

function buildTileUrl(href: string, rescale: string): string {
  const encoded = encodeURIComponent(href)
  return `${TITILER_URL}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}@2x.png?url=${encoded}&rescale=${rescale}`
}

interface LayerPanelProps {
  feature: GeoJsonFeature | null
  layers: CogLayer[]
  onAddLayer: (layer: CogLayer) => void
  onToggleLayer: (id: string) => void
  onOpacityChange: (id: string, opacity: number) => void
  onRemoveLayer: (id: string) => void
}

export function LayerPanel({
  feature,
  layers,
  onAddLayer,
  onToggleLayer,
  onOpacityChange,
  onRemoveLayer,
}: LayerPanelProps) {
  const handleLoadBand = (bandKey: string, bandLabel: string, rescale: string) => {
    if (!feature) return
    const href = feature.properties.download_links[bandKey]
    if (!href) return
    const id = `${feature.properties.id}-${bandKey}`
    if (layers.find((l) => l.id === id)) return
    onAddLayer({
      id,
      name: `${bandLabel}`,
      sceneId: feature.properties.id,
      band: bandKey,
      tileUrl: buildTileUrl(href, rescale),
      visible: true,
      opacity: 1,
    })
  }

  return (
    <div style={styles.panel}>
      {feature ? (
        <>
          <div style={styles.section}>
            <div style={styles.sectionTitle}>Scene</div>
            <div style={styles.meta}>
              <span style={styles.metaLabel}>ID</span>
              <span style={styles.metaValue}>{feature.properties.id.slice(0, 24)}…</span>
            </div>
            {feature.properties.datetime && (
              <div style={styles.meta}>
                <span style={styles.metaLabel}>Date</span>
                <span style={styles.metaValue}>
                  {new Date(feature.properties.datetime).toLocaleDateString()}
                </span>
              </div>
            )}
            {feature.properties.cloud_cover != null && (
              <div style={styles.meta}>
                <span style={styles.metaLabel}>Cloud</span>
                <span style={styles.metaValue}>{feature.properties.cloud_cover.toFixed(1)}%</span>
              </div>
            )}
            <div style={styles.meta}>
              <span style={styles.metaLabel}>Platform</span>
              <span style={styles.metaValue}>{feature.properties.platform}</span>
            </div>
          </div>

          <div style={styles.section}>
            <div style={styles.sectionTitle}>Load Band</div>
            <div style={styles.bandGrid}>
              {BANDS.map(({ key, label, rescale }) => {
                const available = !!feature.properties.download_links[key]
                const loaded = layers.some((l) => l.id === `${feature.properties.id}-${key}`)
                return (
                  <button
                    key={key}
                    style={{
                      ...styles.bandBtn,
                      ...(loaded ? styles.bandBtnLoaded : {}),
                      ...(!available ? styles.bandBtnDisabled : {}),
                    }}
                    disabled={!available || loaded}
                    onClick={() => handleLoadBand(key, label, rescale)}
                    title={available ? (loaded ? 'Already loaded' : `Load ${label}`) : 'Not available'}
                  >
                    {label}
                  </button>
                )
              })}
            </div>
          </div>
        </>
      ) : (
        <div style={styles.empty}>Click a footprint to view bands</div>
      )}

      {layers.length > 0 && (
        <div style={styles.section}>
          <div style={styles.sectionTitle}>Layers</div>
          {[...layers].reverse().map((layer) => (
            <div key={layer.id} style={styles.layerRow}>
              <button
                style={{ ...styles.visBtn, opacity: layer.visible ? 1 : 0.4 }}
                onClick={() => onToggleLayer(layer.id)}
                title={layer.visible ? 'Hide' : 'Show'}
              >
                {layer.visible ? '👁' : '👁‍🗨'}
              </button>
              <span style={styles.layerName} title={layer.name}>
                {layer.name}
              </span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={layer.opacity}
                style={styles.opacitySlider}
                onChange={(e) => onOpacityChange(layer.id, parseFloat(e.target.value))}
              />
              <button
                style={styles.removeBtn}
                onClick={() => onRemoveLayer(layer.id)}
                title="Remove layer"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  panel: {
    background: '#1a1a2e',
    color: '#e0e0e0',
    fontSize: 12,
    overflowY: 'auto',
    maxHeight: '100%',
    borderTop: '1px solid #2a2a4a',
  },
  section: {
    padding: '10px 12px',
    borderBottom: '1px solid #2a2a4a',
  },
  sectionTitle: {
    fontSize: 10,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    color: '#7070a0',
    marginBottom: 8,
  },
  meta: {
    display: 'flex',
    justifyContent: 'space-between',
    marginBottom: 4,
    gap: 8,
  },
  metaLabel: {
    color: '#7070a0',
    flexShrink: 0,
  },
  metaValue: {
    color: '#c0c0e0',
    textAlign: 'right',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  bandGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 6,
  },
  bandBtn: {
    background: '#2a2a4a',
    border: '1px solid #3a3a6a',
    color: '#c0c0ff',
    borderRadius: 4,
    padding: '5px 0',
    cursor: 'pointer',
    fontSize: 11,
    transition: 'background 0.15s',
  },
  bandBtnLoaded: {
    background: '#1a3a1a',
    border: '1px solid #3a6a3a',
    color: '#80ff80',
    cursor: 'default',
  },
  bandBtnDisabled: {
    opacity: 0.35,
    cursor: 'not-allowed',
  },
  empty: {
    padding: '20px 12px',
    color: '#505070',
    textAlign: 'center',
    fontStyle: 'italic',
  },
  layerRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    marginBottom: 6,
  },
  visBtn: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: 0,
    fontSize: 14,
    lineHeight: 1,
    flexShrink: 0,
  },
  layerName: {
    flex: 1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    color: '#c0c0e0',
  },
  opacitySlider: {
    width: 60,
    flexShrink: 0,
    accentColor: '#6060ff',
  },
  removeBtn: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    color: '#606080',
    fontSize: 16,
    lineHeight: 1,
    padding: 0,
    flexShrink: 0,
  },
}
