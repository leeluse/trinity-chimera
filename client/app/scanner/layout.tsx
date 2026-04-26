import type { Metadata, Viewport } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import { Analytics } from '@vercel/analytics/next'

const inter = Inter({
  subsets: ["latin"],
  variable: '--font-inter',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: '--font-mono',
});

export const metadata: Metadata = {
  title: '나혼자 스캐너 · Solo Scanner',
  description: 'Real-time Binance Futures momentum scanner with sector rotation analysis',
}

export const viewport: Viewport = {
  themeColor: '#0a0a0f',
}

export default function ScannerLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <div className={`${inter.variable} ${jetbrainsMono.variable} font-sans antialiased min-h-[100dvh] bg-background overflow-y-auto`}>
      {children}
      {process.env.NODE_ENV === 'production' && <Analytics />}
    </div>
  )
}
