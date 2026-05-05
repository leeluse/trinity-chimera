// Binance Futures WS 싱글턴 — miniTicker + markPrice 각 1개 연결 공유

export interface BinanceTick {
  s: string;
  c: string;
  o: string;
  q: string;
}

export interface BinanceMarkTick {
  s: string;
  p: string;
  i: string;
  r: string;
}

type TickerHandler    = (items: BinanceTick[])     => void;
type MarkPriceHandler = (items: BinanceMarkTick[]) => void;

interface BusSub {
  ticker:    Set<TickerHandler>;
  markPrice: Set<MarkPriceHandler>;
}

const subs: BusSub = { ticker: new Set(), markPrice: new Set() };

let tickerWs:   WebSocket | null = null;
let markWs:     WebSocket | null = null;
let tickerReady = false;
let tickerTimer: ReturnType<typeof setTimeout> | null = null;
let markTimer:   ReturnType<typeof setTimeout> | null = null;

function openTicker() {
  if (tickerWs && tickerWs.readyState < 2) return;
  tickerWs = new WebSocket("wss://fstream.binance.com/ws/!miniTicker@arr");
  tickerWs.onmessage = (ev) => {
    try {
      const list = JSON.parse(ev.data as string) as BinanceTick[];
      if (!Array.isArray(list)) return;
      const usdt = list.filter(t => t.s.endsWith("USDT"));
      if (!tickerReady && usdt.length > 50) tickerReady = true;
      for (const cb of subs.ticker) cb(usdt);
    } catch { /* 파싱 실패 무시 */ }
  };
  tickerWs.onclose = () => {
    tickerReady = false;
    if (subs.ticker.size > 0)
      tickerTimer = setTimeout(openTicker, 3_000);
  };
  tickerWs.onerror = () => { try { tickerWs?.close(); } catch { /* */ } };
}

function openMark() {
  if (markWs && markWs.readyState < 2) return;
  markWs = new WebSocket("wss://fstream.binance.com/ws/!markPrice@arr@1s");
  markWs.onmessage = (ev) => {
    try {
      const list = JSON.parse(ev.data as string) as BinanceMarkTick[];
      if (!Array.isArray(list)) return;
      const usdt = list.filter(t => t.s.endsWith("USDT"));
      for (const cb of subs.markPrice) cb(usdt);
    } catch { /* */ }
  };
  markWs.onclose = () => {
    if (subs.markPrice.size > 0)
      markTimer = setTimeout(openMark, 3_000);
  };
  markWs.onerror = () => { try { markWs?.close(); } catch { /* */ } };
}

function maybeDisconnect() {
  if (subs.ticker.size === 0) {
    if (tickerTimer) clearTimeout(tickerTimer);
    tickerWs?.close();
    tickerWs = null;
    tickerReady = false;
  }
  if (subs.markPrice.size === 0) {
    if (markTimer) clearTimeout(markTimer);
    markWs?.close();
    markWs = null;
  }
}

export function subscribeTickerBus(cb: TickerHandler): () => void {
  if (subs.ticker.size === 0) openTicker();
  subs.ticker.add(cb);
  return () => { subs.ticker.delete(cb); maybeDisconnect(); };
}

export function subscribeMarkPriceBus(cb: MarkPriceHandler): () => void {
  if (subs.markPrice.size === 0) openMark();
  subs.markPrice.add(cb);
  return () => { subs.markPrice.delete(cb); maybeDisconnect(); };
}

export function isTickerReady(): boolean {
  return tickerReady;
}
