'use client'

import { Canvas } from '@react-three/fiber'
import { OrbitControls, Environment } from '@react-three/drei'
import { Suspense } from 'react'
import { useSelector } from 'react-redux'
import SwarmScene3D from '@/components/SwarmScene'
import MapView from '@/components/MapView'
import CameraFeed from '@/components/CameraFeed'
import AnalyticsChart from '@/components/AnalyticsChart'
import { selectDrones } from '@/store/swarmSlice'

export default function DigitalTwinPage() {
  const drones = useSelector(selectDrones)

  return (
    <div className="grid grid-cols-2 grid-rows-2 h-screen">

      {/* ── Quadrant 1: 3D boid simulation ─────────────── */}
      <Canvas camera={{ position: [0, 40, 80], fov: 60 }}>
        <Suspense fallback={null}>
          <ambientLight intensity={0.6} />
          <SwarmScene3D drones={drones} />
          <Environment preset="night" />
          <OrbitControls enablePan enableZoom />
        </Suspense>
      </Canvas>

      {/* ── Quadrant 2: Mapbox geospatial view ─────────── */}
      <MapView drones={drones} token={process.env.NEXT_PUBLIC_MAPBOX_TOKEN} />

      {/* ── Quadrant 3: Live RTSP camera feed ──────────── */}
      <CameraFeed droneId="DR-01" />

      {/* ── Quadrant 4: Battery + signal analytics ─────── */}
      <AnalyticsChart drones={drones} />
    </div>
  )
}