'use client'

import { useEffect, useRef } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import type { DroneData } from '@/types/swarm'

export default function MapView({
  drones, token
}: { drones: DroneData[]; token: string }) {
  const mapRef       = useRef<mapboxgl.Map>(null)
  const markersRef   = useRef<Map<string, mapboxgl.Marker>>(new Map())
  const containerRef = useRef<HTMLDivElement>(null)

  // Init Mapbox GL map once on mount
  useEffect(() => {
    mapboxgl.accessToken = token
    mapRef.current = new mapboxgl.Map({
      container: containerRef.current!,
      style:  'mapbox://styles/mapbox/dark-v11',
      center: [36.8219, -1.2921],  // Nairobi
      zoom:   12,
    })
    return () => mapRef.current?.remove()
  }, [])

  // Reactively add or reposition a marker per drone
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    drones.forEach(d => {
      if (markersRef.current.has(d.id)) {
        markersRef.current.get(d.id)!.setLngLat([d.lon, d.lat])
      } else {
        const el = document.createElement('div')
        el.className = 'drone-marker'
        const m = new mapboxgl.Marker({ element: el })
          .setLngLat([d.lon, d.lat])
          .setPopup(new mapboxgl.Popup().setHTML(
            `<b>${d.id}</b> · 🔋${d.battery}%`
          ))
          .addTo(map)
        markersRef.current.set(d.id, m)
      }
    })
  }, [drones])

  return <div ref={containerRef} className="w-full h-full" />
}