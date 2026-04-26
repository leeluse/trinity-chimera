"use client";

import { useState, useEffect, useRef } from "react";
import { LiqData } from "@/app/scanner/types";

const WS_URL = "wss://fstream.binance.com/ws/!forceOrder@arr";
const WINDOW_MS = 5 * 60 * 1000;

interface LiqEvent {
  symbol: string;
  side: "BUY" | "SELL";
  usd: number;
  time: number;
}

const INITIAL: LiqData = {
  globalShortLiq5m: 0,
  globalLongLiq5m: 0,
  bySymbol: {},
};

export function useLiquidationStream() {
  const [data, setData] = useState<LiqData>(INITIAL);
  const eventsRef = useRef<LiqEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onmessage = (e) => {
        try {
          const now = Date.now();
          const msgs = JSON.parse(e.data);
          const arr = Array.isArray(msgs) ? msgs : [msgs];

          arr.forEach((d: any) => {
            const o = d.o ?? d;
            if (!o?.s) return;
            const usd = parseFloat(o.q) * parseFloat(o.p);
            if (!isFinite(usd) || usd <= 0) return;
            eventsRef.current.push({ symbol: o.s, side: o.S, usd, time: now });
          });

          const cutoff = now - WINDOW_MS;
          eventsRef.current = eventsRef.current.filter((ev) => ev.time >= cutoff);

          let globalShort = 0;
          let globalLong = 0;
          const bySymbol: Record<string, { shortLiq: number; longLiq: number }> = {};

          eventsRef.current.forEach((ev) => {
            if (!bySymbol[ev.symbol]) bySymbol[ev.symbol] = { shortLiq: 0, longLiq: 0 };
            if (ev.side === "BUY") {
              bySymbol[ev.symbol].shortLiq += ev.usd;
              globalShort += ev.usd;
            } else {
              bySymbol[ev.symbol].longLiq += ev.usd;
              globalLong += ev.usd;
            }
          });

          setData({ globalShortLiq5m: globalShort, globalLongLiq5m: globalLong, bySymbol });
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        reconnectTimer.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => ws.close();
    }

    connect();

    return () => {
      wsRef.current?.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, []);

  return data;
}
