import { useEffect } from "react"
import { socket, type WsEvent, type WsEventType } from "@/lib/socket"

export function useWsEvent(event: WsEventType | "*", handler: (e: WsEvent) => void) {
  useEffect(() => {
    return socket.on(event, handler)
  }, [event, handler])
}
