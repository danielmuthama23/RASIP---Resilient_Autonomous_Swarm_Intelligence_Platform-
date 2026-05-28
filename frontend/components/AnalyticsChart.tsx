'use client'

import {
  LineChart, Line, XAxis, YAxis,
  Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import { useMemo } from 'react'
import type { DroneData } from '@/types/swarm'

const COLORS = [
  '#1fffb0', '#89b4fa', '#fab387', '#f38ba8', '#cba6f7'
]

export default function AnalyticsChart({ drones }: { drones: DroneData[] }) {

  // Flatten per-drone history into recharts data array
  const data = useMemo(() =>
    drones[0]?.history?.map((_, tick) => ({
      tick,
      ...Object.fromEntries(
        drones.map(d => [d.id, d.history[tick]?.battery ?? null])
      ),
    })) ?? []
  , [drones])

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <XAxis dataKey="tick" tick={{ fontSize: 11 }} />
        <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v: number) => `${Math.round(v)}%`} />
        <Legend />
        {drones.slice(0, 5).map((d, i) => (
          <Line
            key={d.id}
            type="monotone"
            dataKey={d.id}
            dot={false}
            strokeWidth={1.5}
            stroke={COLORS[i]}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}