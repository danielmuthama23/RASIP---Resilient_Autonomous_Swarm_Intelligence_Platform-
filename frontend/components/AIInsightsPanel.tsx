'use client'

import { useEffect, useState } from 'react'
import type { MissionState } from '@/types/swarm'

interface Insight {
  ts:    string
  msg:   string
  level: 'info' | 'warn' | 'alert'
}

export default function AIInsightsPanel({ mission }: { mission: MissionState }) {
  const [insights, setInsights] = useState<Insight[]>([])

  useEffect(() => {
    if (!mission.lastInsight) return
    setInsights(prev => [
      { ts: new Date().toLocaleTimeString(), ...mission.lastInsight },
      ...prev,
    ].slice(0, 50))
  }, [mission.lastInsight])

  // Severity → left-border colour
  const borderColor = (l: Insight['level']) =>
    l === 'alert' ? '#f38ba8'   // red
    : l === 'warn'  ? '#fab387'  // amber
    :                '#1fffb0'  // teal

  const textColor = (l: Insight['level']) =>
    l === 'alert' ? 'text-red-400'
    : l === 'warn'  ? 'text-yellow-400'
    :                'text-green-400'

  return (
    <div className="flex flex-col gap-1 max-h-48 overflow-y-auto font-mono text-xs">
      {insights.map((ins, i) => (
        <div
          key={i}
          className="flex gap-2 items-start border-l-2 pl-2"
          style={{ borderColor: borderColor(ins.level) }}
        >
          <span className="text-muted-foreground shrink-0">{ins.ts}</span>
          <span className={`${textColor(ins.level)}`}>{ins.msg}</span>
        </div>
      ))}
    </div>
  )
}