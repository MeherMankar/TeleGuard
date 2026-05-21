/**
 * WebSocket client for TeleGuard real-time events.
 * Connects to /ws/events?token=<jwt> and dispatches typed events.
 */

const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8080"

export type WsEventType =
  | "session_revoked"
  | "account_added"
  | "new_message"
  | "security_alert"
  | "automation_log"

export interface WsEvent {
  type: WsEventType
  [key: string]: unknown
}

type Listener = (event: WsEvent) => void

class TeleGuardSocket {
  private ws: WebSocket | null = null
  private listeners: Map<WsEventType | "*", Set<Listener>> = new Map()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectDelay = 2000
  private maxDelay = 30000
  private shouldConnect = false

  connect(token: string) {
    this.shouldConnect = true
    this._open(token)
  }

  disconnect() {
    this.shouldConnect = false
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  on(event: WsEventType | "*", listener: Listener) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set())
    }
    this.listeners.get(event)!.add(listener)
    return () => this.off(event, listener)
  }

  off(event: WsEventType | "*", listener: Listener) {
    this.listeners.get(event)?.delete(listener)
  }

  private _open(token: string) {
    if (typeof WebSocket === "undefined") return
    if (this.ws) {
      this.ws.close()
    }

    const url = `${WS_URL}/ws/events?token=${encodeURIComponent(token)}`
    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      this.reconnectDelay = 2000
      // Start ping interval
      const ping = setInterval(() => {
        if (this.ws?.readyState === WebSocket.OPEN) {
          this.ws.send("ping")
        } else {
          clearInterval(ping)
        }
      }, 25000)
    }

    this.ws.onmessage = (e) => {
      if (e.data === "pong") return
      try {
        const event: WsEvent = JSON.parse(e.data)
        this._dispatch(event)
      } catch {
        // ignore malformed messages
      }
    }

    this.ws.onclose = () => {
      if (!this.shouldConnect) return
      this.reconnectTimer = setTimeout(() => {
        this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, this.maxDelay)
        this._open(token)
      }, this.reconnectDelay)
    }

    this.ws.onerror = () => {
      this.ws?.close()
    }
  }

  private _dispatch(event: WsEvent) {
    this.listeners.get(event.type as WsEventType)?.forEach((l) => l(event))
    this.listeners.get("*")?.forEach((l) => l(event))
  }
}

export const socket = new TeleGuardSocket()
