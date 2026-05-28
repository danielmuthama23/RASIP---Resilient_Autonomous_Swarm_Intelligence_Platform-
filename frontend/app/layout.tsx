import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { ReduxProvider } from '@/store/provider'
import { WebSocketProvider } from '@/services/websocket'
import { HederaProvider } from '@/services/hedera'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'RASIP — Swarm Command',
  description: 'Resilient Autonomous Swarm Intelligence Platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <ReduxProvider>
          <HederaProvider>
            <WebSocketProvider url={process.env.NEXT_PUBLIC_WS_URL}>
              <main className="min-h-screen bg-background">
                {children}
              </main>
            </WebSocketProvider>
          </HederaProvider>
        </ReduxProvider>
      </body>
    </html>
  )
}