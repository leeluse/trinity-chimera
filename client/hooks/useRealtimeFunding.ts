"use client";

import { useState, useEffect, useRef } from "react";

export type FundingMap = Record<string, number>;

export function useRealtimeFunding(): FundingMap {
  const [data, setData] = useState<FundingMap>({});
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    async function poll() {
      try {
        const r = await fetch("https://fapi.binance.com/fapi/v1/premiumIndex", {
          signal: AbortSignal.timeout(8000),
        });
        if (!r.ok) return;

        const arr: Array<{ symbol: string; lastFundingRate: string }> = await r.json();
        const map: FundingMap = {};
        arr.forEach((d) => {
          if (d.symbol?.endsWith("USDT")) {
            map[d.symbol] = parseFloat(d.lastFundingRate);
          }
        });
        setData(map);
      } catch {
        // ignore network errors and retry on next poll
      }
    }

    poll();
    timerRef.current = setInterval(poll, 30_000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  return data;
}
