import { useEffect, useRef, useState, useCallback } from 'react'

/**
 * Kết nối WebSocket tới /ws/visits/{visitId}.
 * Tự động reconnect khi mất kết nối (mạng công trình thường chập chờn).
 * Trả về: connectionStatus, lastEvent, sendPing
 */
export function useVisitSocket(visitId) {
  const [connectionStatus, setConnectionStatus] = useState('connecting') // connecting | connected | disconnected
  const [lastEvent, setLastEvent] = useState(null)
  const wsRef = useRef(null)
  const reconnectTimerRef = useRef(null)
  const reconnectAttemptRef = useRef(0)

  const connect = useCallback(() => {
    if (!visitId) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/visits/${visitId}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnectionStatus('connected')
      reconnectAttemptRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'heartbeat' || data.type === 'pong') return
        setLastEvent(data)
      } catch {
        // ignore malformed message
      }
    }

    ws.onclose = () => {
      setConnectionStatus('disconnected')
      // Exponential backoff, tối đa 10s — phù hợp mạng công trình chập chờn
      const delay = Math.min(1000 * 2 ** reconnectAttemptRef.current, 10000)
      reconnectAttemptRef.current += 1
      reconnectTimerRef.current = setTimeout(connect, delay)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [visitId])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  // Ping định kỳ để giữ kết nối sống qua Nginx/Cloudflare proxy
  useEffect(() => {
    const interval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }))
      }
    }, 25000)
    return () => clearInterval(interval)
  }, [])

  return { connectionStatus, lastEvent }
}
