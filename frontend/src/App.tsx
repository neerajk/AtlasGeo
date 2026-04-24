import { useState, useCallback } from 'react'
import { Globe } from './components/Globe'
import { ChatPanel } from './components/ChatPanel'
import { atlasSocket } from './api/atlas'
import type { CogLayer } from './types'

export default function App() {
  const [features, setFeatures] = useState<import('./types').GeoJsonFeature[]>([])
  const [cogLayers, setCogLayers] = useState<CogLayer[]>([])
  const [pickerMode, setPickerMode] = useState<{ taskType: string } | null>(null)

  const handleAddLayer = useCallback((layer: CogLayer) => {
    setCogLayers((prev) => {
      if (prev.some((l) => l.id === layer.id)) return prev
      return [...prev, layer]
    })
  }, [])

  const handleToggleLayer = useCallback((id: string) => {
    setCogLayers((prev) => prev.map((l) => (l.id === id ? { ...l, visible: !l.visible } : l)))
  }, [])

  const handleOpacityChange = useCallback((id: string, opacity: number) => {
    setCogLayers((prev) => prev.map((l) => (l.id === id ? { ...l, opacity } : l)))
  }, [])

  const handleRemoveLayer = useCallback((id: string) => {
    setCogLayers((prev) => prev.filter((l) => l.id !== id))
  }, [])

  const handleScenePicker = useCallback((taskType: string) => {
    setPickerMode({ taskType })
  }, [])

  const handleSceneSelected = useCallback((sceneId: string) => {
    if (!pickerMode) return
    setPickerMode(null)
    atlasSocket.send({ type: 'run_analysis', scene_id: sceneId, task_type: pickerMode.taskType })
  }, [pickerMode])

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw' }}>
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        <Globe
          features={features}
          cogLayers={cogLayers}
          pickerMode={pickerMode}
          onSceneSelect={handleSceneSelected}
          onAddLayer={handleAddLayer}
          onToggleLayer={handleToggleLayer}
          onOpacityChange={handleOpacityChange}
          onRemoveLayer={handleRemoveLayer}
        />
      </div>

      <div style={{ width: 420, flexShrink: 0, borderLeft: '1px solid #252540', overflow: 'hidden' }}>
        <ChatPanel
          onFeatures={setFeatures}
          onTifLayers={(layers) => layers.forEach(handleAddLayer)}
          pickerMode={!!pickerMode}
          onScenePicker={handleScenePicker}
          onPickerCancel={() => setPickerMode(null)}
        />
      </div>
    </div>
  )
}
