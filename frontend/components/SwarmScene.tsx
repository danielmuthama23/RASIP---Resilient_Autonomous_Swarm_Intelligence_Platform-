'use client'

import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { InstancedMesh, Object3D } from 'three'
import type { DroneData } from '@/types/swarm'

interface Props {
  drones:    DroneData[]
  formation?: string
}

// Single instanced mesh — one GPU draw call for the whole swarm
export default function SwarmScene({ drones, formation }: Props) {
  const meshRef = useRef<InstancedMesh>(null)
  const dummy   = useRef(new Object3D())

  useFrame(() => {
    drones.forEach((d, i) => {
      dummy.current.position.set(d.x, d.altitude, d.y)
      dummy.current.rotation.y = d.heading
      dummy.current.updateMatrix()
      meshRef.current?.setMatrixAt(i, dummy.current.matrix)
    })
    if (meshRef.current)
      meshRef.current.instanceMatrix.needsUpdate = true
  })

  return (
    <instancedMesh
      ref={meshRef}
      args={[undefined, undefined, 20]}
    >
      <coneGeometry args={[0.6, 2, 4]} />
      <meshStandardMaterial
        color="#1fffb0"
        emissive="#00ff88"
        emissiveIntensity={0.4}
      />
    </instancedMesh>
  )
}