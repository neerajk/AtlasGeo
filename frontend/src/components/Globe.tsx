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
  onAddLayer:      (layer: CogLayer) => void
  onToggleLayer:   (id: string) => void
  onOpacityChange: (id: string, opacity: number) => void
  onRemoveLayer:   (id: string) => void
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

export function Globe({ features, cogLayers, onAddLayer, onToggleLayer, onOpacityChange, onRemoveLayer }: GlobeProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef       = useRef<maplibregl.Map | null>(null)
  const overlayRef   = useRef<MapboxOverlay | null>(null)
  const mapReadyRef  = useRef(false)

  const [selectedFeature, setSelectedFeature] = useState<GeoJsonFeature | null>(null)

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

  // Sync deck.gl footprint layer
  useEffect(() => {
    if (!overlayRef.current) return
    overlayRef.current.setProps({
      layers: [new GeoJsonLayer({
        id: 'stac-footprints',
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        data: { type: 'FeatureCollection' as const, features } as any,
        filled: true,
        stroked: true,
        getFillColor: [64, 160, 255, 35],
        getLineColor: [64, 160, 255, 220],
        getLineWidth: 2,
        lineWidthMinPixels: 1,
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 200, 64, 80],
        onClick: ({ object }) => {
          if (!object) return
          const feat = object as GeoJsonFeature
          setSelectedFeature((prev) =>
            prev?.properties.id === feat.properties.id ? null : feat
          )
        },
      })],
    })
  }, [features])

  // Fly to results (separate so it doesn't re-fire on inspectMode toggle)
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

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
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
