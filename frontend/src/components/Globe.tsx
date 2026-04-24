import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import { MapboxOverlay } from '@deck.gl/mapbox'
import { GeoJsonLayer } from '@deck.gl/layers'
import type { CogLayer, GeoJsonFeature } from '../types'
import { SceneDrawer } from './SceneDrawer'

import 'maplibre-gl/dist/maplibre-gl.css'

interface GlobeProps {
  features: GeoJsonFeature[]
  cogLayers: CogLayer[]
  pickerMode: { taskType: string } | null
  onSceneSelect: (sceneId: string) => void
  onAddLayer:      (layer: CogLayer) => void
  onToggleLayer:   (id: string) => void
  onOpacityChange: (id: string, opacity: number) => void
  onRemoveLayer:   (id: string) => void
}

const TASK_LABELS: Record<string, string> = {
  ndvi: 'NDVI',
  ndwi: 'NDWI',
  ndbi: 'NDBI',
  flood_mapping: 'Flood Mapping',
  burn_scar: 'Burn Scar',
}

const FREE_STYLE = {
  version: 8 as const,
  sources: {
    esri: {
      type: 'raster' as const,
      // ESRI tile order is {z}/{y}/{x} — not the usual {z}/{x}/{y}
      tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
      tileSize: 256,
      attribution: 'Tiles © <a href="https://www.esri.com/">Esri</a> — Source: Esri, Maxar, Earthstar Geographics',
      maxzoom: 19,
    },
  },
  layers: [{ id: 'esri-imagery', type: 'raster' as const, source: 'esri' }],
}

