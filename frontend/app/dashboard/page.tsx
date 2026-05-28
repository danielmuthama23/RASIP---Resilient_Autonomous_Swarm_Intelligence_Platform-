'use client'

import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import SwarmScene from '@/components/SwarmScene'
import TelemetryPanel from '@/components/TelemetryPanel'
import RadarPanel from '@/components/RadarPanel'
import AIInsightsPanel from '@/components/AIInsightsPanel'
import ATCConsole from '@/components/ATCConsole'
import { selectDrones, selectMission } from '@/store/swarmSlice'
import { useWebSocket } from '@/services/websocket'

export default function DashboardPage() {
  const drones  = useSelector(selectDrones)
  const mission = useSelector(selectMission)
  const { status } = useWebSocket()
  const [activeTab, setActiveTab] = useState('swarm')

  return (
    <div className="flex h-screen bg-background text-foreground">

      {/* ── Left panel: boid canvas + radar ────────────── */}
      <section className="flex-1 flex flex-col">
        <SwarmScene drones={drones} formation={mission.formation} />
        <RadarPanel drones={drones} />
      </section>

      {/* ── Right panel: telemetry + AI insights ───────── */}
      <aside className="w-80 border-l flex flex-col gap-4 p-4 overflow-y-auto">
        <TelemetryPanel drones={drones} wsStatus={status} />
        <AIInsightsPanel mission={mission} />
        <ATCConsole />
      </aside>
    </div>
  )
}