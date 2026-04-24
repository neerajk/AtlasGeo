import type { WsMessage } from '../types'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/chat'

type MessageHandler = (msg: WsMessage) => void

export class AtlasSocket {
  private ws: WebSocket | null = null
  private handlers: Set<MessageHandler> = new Set()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return

    this.ws = new WebSocket(WS_URL)

    this.ws.onmessage = (ev) => {
      try {
        const msg: WsMessage = JSON.parse(ev.data)
        this.handlers.forEach((h) => h(msg))
      } catch {
        // ignore malformed frames
      }
    }

    this.ws.onclose = () => {
      this.reconnectTimer = setTimeout(() => this.connect(), 2000)
    }

    this.ws.onerror = () => {
      this.ws?.close()
    }
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.ws?.close()
  }

  send(query: string) {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      this.connect()
      this.ws!.addEventListener('open', () => this._send(query), { once: true })
    } else {
      this._send(query)
    }
  }

  private _send(query: string) {
    this.ws?.send(JSON.stringify({ query }))
  }

  onMessage(handler: MessageHandler) {
    this.handlers.add(handler)
    return () => this.handlers.delete(handler)
  }
}

export const atlasSocket = new AtlasSocket()
