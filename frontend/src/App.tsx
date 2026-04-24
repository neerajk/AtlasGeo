import { useState, useCallback } from 'react'
import { Globe } from './components/Globe'
import { ChatPanel } from './components/ChatPanel'
import { LayerPanel } from './components/LayerPanel'
import type { GeoJsonFeature, CogLayer } from './types'

export default function App() {
  const [features, setFeatures] = useState<GeoJsonFeature[]>([])
  const [selectedFeature, setSelectedFeature] = useState<GeoJsonFeature | null>(null)
  const [cogLayers, setCogLayers] = useState<CogLayer[]>([])

  const handleAddLayer = useCallback((layer: CogLayer) => {
    setCogLayers((prev) => [...prev, layer])
  }, [])

  const handleToggleLayer = useCallback((id: string) => {
    setCogLayers((prev) =>
      prev.map((l) => (l.id === id ? { ...l, visible: !l.visible } : l))
    )
  }, [])

  const handleOpacityChange = useCallback((id: string, opacity: number) => {
    setCogLayers((prev) =>
      prev.map((l) => (l.id === id ? { ...l, opacity } : l))
    )
  }, [])

  const handleRemoveLayer = useCallback((id: string) => {
    setCogLayers((prev) => prev.filter((l) => l.id !== id))
  }, [])

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw' }}>
      <div style={{ flex: 1, position: 'relative' }}>
        <Globe
          features={features}
          cogLayers={cogLayers}
          onFeatureClick={setSelectedFeature}
        />
      </div>
      <div style={{ width: 420, flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <ChatPanel onFeatures={setFeatures} selectedFeature={selectedFeature} />
        </div>
        <LayerPanel
          feature={selectedFeature}
          layers={cogLayers}
          onAddLayer={handleAddLayer}
          onToggleLayer={handleToggleLayer}
          onOpacityChange={handleOpacityChange}
          onRemoveLayer={handleRemoveLayer}
        />
      </div>
    </div>
  )
}
