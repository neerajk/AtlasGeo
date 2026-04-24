import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import type { CogLayer, GeoJsonFeature } from '../types'

import 'maplibre-gl/dist/maplibre-gl.css'

const TITILER_URL = import.meta.env.VITE_TITILER_URL ?? 'http://localhost:8001'

const BANDS = [
  // visual is an 8-bit TCI (pre-rendered by ESA) — rescale to 0,255, no gamma needed
  { key: 'visual',  label: 'True Color', color: '#c8c8c8', rescale: '0,255',  gamma: false },
  // 16-bit surface reflectance bands — floor at 100 to cut nodata shadow noise
  { key: 'red',     label: 'Red',        color: '#e05050', rescale: '100,3000', gamma: true },
  { key: 'nir',     label: 'NIR',        color: '#9040d0', rescale: '100,5000', gamma: true },
  { key: 'green',   label: 'Green',      color: '#3db860', rescale: '100,3000', gamma: true },
  { key: 'blue',    label: 'Blue',       color: '#4090e0', rescale: '100,3000', gamma: true },
  { key: 'swir16',  label: 'SWIR1',      color: '#e07830', rescale: '100,3000', gamma: true },
]

const BAND_COLOR: Record<string, string> = {
  ...Object.fromEntries(BANDS.map((b) => [b.key, b.color])),
  flood: '#30b8e8', swir22: '#d05a20', burn_scar: '#e04020',
  ndvi: '#3db860', ndwi: '#3090e0', ndbi: '#e07830',
}
const bandColor = (band: string) => BAND_COLOR[band] ?? '#6060a0'

const MAP_STYLE = {
  version: 8 as const,
  sources: {
    esri: {
      type: 'raster' as const,
      tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
      tileSize: 256, maxzoom: 19,
    },
  },
  layers: [{ id: 'esri-imagery', type: 'raster' as const, source: 'esri' }],
}

function buildTileUrl(href: string, rescale: string, gamma = false) {
  const base = `${TITILER_URL}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png?url=${encodeURIComponent(href)}&rescale=${rescale}`
  return gamma ? `${base}&color_formula=gamma+R+1.7` : base
}

function featureBbox(feat: GeoJsonFeature): [[number, number], [number, number]] | null {
  const coords: number[][] =
    feat.geometry.type === 'Polygon'
      ? (feat.geometry.coordinates as number[][][])[0]
      : feat.geometry.type === 'MultiPolygon'
      ? (feat.geometry.coordinates as number[][][][]).flat(2)
      : []
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  coords.forEach(([x, y]) => {
    minX = Math.min(minX, x); minY = Math.min(minY, y)
    maxX = Math.max(maxX, x); maxY = Math.max(maxY, y)
  })
  return isFinite(minX) ? [[minX, minY], [maxX, maxY]] : null
}

function syncCogLayers(map: maplibregl.Map, layers: CogLayer[]) {
  const style = map.getStyle()
  const existingSrc = new Set<string>()
  const existingLay = new Set<string>()
  if (style?.sources) Object.keys(style.sources).forEach((id) => { if (id.startsWith('cog-')) existingSrc.add(id) })
  if (style?.layers)  style.layers.forEach((l) => { if (l.id.startsWith('cog-')) existingLay.add(l.id) })

  const wanted = new Set(layers.map((l) => `cog-${l.id}`))
  existingLay.forEach((lid) => { if (!wanted.has(lid) && map.getLayer(lid))   map.removeLayer(lid) })
  existingSrc.forEach((sid) => { if (!wanted.has(sid) && map.getSource(sid)) map.removeSource(sid) })

  layers.forEach((cog) => {
    const sid = `cog-${cog.id}`, lid = `cog-${cog.id}`
    if (!map.getSource(sid)) map.addSource(sid, { type: 'raster', tiles: [cog.tileUrl], tileSize: 512 })
    if (!map.getLayer(lid))  map.addLayer({ id: lid, type: 'raster', source: sid, paint: { 'raster-opacity': cog.visible ? cog.opacity : 0 } })
    else                     map.setPaintProperty(lid, 'raster-opacity', cog.visible ? cog.opacity : 0)
  })
}

// ─── Public component ───────────────────────────────────────────

