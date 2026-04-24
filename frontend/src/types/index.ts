export interface GeoJsonFeature {
  type: 'Feature'
  id: string
  geometry: {
    type: string
    coordinates: unknown
  }
  properties: {
    id: string
    datetime: string | null
    cloud_cover: number | null
    platform: string
    thumbnail: string | null
    download_links: Record<string, string>
  }
}

export type WsMessageType = 'thinking' | 'geojson' | 'message' | 'error' | 'done'

export interface WsMessage {
  type: WsMessageType
  message?: string   // thinking | error
  content?: string   // message (markdown)
  features?: GeoJsonFeature[]  // geojson
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  isThinking?: boolean
}
