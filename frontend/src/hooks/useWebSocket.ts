import { useCallback, useEffect, useRef, useState } from "react";
import type { WSEvent } from "../types";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws";
const RECONNECT_DELAY = 3000;

export function useWebSocket(onEvent?: (event: WSEvent) => void) {
  const [connected, setConnected] = useState(false);
  const [clientId, setClientId] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);

    ws.onmessage = (e) => {
      try {
        const event: WSEvent = JSON.parse(e.data);
        if (event.event === "connected") {
          setClientId(event.data.client_id as string);
        } else if (event.event === "ping") {
          ws.send(JSON.stringify({ event: "pong" }));
        }
        onEvent?.(event);
      } catch {}
    };

    ws.onclose = () => {
      setConnected(false);
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
    };

    ws.onerror = () => ws.close();
  }, [onEvent]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((event: string, data: Record<string, unknown>) => {
    wsRef.current?.send(JSON.stringify({ event, data }));
  }, []);

  return { connected, clientId, send };
}
