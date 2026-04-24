import { useState } from 'react'
import { Globe } from './components/Globe'
import { ChatPanel } from './components/ChatPanel'
import type { GeoJsonFeature } from './types'

export default function App() {
  const [features, setFeatures] = useState<GeoJsonFeature[]>([])
  const [selectedFeature, setSelectedFeature] = useState<GeoJsonFeature | null>(null)

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw' }}>
      <div style={{ flex: 1, position: 'relative' }}>
        <Globe features={features} onFeatureClick={setSelectedFeature} />
      </div>
      <div style={{ width: 420, flexShrink: 0 }}>
        <ChatPanel onFeatures={setFeatures} selectedFeature={selectedFeature} />
      </div>
    </div>
  )
}