export function Globe({ features, cogLayers, pickerMode, onSceneSelect, onAddLayer, onToggleLayer, onOpacityChange, onRemoveLayer }: GlobeProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef       = useRef<maplibregl.Map | null>(null)
  const overlayRef   = useRef<MapboxOverlay | null>(null)
  const mapReadyRef  = useRef(false)
  // Refs so deck.gl callbacks always get fresh values without layer recreation
  const pickerModeRef   = useRef(pickerMode)
  const onSceneSelectRef = useRef(onSceneSelect)

  const [selectedFeature, setSelectedFeature] = useState<GeoJsonFeature | null>(null)

  // Keep refs in sync
  useEffect(() => { pickerModeRef.current = pickerMode }, [pickerMode])
  useEffect(() => { onSceneSelectRef.current = onSceneSelect }, [onSceneSelect])

  // Map init
  useEffect(() => {
    if (!containerRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: FREE_STYLE,
      center: [0, 20],
      zoom: 2,
      attributionControl: { compact: false },
    })

    map.addControl(new maplibregl.NavigationControl(), 'top-right')

    const overlay = new MapboxOverlay({ layers: [] })
    map.addControl(overlay as unknown as maplibregl.IControl)

    map.on('load', () => { mapReadyRef.current = true })

    mapRef.current     = map
    overlayRef.current = overlay

    return () => {
      mapReadyRef.current = false
      overlay.finalize()
      map.remove()
    }
  }, [])

  // Sync deck.gl footprint layer + tooltip (re-runs on features OR picker mode change)
  useEffect(() => {
    if (!overlayRef.current) return

    const isPickerActive = !!pickerMode

    const layer = new GeoJsonLayer({
      id: 'stac-footprints',
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      data: { type: 'FeatureCollection' as const, features } as any,
      filled: true,
      stroked: true,
      getFillColor: isPickerActive ? [255, 165, 0, 45] : [64, 160, 255, 35],
      getLineColor: isPickerActive ? [255, 165, 0, 220] : [64, 160, 255, 220],
      getLineWidth: isPickerActive ? 3 : 2,
      lineWidthMinPixels: 1,
      pickable: true,
      autoHighlight: true,
      highlightColor: isPickerActive ? [255, 200, 0, 100] : [255, 200, 64, 80],
      onClick: ({ object }) => {
        if (!object) return
        const feat = object as GeoJsonFeature
        if (pickerModeRef.current) {
          onSceneSelectRef.current(feat.properties.id)
        } else {
          setSelectedFeature((prev) =>
            prev?.properties.id === feat.properties.id ? null : feat
          )
        }
      },
    })

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const getTooltip = isPickerActive ? (({ object }: any) => {
      if (!object) return null
      const p = (object as GeoJsonFeature).properties
      const date = (p.datetime || '').slice(0, 10)
      const cloud = p.cloud_cover != null ? p.cloud_cover.toFixed(1) + '%' : '?'
      return {
        html: `
          <div>
            <strong style="display:block;margin-bottom:4px;font-size:12px;color:#94c4ff">${p.id}</strong>
            <span>📅 ${date}</span><br/>
            <span>☁️ ${cloud} cloud cover</span><br/>
            <span style="color:#86efac;font-size:11px;margin-top:4px;display:block">Click to select</span>
          </div>
        `,
        style: {
          background: '#1e1e2e',
          color: '#cbd5e1',
          border: '1px solid #3a3a5a',
          borderRadius: '8px',
          fontSize: '13px',
          lineHeight: '1.6',
          padding: '8px 12px',
          pointerEvents: 'none',
        },
      }
    }) : null

    overlayRef.current.setProps({ layers: [layer], getTooltip })
  }, [features, pickerMode])

  // Fly to results (separate so it doesn't re-fire on picker mode toggle)
  useEffect(() => {
    if (!features.length) return
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    features.forEach((f) => {
      const coords: number[][] =
        f.geometry.type === 'Polygon'
          ? (f.geometry.coordinates as number[][][])[0]
          : f.geometry.type === 'MultiPolygon'
          ? (f.geometry.coordinates as number[][][][]).flat(2)
          : []
      coords.forEach(([x, y]) => {
        minX = Math.min(minX, x); minY = Math.min(minY, y)
        maxX = Math.max(maxX, x); maxY = Math.max(maxY, y)
      })
    })
    if (isFinite(minX)) {
      mapRef.current?.fitBounds([[minX, minY], [maxX, maxY]], { padding: 60, duration: 1200 })
    }
  }, [features])

  // Sync COG raster layers into MapLibre
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const apply = () => {
      const existingSources = new Set<string>()
      const existingLayers  = new Set<string>()

      const style = map.getStyle()
      if (style?.sources) {
        Object.keys(style.sources).forEach((id) => {
          if (id.startsWith('cog-')) existingSources.add(id)
        })
      }
      if (style?.layers) {
        style.layers.forEach((l) => {
          if (l.id.startsWith('cog-')) existingLayers.add(l.id)
        })
      }

      const wantedIds = new Set(cogLayers.map((l) => `cog-${l.id}`))

      existingLayers.forEach((lid) => {
        if (!wantedIds.has(lid) && map.getLayer(lid)) map.removeLayer(lid)
      })
      existingSources.forEach((sid) => {
        if (!wantedIds.has(sid) && map.getSource(sid)) map.removeSource(sid)
      })

      cogLayers.forEach((cog) => {
        const srcId = `cog-${cog.id}`
        const layId = `cog-${cog.id}`

        if (!map.getSource(srcId)) {
          map.addSource(srcId, { type: 'raster', tiles: [cog.tileUrl], tileSize: 512 })
        }

        if (!map.getLayer(layId)) {
          map.addLayer({
            id: layId, type: 'raster', source: srcId,
            paint: { 'raster-opacity': cog.visible ? cog.opacity : 0 },
          })
        } else {
          map.setPaintProperty(layId, 'raster-opacity', cog.visible ? cog.opacity : 0)
        }
      })
    }

    if (mapReadyRef.current) {
      apply()
    } else {
      mapRef.current?.once('load', apply)
    }
  }, [cogLayers])

  const taskLabel = pickerMode ? (TASK_LABELS[pickerMode.taskType] || pickerMode.taskType) : ''

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div
        ref={containerRef}
        style={{ width: '100%', height: '100%', cursor: pickerMode ? 'crosshair' : undefined }}
      />

      {pickerMode && (
        <div style={pickerBannerStyle}>
          <span style={{ fontSize: 14 }}>🎯</span>
          <span>Click a scene footprint to run <strong>{taskLabel}</strong> analysis</span>
        </div>
      )}

      <SceneDrawer
        feature={selectedFeature}
        cogLayers={cogLayers}
        onAddLayer={onAddLayer}
        onToggleLayer={onToggleLayer}
        onOpacityChange={onOpacityChange}
        onRemoveLayer={onRemoveLayer}
        onClose={() => setSelectedFeature(null)}
      />
    </div>
  )
}

const pickerBannerStyle: React.CSSProperties = {
  position: 'absolute',
  top: 12,
  left: '50%',
  transform: 'translateX(-50%)',
  background: 'rgba(26, 42, 26, 0.92)',
  border: '1px solid #3a6a3a',
  borderRadius: 10,
  padding: '8px 18px',
  color: '#86efac',
  fontSize: 13,
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  pointerEvents: 'none',
  backdropFilter: 'blur(4px)',
  whiteSpace: 'nowrap',
  zIndex: 10,
}
