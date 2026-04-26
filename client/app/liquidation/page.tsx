import type { Metadata } from 'next';
import { Suspense } from 'react';
import LiquidationClient from './LiquidationClient';

export const metadata: Metadata = {
  title: 'Liquidation Pressure Map | TRINITY CHIMERA',
  description: 'Real-time liquidation cascade detection & pressure zone visualization for Binance Futures',
};

export default function LiquidationPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', background: '#0a0a0c' }} />}>
      <LiquidationClient />
    </Suspense>
  );
}
