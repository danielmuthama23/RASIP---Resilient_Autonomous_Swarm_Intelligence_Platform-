'use client'

import { useState } from 'react'
import { useDispatch } from 'react-redux'
import { setFormation, issueCommand } from '@/store/swarmSlice'

const FORMATIONS = [
  'V-WING', 'CIRCLE', 'GRID', 'DIAMOND', 'SEARCH'
] as const

export default function ATCConsole() {
  const dispatch        = useDispatch()
  const [cmd, setCmd]   = useState('')
  const [log, setLog]   = useState<string[]>([])

  const send = () => {
    if (!cmd.trim()) return
    dispatch(issueCommand(cmd))
    setLog(l => [`> ${cmd}`, ...l].slice(0, 20))
    setCmd('')
  }

  return (
    <div className="flex flex-col gap-2">

      {/* Formation quick-select */}
      <div className="flex gap-1 flex-wrap">
        {FORMATIONS.map(f => (
          <button
            key={f}
            onClick={() => dispatch(setFormation(f))}
            className="text-xs px-2 py-1 rounded border"
          >{f}</button>
        ))}
      </div>

      {/* Free-text command input */}
      <div className="flex gap-2">
        <input
          value={cmd}
          onChange={e => setCmd(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          placeholder="Enter command…"
          className="flex-1 font-mono text-xs"
        />
        <button onClick={send}>TX</button>
      </div>

      {/* Scrollable command log */}
      <div className="font-mono text-xs text-muted-foreground max-h-28 overflow-y-auto">
        {log.map((l, i) => <p key={i}>{l}</p>)}
      </div>
    </div>
  )
}