'use client'

import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import { updateDrones, updateMission } from '@/store/swarmSlice'
import type { DroneData, MissionState } from '@/types/swarm'

// ── Types ─────────────────────────────────────────────────
interface WsMessage {
  type:    'telemetry' | 'mission' | 'alert' | 'ping'
  drones?: DroneData[]
  mission?:MissionState
  alert?:  string
}

interface WsContext { status: 'connecting' | 'open' | 'closed' }

// ── Context ───────────────────────────────────────────────
const Ctx = createContext<WsContext>({ status: 'connecting' })
export const useWebSocket = () => useContext(Ctx)

// ── Provider ──────────────────────────────────────────────
export function WebSocketProvider({ url, children }: {
  url:      string
  children: React.ReactNode
}) {
  const dispatch   = useDispatch()
  const wsRef      = useRef<WebSocket | null>(null)
  const retryRef   = useRef<number>()
  const retryCount = useRef(0)
  const [status, setStatus] = useState<WsContext['status']>('connecting')

  useEffect(() => {
    function connect() {
      setStatus('connecting')
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.addEventListener('open', () => {
        setStatus('open')
        retryCount.current = 0
      })

      ws.addEventListener('message', e => {
        const msg = JSON.parse(e.data) as WsMessage
        if (msg.type === 'telemetry' && msg.drones) {
          dispatch(updateDrones(msg.drones))
        }
        if (msg.type === 'mission' && msg.mission) {
          dispatch(updateMission(msg.mission))
        }
        if (msg.type === 'ping') {
          ws.send(JSON.stringify({ type: 'pong' }))
        }
      })

      ws.addEventListener('close', () => {
        setStatus('closed')
        retryCount.current = Math.min(retryCount.current + 1, 5)
        const delay = Math.min(16_000, 1_000 * 2 ** retryCount.current)
        retryRef.current = window.setTimeout(connect, delay)
      })

      ws.addEventListener('error', () => ws.close())
    }

    connect()
    return () => {
      if (retryRef.current) window.clearTimeout(retryRef.current)
      wsRef.current?.close()
    }
  }, [url])

  return <Ctx.Provider value={{ status }}>{children}</Ctx.Provider>
}