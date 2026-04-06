/**
 * TRINITY-CHIMERY Dashboard - Root Layout
 * Next.js App Router 기반 루트 레이아웃
 */

import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'TRINITY-CHIMERY | AI Trading Dashboard',
  description: 'Real-time AI trading agent monitoring and portfolio management',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" className="dark">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased dark:bg-gray-900 dark:text-gray-100">
        {children}
      </body>
    </html>
  );
}
