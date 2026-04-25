import { useState, useEffect, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import { atlasSocket } from '../api/atlas'
import type { ChatMessage, CogLayer, GeoJsonFeature, TifLayerMsg, WsMessage } from '../types'

interface Step {
  text: string
  done: boolean
}

const TITILER_URL = import.meta.env.VITE_TITILER_URL ?? 'http://localhost:8001'
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

function resolveTifLayer(msg: TifLayerMsg): CogLayer {
  return {
    id: msg.id,
    name: msg.name,
    sceneId: msg.sceneId,
    band: msg.band,
    tileUrl: msg.tileUrl
      .replace('{TITILER_URL}', TITILER_URL)
      .replace('{BACKEND_URL}', encodeURIComponent(BACKEND_URL)),
    visible: msg.visible,
    opacity: msg.opacity,
  }
}

const TASK_LABELS: Record<string, string> = {
  ndvi: 'NDVI vegetation analysis',
  ndwi: 'NDWI water index analysis',
  ndbi: 'NDBI built-up analysis',
  flood_mapping: 'flood mapping',
  burn_scar: 'burn scar mapping',
}

interface ChatPanelProps {
  onFeatures: (features: GeoJsonFeature[]) => void
  onTifLayers: (layers: CogLayer[]) => void
  pickerMode: boolean
  onScenePicker: (taskType: string) => void
  onPickerCancel: () => void
}

let msgCounter = 0
const uid = () => String(++msgCounter)

const EXAMPLES = [
  'Show Sentinel-2 images over Nairobi, Kenya from last month',
  'Find clear scenes over the Amazon rainforest with less than 5% cloud cover',
  'NDBI analysis over Mumbai, India in March 2024',
]

export function ChatPanel({ onFeatures, onTifLayers, pickerMode, onScenePicker, onPickerCancel }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [steps, setSteps] = useState<Step[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    atlasSocket.connect()
    const unsub = atlasSocket.onMessage(handleWsMessage)
    const unsubReconnect = atlasSocket.onReconnect(() => {
      setBusy(false)
      setSteps([])
      if (pickerMode) {
        onPickerCancel()
        setMessages(prev => [
          ...prev,
          { id: uid(), role: 'assistant', content: '⚠️ Connection lost during scene selection — please re-run your query.' },
        ])
      }
    })
    return () => { unsub(); unsubReconnect() }
  }, [pickerMode, onPickerCancel])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, steps])

  const handleWsMessage = useCallback((msg: WsMessage) => {
    switch (msg.type) {
      case 'thinking':
        setSteps(prev => [
          ...prev.map(s => ({ ...s, done: true })),
          { text: msg.message || '', done: false },
        ])
        break

      case 'geojson':
        if (msg.features) onFeatures(msg.features)
        break

      case 'tif_layers':
        if (msg.tif_layers?.length) {
          onTifLayers(msg.tif_layers.map(resolveTifLayer))
        }
        break

      case 'scene_picker': {
        const taskType = msg.task_type || 'analysis'
        const label = TASK_LABELS[taskType] || taskType
        const n = msg.scene_count ?? 0
        setSteps([])
        setMessages(prev => [
          ...prev,
          {
            id: uid(),
            role: 'assistant',
            content: `Found **${n} scene${n !== 1 ? 's' : ''}**. Click a scene on the map to run **${label}**.`,
          },
        ])
        onScenePicker(taskType)
        setBusy(false)
        break
      }

      case 'message':
        setSteps([])
        setMessages(prev => [
          ...prev,
          { id: uid(), role: 'assistant', content: msg.content || '' },
        ])
        break

      case 'error':
        setSteps([])
        setMessages(prev => [
          ...prev,
          { id: uid(), role: 'assistant', content: `⚠️ ${msg.message}` },
        ])
        setBusy(false)
        break

      case 'done':
        setSteps([])
        setBusy(false)
        break
    }
  }, [onFeatures, onTifLayers, onScenePicker])

  const send = useCallback(() => {
    const q = input.trim()
    if (!q || busy || pickerMode || steps.length > 0) return
    setInput('')
    setBusy(true)
    setSteps([])
    atlasSocket.send({
      query: q,
      history: messages.map(m => ({ role: m.role, content: m.content })),
    })
    setMessages(prev => [...prev, { id: uid(), role: 'user', content: q }])
  }, [input, busy, pickerMode, steps, messages])

  const isDisabled = busy || pickerMode || steps.length > 0

  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <span style={styles.logo}>🌍 Atlas GeoAI</span>
        <span style={styles.subtitle}>Natural Language Satellite Search</span>
      </div>

      <div style={styles.messages}>
        {messages.length === 0 && steps.length === 0 && (
          <div style={styles.empty}>
            <p style={styles.emptyTitle}>Ask about satellite imagery</p>
            {EXAMPLES.map(ex => (
              <button key={ex} style={styles.example} onClick={() => setInput(ex)}>
                {ex}
              </button>
            ))}
          </div>
        )}

        {messages.map(m => (
          <div
            key={m.id}
            style={{ ...styles.msg, ...(m.role === 'user' ? styles.userMsg : styles.botMsg) }}
          >
            <ReactMarkdown>{m.content}</ReactMarkdown>
          </div>
        ))}

        {steps.length > 0 && (
          <div style={styles.stepsBox}>
            {steps.map((step, i) => (
              <div key={i} style={styles.stepRow}>
                {step.done ? (
                  <span style={styles.stepDoneIcon}>✓</span>
                ) : (
                  <span className="atlas-spinner" />
                )}
                <span
                  className={step.done ? '' : 'atlas-step-active'}
                  style={{ ...styles.stepText, ...(step.done ? styles.stepDoneText : styles.stepActiveText) }}
                >
                  {step.text}
                </span>
              </div>
            ))}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {pickerMode ? (
        <div style={styles.pickerBar}>
          <span style={styles.pickerText}>Click a scene on the map to run analysis</span>
          <button style={styles.cancelBtn} onClick={onPickerCancel}>Cancel</button>
        </div>
      ) : (
        <div style={styles.inputRow}>
          <input
            style={{ ...styles.input, opacity: isDisabled ? 0.65 : 1 }}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
            placeholder={busy ? 'Processing…' : 'Ask about satellite imagery…'}
            disabled={isDisabled}
          />
          <button
            style={{ ...styles.sendBtn, opacity: isDisabled ? 0.45 : 1, cursor: isDisabled ? 'not-allowed' : 'pointer' }}
            onClick={send}
            disabled={isDisabled}
          >
            {busy ? <span className="atlas-spinner" style={{ borderColor: '#1a3a5f', borderTopColor: '#fff' }} /> : '→'}
          </button>
        </div>
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  panel:          { display: 'flex', flexDirection: 'column', height: '100%', background: '#13131a', borderLeft: '1px solid #2a2a3a' },
  header:         { padding: '16px', borderBottom: '1px solid #2a2a3a' },
  logo:           { fontWeight: 700, fontSize: 16 },
  subtitle:       { display: 'block', fontSize: 12, color: '#64748b', marginTop: 2 },
  messages:       { flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: 12 },
  empty:          { display: 'flex', flexDirection: 'column', gap: 8, marginTop: 24 },
  emptyTitle:     { color: '#64748b', fontSize: 14, marginBottom: 8 },
  example:        { background: '#1e1e2e', border: '1px solid #2a2a3a', borderRadius: 8, padding: '8px 12px', color: '#94a3b8', fontSize: 13, textAlign: 'left', cursor: 'pointer' },
  msg:            { padding: '10px 14px', borderRadius: 10, fontSize: 14, lineHeight: 1.6, maxWidth: '100%' },
  userMsg:        { background: '#1e3a5f', alignSelf: 'flex-end', color: '#e2e8f0' },
  botMsg:         { background: '#1e1e2e', alignSelf: 'flex-start', color: '#cbd5e1' },
  stepsBox:       { background: '#16202e', border: '1px solid #1e3a5f', borderRadius: 10, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8, alignSelf: 'flex-start', minWidth: 220 },
  stepRow:        { display: 'flex', alignItems: 'center', gap: 8 },
  stepDoneIcon:   { fontSize: 12, color: '#22c55e', width: 14, textAlign: 'center', flexShrink: 0 },
  stepText:       { fontSize: 13, lineHeight: 1.4 },
  stepDoneText:   { color: '#475569' },
  stepActiveText: { color: '#94c4ff' },
  inputRow:       { padding: 12, borderTop: '1px solid #2a2a3a', display: 'flex', gap: 8, alignItems: 'center' },
  input:          { flex: 1, background: '#1e1e2e', border: '1px solid #2a2a3a', borderRadius: 8, padding: '10px 14px', color: '#e2e8f0', fontSize: 14, outline: 'none' },
  sendBtn:        { background: '#40a0ff', border: 'none', borderRadius: 8, padding: '0 18px', height: 40, color: '#fff', fontSize: 16, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', minWidth: 44 },
  pickerBar:      { padding: '12px 16px', borderTop: '1px solid #2a2a3a', background: '#1a2a1a', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  pickerText:     { fontSize: 13, color: '#86efac', flex: 1 },
  cancelBtn:      { background: 'transparent', border: '1px solid #475569', borderRadius: 6, padding: '4px 12px', color: '#94a3b8', fontSize: 12, cursor: 'pointer' },
}
