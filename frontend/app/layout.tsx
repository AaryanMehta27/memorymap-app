import type { Metadata } from 'next'
import type { ReactNode } from 'react'
import './globals.css'
import { Nav } from '@/components/Nav'

export const metadata: Metadata = {
  title: 'MemoryMap',
  description: 'Helping you remember where things are.',
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50" style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' }}>
        <Nav />
        {children}
      </body>
    </html>
  )
}
