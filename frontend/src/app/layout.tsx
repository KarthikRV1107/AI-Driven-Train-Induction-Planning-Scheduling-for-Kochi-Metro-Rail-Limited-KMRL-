import type { Metadata } from 'next'
import AppChrome from '@/components/layout/AppChrome'
import './globals.css'

export const metadata: Metadata = {
  title: 'KMRL NexusAI - Train Induction Platform',
  description: 'AI-Driven Train Induction Planning & Scheduling System - Kochi Metro Rail Limited',
  icons: { icon: '/favicon.ico' },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppChrome>{children}</AppChrome>
      </body>
    </html>
  )
}
