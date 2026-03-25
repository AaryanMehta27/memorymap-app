import type { Metadata } from 'next'
import { Geist } from 'next/font/google'
import { cn } from '@/lib/utils'
import './globals.css'
import { Nav } from '@/components/Nav'

const geist = Geist({ subsets: ['latin'], variable: '--font-sans' })

export const metadata: Metadata = {
  title: 'MemoryMap',
  description: 'Helping you remember where things are.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={cn('font-sans', geist.variable)}>
      <body className="min-h-screen bg-gray-50">
        <Nav />
        {children}
      </body>
    </html>
  )
}
