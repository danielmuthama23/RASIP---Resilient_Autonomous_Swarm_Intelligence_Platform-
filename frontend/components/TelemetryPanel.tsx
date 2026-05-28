'use client'

import { useMemo } from 'react'
import type { DroneData } from '@/types/swarm'

interface Props { drones: DroneData[]; wsStatus: string }

export default function TelemetryPanel({ drones, wsStatus }: Props) {
  const avg = useMemo(() => {
    const count = Math.max(1, drones.length)
    return {
      battery: drones.reduce((s, d) => s + d.battery, 0) / count,
      signal:  drones.reduce((s, d) => s + d.signal,  0) / count,
      aiConf:  drones.reduce((s, d) => s + d.ai_conf, 0) / count,
    }
  }, [drones])

  return (
    <div className="flex flex-col gap-3">

      {/* WebSocket status badge */}
      <div className="flex items-center gap-2 text-xs">
        <span className={`w-2 h-2 rounded-full ${
          wsStatus === 'open' ? 'bg-green-400' : 'bg-red-400'}`} />
        {wsStatus === 'open' ? 'Swarm online' : 'Reconnecting…'}
      </div>

      {/* Fleet average metric cards */}
      {([
        ['Avg battery',    avg.battery, '%'],
        ['Avg signal',     avg.signal,  '%'],
        ['AI confidence', avg.aiConf,  '%'],
      ] as const).map(([label, value, unit]) => (
        <div key={label} className="bg-secondary rounded-lg p-3">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-2xl font-medium mt-1">
            {Math.round(value)}{unit}
          </p>
        </div>
      ))}

      {/* Per-drone row list */}
      {drones.map(d => (
        <div key={d.id} className="text-xs flex justify-between border-b pb-1">
          <span className="font-medium">{d.id}</span>
          <span>🔋{d.battery}% · 📡{d.signal}%</span>
        </div>
      ))}
    </div>
  )
}