"use client";

import { useState, useEffect, useRef } from "react";
import { MarketGlobal } from "@/app/scanner/types";

const POLL_MS = 5 * 60 * 1000;

async function jFetch(url: string): Promise<unknown> {
  const r = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!r.ok) throw new Error(`API error: ${r.status}`);
  return r.json();
}

function fearGreedLabel(v: number): string {
  if (v <= 15) return "극단 공포";
  if (v <= 30) return "공포";
  if (v <= 45) return "다소 공포";
  if (v <= 55) return "중립";
  if (v <= 70) return "탐욕";
  if (v <= 85) return "과탐욕";
  return "극단 탐욕";
}

const INITIAL: MarketGlobal = {
  fearGreed: null,
  fearGreedLabel: "—",
  usdKrw: null,
  btcKrwKimchi: null,
  btcTx: null,
  btcTxLabel: "—",
  mempoolFee: null,
  mempoolFeeLabel: "—",
};

export function useMarketGlobal() {
  const [data, setData] = useState<MarketGlobal>(INITIAL);
  const btcBinancePrice = useRef<number>(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const [fgR, krwR, btcR, feeR, bithR, bnBtcR] = await Promise.allSettled([
        jFetch("https://api.alternative.me/fng/?limit=1"),
        jFetch("https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=krw"),
        jFetch("https://api.blockchain.info/stats"),
        jFetch("https://mempool.space/api/v1/fees/recommended"),
        jFetch("https://api.bithumb.com/public/ticker/BTC_KRW"),
        jFetch("https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT"),
      ]);

      if (cancelled) return;

      const next: MarketGlobal = { ...INITIAL };

      if (fgR.status === "fulfilled") {
        const v = parseInt((fgR.value as any)?.data?.[0]?.value ?? "50");
        next.fearGreed = v;
        next.fearGreedLabel = fearGreedLabel(v);
      }

      let usdKrwRate = 1350;
      if (krwR.status === "fulfilled") {
        const rate = (krwR.value as any)?.tether?.krw ?? 1350;
        usdKrwRate = rate;
        next.usdKrw = Math.round(rate);
      }

      if (bnBtcR.status === "fulfilled") {
        btcBinancePrice.current = parseFloat((bnBtcR.value as any)?.price ?? "0");
      }

      if (bithR.status === "fulfilled" && btcBinancePrice.current > 0) {
        const bithKrw = parseFloat((bithR.value as any)?.data?.closing_price ?? "0");
        if (bithKrw > 0) {
          next.btcKrwKimchi = ((bithKrw / (btcBinancePrice.current * usdKrwRate)) - 1) * 100;
        }
      }

      if (btcR.status === "fulfilled") {
        const nTx = (btcR.value as any)?.n_tx ?? 0;
        next.btcTx = nTx;
        next.btcTxLabel = nTx > 450000 ? "활발" : nTx > 250000 ? "보통" : "침체";
      }

      if (feeR.status === "fulfilled") {
        const fast = (feeR.value as any)?.fastestFee ?? 0;
        next.mempoolFee = fast;
        next.mempoolFeeLabel = fast > 80 ? "혼잡" : fast > 30 ? "높음" : "낮음";
      }

      setData(next);
    }

    load();
    const iv = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(iv);
    };
  }, []);

  return data;
}
