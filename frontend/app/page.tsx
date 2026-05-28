// Root redirect → /dashboard
import { redirect } from 'next/navigation'

export default function Home() {
  redirect('/dashboard')
}

// ─── Metadata ──────────────────────────────────────
export const metadata = {
  title: 'RASIP',
  robots: { index: false },
}