interface SceneDrawerProps {
  feature:         GeoJsonFeature | null
  cogLayers:       CogLayer[]
  onAddLayer:      (layer: CogLayer) => void
  onToggleLayer:   (id: string) => void
  onOpacityChange: (id: string, opacity: number) => void
  onRemoveLayer:   (id: string) => void
  onClose:         () => void
}

export function SceneDrawer(props: SceneDrawerProps) {
  const open = props.feature !== null
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: '#08080f',
      opacity: open ? 1 : 0,
      pointerEvents: open ? 'auto' : 'none',
      transition: 'opacity 0.2s ease',
    }}>
      {open && props.feature && <PopupContent {...props} feature={props.feature} />}
    </div>
  )
}

// ─── Popup content (own map instance) ───────────────────────────

function PopupContent({
  feature, cogLayers,
  onAddLayer, onToggleLayer, onOpacityChange, onRemoveLayer, onClose,
}: SceneDrawerProps & { feature: GeoJsonFeature }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef       = useRef<maplibregl.Map | null>(null)
  const readyRef     = useRef(false)
  const loadedIds    = new Set(cogLayers.map((l) => l.id))

  const [visible, setVisible] = useState(false)
  useEffect(() => { requestAnimationFrame(() => setVisible(true)) }, [])

  // Init map once on mount
  useEffect(() => {
    if (!containerRef.current) return
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE, center: [0, 0], zoom: 2,
      attributionControl: { compact: true },
    })
    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.on('load', () => {
      readyRef.current = true
      const bbox = featureBbox(feature)
      if (bbox) map.fitBounds(bbox, { padding: 80, duration: 800 })
      syncCogLayers(map, cogLayers)
    })
    mapRef.current = map
    return () => { readyRef.current = false; map.remove(); mapRef.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (mapRef.current && readyRef.current) syncCogLayers(mapRef.current, cogLayers)
  }, [cogLayers])

  const handleLoad = (bandKey: string, bandLabel: string, rescale: string, gamma: boolean) => {
    const href = feature.properties.download_links[bandKey]
    if (!href) return
    const id = `${feature.properties.id}-${bandKey}`
    if (loadedIds.has(id)) return
    onAddLayer({ id, name: bandLabel, sceneId: feature.properties.id, band: bandKey,
      tileUrl: buildTileUrl(href, rescale, gamma), visible: true, opacity: 1 })
  }

  const dateStr = feature.properties.datetime
    ? new Date(feature.properties.datetime).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
    : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', opacity: visible ? 1 : 0, transition: 'opacity 0.18s ease' }}>

      {/* ── Top bar ── */}
      <div style={s.topBar}>
        <span style={s.topIcon}>▦</span>
        <span style={s.topId} title={feature.properties.id}>{feature.properties.id}</span>
        <span style={{ flex: 1 }} />
        <button onClick={onClose} style={s.closeBtn}>✕ Close</button>
      </div>

      {/* ── Body ── */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', display: 'flex' }}>

        {/* Map canvas */}
        <div ref={containerRef} style={{ flex: 1, height: '100%' }} />

        {/* ── Left panel ── */}
        <div style={s.panel}>

          {/* 1. Metadata */}
          <Section title="Scene Info">
            <Meta label="ID"       value={feature.properties.id} mono truncate />
            {dateStr && <Meta label="Date"  value={dateStr} />}
            {feature.properties.cloud_cover != null && (
              <Meta label="Cloud"    value={`${feature.properties.cloud_cover.toFixed(1)} %`} />
            )}
            <Meta label="Platform" value={feature.properties.platform} />
            <Meta label="Source"   value="Element84 / Sentinel-2 L2A" />
          </Section>

          <Divider />

          {/* 2. Loaded layers (eye on/off) */}
          <Section title="Layers" count={cogLayers.length}>
            {cogLayers.length === 0
              ? <p style={s.hint}>No layers — add a band below</p>
              : [...cogLayers].reverse().map((layer) => (
                  <LayerRow
                    key={layer.id}
                    layer={layer}
                    onToggle={() => onToggleLayer(layer.id)}
                    onOpacity={(v) => onOpacityChange(layer.id, v)}
                    onRemove={() => onRemoveLayer(layer.id)}
                  />
                ))
            }
          </Section>

          <Divider />

          {/* 3. Add layer */}
          <Section title="Add Layer">
            {BANDS.map(({ key, label, color, rescale, gamma }) => {
              const available = !!feature.properties.download_links[key]
              const loaded    = loadedIds.has(`${feature.properties.id}-${key}`)
              return (
                <div key={key} style={{ ...s.bandRow, opacity: available ? 1 : 0.22 }}>
                  <div style={{ ...s.swatch, background: available ? color : '#161628' }} />
                  <span style={{ ...s.bandLabel, color: available ? '#5a5a92' : '#1c1c38' }}>{label}</span>
                  <span style={s.bandKey}>{key}</span>
                  {loaded
                    ? <span style={s.loadedTag}>✓</span>
                    : available
                    ? <button onClick={() => handleLoad(key, label, rescale, gamma)} style={s.addBtn}>+ Add</button>
                    : <span style={s.unavail}>—</span>
                  }
                </div>
              )
            })}
          </Section>

          <Divider />

          {/* 4. Downloads — always at bottom */}
          <Section title="Downloads">
            {Object.entries(feature.properties.download_links).length === 0
              ? <p style={s.hint}>No assets available</p>
              : Object.entries(feature.properties.download_links).map(([key, url]) => (
                  <a
                    key={key}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={s.dlRow}
                    title={url}
                  >
                    <span style={s.dlIcon}>↓</span>
                    <span style={s.dlKey}>{key}</span>
                    <span style={s.dlFile}>{url.split('/').pop()?.split('?')[0] ?? url}</span>
                  </a>
                ))
            }
          </Section>

        </div>
      </div>
    </div>
  )
}

