'use client'

import { useRef, useEffect } from 'react'
import type { DroneData } from '@/types/swarm'

const R  = 120           // sweep radius px
const CX = 140, CY = 140  // canvas centre

export default function RadarPanel({ drones }: { drones: DroneData[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const sweepRef  = useRef(0)

  useEffect(() => {
    const ctx = canvasRef.current?.getContext('2d')
    if (!ctx) return
    let raf: number

    function draw() {
      ctx.clearRect(0, 0, 280, 280)

      // Three concentric grid rings
      ctx.strokeStyle = '#1fffb030'
      ;[1, 2, 3].forEach(r => {
        ctx.beginPath()
        ctx.arc(CX, CY, R * r / 3, 0, Math.PI * 2)
        ctx.stroke()
      })

      // Rotating sweep line
      sweepRef.current = (sweepRef.current + 0.02) % (Math.PI * 2)
      ctx.strokeStyle = '#1fffb0'
      ctx.beginPath()
      ctx.moveTo(CX, CY)
      ctx.lineTo(
        CX + R * Math.cos(sweepRef.current),
        CY + R * Math.sin(sweepRef.current),
      )
      ctx.stroke()

      // Drone blips — red if alert, teal otherwise
      drones.forEach(d => {
        ctx.fillStyle = d.alert ? '#f38ba8' : '#1fffb0'
        ctx.beginPath()
        ctx.arc(
          CX + (d.x / 500) * R,
          CY + (d.y / 500) * R,
          3, 0, Math.PI * 2
        )
        ctx.fill()
      })

      raf = requestAnimationFrame(draw)
    }

    raf = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [drones])

  return (
    <canvas
      ref={canvasRef}
      width={280} height={280}
      className="rounded-lg"
    />
  )
}