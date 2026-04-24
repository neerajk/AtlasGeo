import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import { MapboxOverlay } from '@deck.gl/mapbox'
import { GeoJsonLayer } from '@deck.gl/layers'
import type { GeoJsonFeature } from '../types'

import 'maplibre-gl/dist/maplibre-gl.css'

interface GlobeProps {
  features: GeoJsonFeature[]
  onFeatureClick?: (feature: GeoJsonFeature) => void
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

export function Globe({ features, onFeatureClick }: GlobeProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const overlayRef = useRef<MapboxOverlay | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: FREE_STYLE,
      center: [0, 20],
      zoom: 2,
      attributionControl: true,
    })

    map.addControl(new maplibregl.NavigationControl(), 'top-right')

    const overlay = new MapboxOverlay({ layers: [] })
    map.addControl(overlay as unknown as maplibregl.IControl)

    mapRef.current = map
    overlayRef.current = overlay

    return () => {
      overlay.finalize()
      map.remove()
    }
  }, [])

  useEffect(() => {
    if (!overlayRef.current) return

    const layer = new GeoJsonLayer({
      id: 'stac-footprints',
      data: { type: 'FeatureCollection', features },
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
        if (object && onFeatureClick) onFeatureClick(object as GeoJsonFeature)
      },
    })

    overlayRef.current.setProps({ layers: [layer] })

    // Fly to results
    if (features.length > 0) {
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
    }
  }, [features, onFeatureClick])

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
}