// ─── Sub-components ─────────────────────────────────────────────

function Section({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
  return (
    <div style={s.section}>
      <div style={s.sHead}>
        <span style={s.sTitle}>{title}</span>
        {count != null && count > 0 && <span style={s.badge}>{count}</span>}
      </div>
      {children}
    </div>
  )
}

function Divider() {
  return <div style={{ height: 1, background: '#0c0c1a', flexShrink: 0 }} />
}

function Meta({ label, value, mono, truncate }: { label: string; value: string; mono?: boolean; truncate?: boolean }) {
  return (
    <div style={s.metaRow}>
      <span style={s.metaLabel}>{label}</span>
      <span
        style={{ ...s.metaValue, fontFamily: mono ? 'monospace' : 'inherit', fontSize: mono ? 10 : 11 }}
        title={truncate ? value : undefined}
      >
        {truncate && value.length > 20 ? value.slice(0, 20) + '…' : value}
      </span>
    </div>
  )
}

function LayerRow({ layer, onToggle, onOpacity, onRemove }: {
  layer: CogLayer; onToggle: () => void; onOpacity: (v: number) => void; onRemove: () => void
}) {
  const color = bandColor(layer.band)
  return (
    <div style={s.layerRow}>
      <div style={{ ...s.strip, background: layer.visible ? color : '#161628' }} />

      {/* Eye toggle */}
      <button onClick={onToggle} style={s.eyeBtn} title={layer.visible ? 'Hide' : 'Show'}>
        <span style={{ fontSize: 13, opacity: layer.visible ? 1 : 0.25, lineHeight: 1 }}>
          {layer.visible ? '👁' : '👁'}
        </span>
      </button>

      <span style={{ fontSize: 11, color: layer.visible ? color : '#252548', flexShrink: 0 }}>▦</span>

      <div style={s.layerInfo}>
        <span style={{ ...s.layerName, color: layer.visible ? '#aaaacc' : '#303050' }} title={layer.name}>
          {layer.name}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
          <span style={s.pill}>{layer.band}</span>
          <span style={s.pct}>{Math.round(layer.opacity * 100)}%</span>
          <input
            type="range" min={0} max={1} step={0.01} value={layer.opacity}
            onChange={(e) => onOpacity(parseFloat(e.target.value))}
            style={{ flex: 1, height: 2, cursor: 'pointer', accentColor: color }}
          />
        </div>
      </div>

      <button onClick={onRemove} style={s.removeBtn} title="Remove">×</button>
    </div>
  )
}

// ─── Styles ─────────────────────────────────────────────────────

const s: Record<string, React.CSSProperties> = {
  topBar: {
    display: 'flex', alignItems: 'center', gap: 10,
    height: 48, flexShrink: 0,
    padding: '0 16px',
    background: '#06060e',
    borderBottom: '1px solid #131325',
  },
  topIcon: { fontSize: 14, color: '#35358a', flexShrink: 0 },
  topId:   { fontSize: 11, color: '#404080', fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 400 },
  closeBtn: {
    background: '#0e0e24', border: '1px solid #1c1c40', borderRadius: 6,
    color: '#505090', fontSize: 11, fontWeight: 600,
    padding: '5px 14px', cursor: 'pointer', flexShrink: 0,
  },
  panel: {
    width: 256, flexShrink: 0,
    background: 'rgba(6,6,14,0.92)',
    backdropFilter: 'blur(10px)',
    borderRight: '1px solid #101020',
    display: 'flex', flexDirection: 'column',
    overflowY: 'auto',
  },
  section:  { padding: '10px 11px 10px', flexShrink: 0 },
  sHead:    { display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 },
  sTitle:   { fontSize: 9, fontWeight: 700, textTransform: 'uppercase' as const, letterSpacing: '0.14em', color: '#22224a' },
  badge:    { fontSize: 9, background: '#0e0e28', color: '#303078', borderRadius: 8, padding: '1px 5px', fontWeight: 700, border: '1px solid #161640' },
  hint:     { fontSize: 10, color: '#1a1a36', margin: 0, fontStyle: 'italic' },
  metaRow:  { display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8, marginBottom: 5 },
  metaLabel: { fontSize: 10, color: '#28284a', flexShrink: 0 },
  metaValue: { fontSize: 11, color: '#606090', textAlign: 'right' as const, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '60%' },
  layerRow: { display: 'flex', alignItems: 'center', gap: 5, paddingRight: 3, paddingBottom: 7, borderBottom: '1px solid #090916', marginBottom: 5 },
  strip:    { width: 3, alignSelf: 'stretch', flexShrink: 0, borderRadius: '0 2px 2px 0' },
  eyeBtn:   { background: 'none', border: 'none', cursor: 'pointer', padding: '0 1px', flexShrink: 0, display: 'flex', alignItems: 'center' },
  layerInfo: { flex: 1, minWidth: 0 },
  layerName: { fontSize: 11, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const, lineHeight: 1.3 },
  pill:     { fontSize: 9, fontFamily: 'monospace', color: '#1e1e3a', background: '#0c0c20', border: '1px solid #141430', borderRadius: 2, padding: '0 3px', flexShrink: 0 },
  pct:      { fontSize: 9, color: '#1c1c38', fontFamily: 'monospace', width: 24, flexShrink: 0 },
  removeBtn: { background: 'none', border: 'none', cursor: 'pointer', color: '#1c1c38', fontSize: 16, lineHeight: 1, padding: '0 2px', flexShrink: 0 },
  bandRow:  { display: 'flex', alignItems: 'center', gap: 6, padding: '5px 0', borderBottom: '1px solid #090916' },
  swatch:   { width: 10, height: 10, borderRadius: 2, flexShrink: 0 },
  bandLabel: { flex: 1, fontSize: 11, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const },
  bandKey:  { fontSize: 9, color: '#1a1a36', fontFamily: 'monospace', width: 44, flexShrink: 0 },
  addBtn:   { background: '#0e0e24', border: '1px solid #181838', borderRadius: 3, color: '#303080', fontSize: 10, fontWeight: 600, padding: '2px 7px', cursor: 'pointer', flexShrink: 0 },
  loadedTag: { fontSize: 9, color: '#254835', fontWeight: 700, flexShrink: 0 },
  unavail:  { fontSize: 11, color: '#111128', flexShrink: 0 },
  dlRow: {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '5px 0', borderBottom: '1px solid #090916',
    textDecoration: 'none',
  },
  dlIcon:  { fontSize: 11, color: '#252550', flexShrink: 0 },
  dlKey:   { fontSize: 10, color: '#303068', fontFamily: 'monospace', fontWeight: 600, width: 50, flexShrink: 0 },
  dlFile:  { fontSize: 10, color: '#1c1c38', fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const, flex: 1 },
}
