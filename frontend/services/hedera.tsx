'use client'

// Hedera-inspired SHA-256 TX integrity check
// Verifies each telemetry payload hash against the identity ledger

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

// ── Types ─────────────────────────────────────────────────
export interface HederaTx {
  txId:      string
  droneId:   string
  hash:      string   // SHA-256 hex of payload
  timestamp: string
  valid:     boolean
}

export interface VerifyResult {
  match:    boolean
  expected: string
  received: string
}

// ── Context provider (wraps app) ──────────────────────────
import { createContext, useContext } from 'react'

interface HederaCtx {
  getHashes:  () => Promise<HederaTx[]>
  verifyHash: (droneId: string, payload: unknown) => Promise<VerifyResult>
}

const Ctx = createContext<HederaCtx>(null!)
export const useHedera = () => useContext(Ctx)

// ── API calls ─────────────────────────────────────────────

async function getHashes(): Promise<HederaTx[]> {
  const res = await fetch(`${API}/hashes`)
  if (!res.ok) throw new Error('Failed to fetch Hedera hashes')
  return res.json()
}

async function verifyHash(droneId: string, payload: unknown): Promise<VerifyResult> {
  const res = await fetch(`${API}/verify`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ droneId, payload }),
  })
  if (!res.ok) throw new Error('Verification request failed')
  return res.json()
}

// ── Provider ──────────────────────────────────────────────
export function HederaProvider({ children }: { children: React.ReactNode }) {
  return (
    <Ctx.Provider value={{ getHashes, verifyHash }}>
      {children}
    </Ctx.Provider>
  )
}
