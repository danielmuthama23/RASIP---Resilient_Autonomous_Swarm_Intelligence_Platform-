'use client'

import { useEffect, useRef } from 'react'

// droneId selects which RTSP stream from the backend bridge
export default function CameraFeed({ droneId }: { droneId: string }) {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const pc = new RTCPeerConnection({ iceServers: [] })

    // Pipe incoming video track straight to the element
    pc.addEventListener('track', e => {
      if (videoRef.current)
        videoRef.current.srcObject = e.streams[0]
    })

    async function connect() {
      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)

      // POST SDP offer; receive answer from backend WebRTC bridge
      const res = await fetch(`/api/webrtc/${droneId}`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ sdp: offer }),
      })
      const { answer } = await res.json()
      await pc.setRemoteDescription(answer)
    }

    connect()
    return () => pc.close()
  }, [droneId])

  return (
    <div className="relative w-full aspect-video bg-black rounded-lg overflow-hidden">
      <video
        ref={videoRef}
        autoPlay muted playsInline
        className="w-full h-full object-cover"
      />
      <span className="absolute top-2 left-2 text-xs bg-black/60 px-2 py-0.5 rounded font-mono text-green-400">
        LIVE · {droneId}
      </span>
    </div>
  )
}