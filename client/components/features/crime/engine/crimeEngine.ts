// Crime Pump Hunter V5 — scan orchestrator

import type { CoinData } from "../crimeData";
import {
  getBybitSymbols, getBybitTicker, getBybitOI,
  getBybitLSRatio, getBybitFundingHistory,
  getBybitOrderbook, getBybitTakerFlow, getBybitKlines,
} from "./bybitApi";
import {
  getBinanceSymbols, getBinanceTicker, getBinanceOI,
  getBinanceLSRatio, getBinanceFundingHistory,
  getBinanceOrderbook, getBinanceTakerFlow, getBinanceKlines,
} from "./binanceApi";
import { scoreCoin, calculateAtr } from "./scoring";

const CONCURRENCY = 8;

async function pLimit<T>(
  tasks: (() => Promise<T>)[],
  limit: number,
  onProgress?: (done: number, total: number) => void,
): Promise<T[]> {
  const results: T[] = new Array(tasks.length);
  let idx = 0;
  let done = 0;

  async function worker() {
    while (idx < tasks.length) {
      const i = idx++;
      results[i] = await tasks[i]();
      done++;
      onProgress?.(done, tasks.length);
    }
  }

  await Promise.all(Array.from({ length: limit }, worker));
  return results;
}

// ─── Bybit coin analysis ──────────────────────────────────
async function analyzeBybitCoin(symbol: string): Promise<CoinData | null> {
  try {
    const [ticker, oi, ls, funding, book, taker, klines] = await Promise.all([
      getBybitTicker(symbol),
      getBybitOI(symbol),
      getBybitLSRatio(symbol),
      getBybitFundingHistory(symbol),
      getBybitOrderbook(symbol),
      getBybitTakerFlow(symbol),
      getBybitKlines(symbol),
    ]);

    if (!ticker) return null;

    const price      = parseFloat(ticker.lastPrice ?? "0");
    const markPrice  = parseFloat(ticker.markPrice ?? "0");
    const indexPrice = parseFloat(ticker.indexPrice ?? "0");
    const fr         = parseFloat(ticker.fundingRate ?? "0") * 100;
    const vol24h     = parseFloat(ticker.turnover24h ?? "0");
    const pc24h      = parseFloat(ticker.price24hPcnt ?? "0") * 100;

    if (price <= 0) return null;

    // price change 1h / 4h from klines
    let pc1h = 0, pc4h = 0, volChangePct = 0;
    if (klines.length >= 2) {
      const nowClose  = parseFloat(klines[0][4]);
      const open1h    = parseFloat(klines[1][1]);
      pc1h = open1h > 0 ? (nowClose - open1h) / open1h * 100 : 0;
      if (klines.length >= 5) {
        const open4h = parseFloat(klines[4][1]);
        pc4h = open4h > 0 ? (nowClose - open4h) / open4h * 100 : 0;
      }
      const recentVol = parseFloat(klines[0][6]);
      const pastVols  = klines.slice(1).map((k) => parseFloat(k[6]));
      const avgVol    = pastVols.reduce((a, b) => a + b, 0) / (pastVols.length || 1);
      volChangePct = avgVol > 0 ? (recentVol - avgVol) / avgVol * 100 : 0;
    }

    const atr    = calculateAtr(klines);
    const atrPct = price > 0 ? (atr / price) * 100 : 0;
    const mid    = indexPrice > 0 ? (markPrice - indexPrice) / indexPrice * 100 : 0;

    return scoreCoin({
      symbol,
      funding_rate:         fr,
      oi_change_pct_1h:     oi.change1h,
      oi_change_pct_4h:     oi.change4h,
      oi_change_pct_24h:    oi.change24h,
      long_ratio:           ls.longRatio,
      short_ratio:          ls.shortRatio,
      top_long_ratio:       ls.longRatio,   // Bybit no top-trader endpoint in free tier
      top_short_ratio:      ls.shortRatio,
      taker_buy_ratio:      taker.buyRatio,
      taker_sell_ratio:     taker.sellRatio,
      book_imbalance:       book.imbalance,
      mark_index_diff_pct:  mid,
      price,
      price_change_1h:      pc1h,
      price_change_4h:      pc4h,
      price_change_24h:     pc24h,
      volume_24h:           vol24h,
      volume_change_pct:    volChangePct,
      atr_pct:              atrPct,
      funding_history:      funding,
    });
  } catch {
    return null;
  }
}

// ─── Binance coin analysis ────────────────────────────────
async function analyzeBinanceCoin(symbol: string): Promise<CoinData | null> {
  try {
    const [ticker, oi, ls, funding, book, taker, klines] = await Promise.all([
      getBinanceTicker(symbol),
      getBinanceOI(symbol),
      getBinanceLSRatio(symbol),
      getBinanceFundingHistory(symbol),
      getBinanceOrderbook(symbol),
      getBinanceTakerFlow(symbol),
      getBinanceKlines(symbol),
    ]);

    if (!ticker) return null;

    const price   = parseFloat(ticker.lastPrice ?? "0");
    const vol24h  = parseFloat(ticker.quoteVolume ?? "0");
    const pc24h   = parseFloat(ticker.priceChangePercent ?? "0");
    const fr      = parseFloat(ticker.lastFundingRate ?? ticker.fundingRate ?? "0") * 100;

    if (price <= 0) return null;

    let pc1h = 0, pc4h = 0, volChangePct = 0;
    const binKlines = klines as number[][];
    if (binKlines.length >= 2) {
      const nowClose  = binKlines[0][4];
      const open1h    = binKlines[1][1];
      pc1h = open1h > 0 ? (nowClose - open1h) / open1h * 100 : 0;
      if (binKlines.length >= 5) {
        const open4h = binKlines[4][1];
        pc4h = open4h > 0 ? (nowClose - open4h) / open4h * 100 : 0;
      }
      const recentVol = binKlines[0][7];  // quoteAssetVolume
      const pastVols  = binKlines.slice(1).map((k) => k[7]);
      const avgVol    = pastVols.reduce((a, b) => a + b, 0) / (pastVols.length || 1);
      volChangePct = avgVol > 0 ? (recentVol - avgVol) / avgVol * 100 : 0;
    }

    // Convert Binance klines to string[][] for ATR calculation
    const strKlines = binKlines.map((k) => k.map(String));
    const atr    = calculateAtr(strKlines);
    const atrPct = price > 0 ? (atr / price) * 100 : 0;

    return scoreCoin({
      symbol,
      funding_rate:         fr,
      oi_change_pct_1h:     oi.change1h,
      oi_change_pct_4h:     oi.change4h,
      oi_change_pct_24h:    oi.change24h,
      long_ratio:           ls.longRatio,
      short_ratio:          ls.shortRatio,
      top_long_ratio:       ls.topLongRatio,
      top_short_ratio:      ls.topShortRatio,
      taker_buy_ratio:      taker.buyRatio,
      taker_sell_ratio:     taker.sellRatio,
      book_imbalance:       book.imbalance,
      mark_index_diff_pct:  0,
      price,
      price_change_1h:      pc1h,
      price_change_4h:      pc4h,
      price_change_24h:     pc24h,
      volume_24h:           vol24h,
      volume_change_pct:    volChangePct,
      atr_pct:              atrPct,
      funding_history:      funding,
    });
  } catch {
    return null;
  }
}

// ─── Public: Full Scan ────────────────────────────────────
export interface ScanOptions {
  bybit:    boolean;
  binance:  boolean;
  onProgress?: (done: number, total: number) => void;
  signal?: AbortSignal;
}

export async function runFullScan(opts: ScanOptions): Promise<CoinData[]> {
  const { bybit, binance, onProgress, signal } = opts;

  // 1. Fetch symbol lists in parallel
  const [bybitSymbols, binanceSymbols] = await Promise.all([
    bybit   ? getBybitSymbols()   : Promise.resolve([] as string[]),
    binance ? getBinanceSymbols() : Promise.resolve([] as string[]),
  ]);

  type Task = () => Promise<CoinData | null>;
  const tasks: Task[] = [];

  if (bybit) {
    for (const sym of bybitSymbols) {
      tasks.push(() => {
        if (signal?.aborted) return Promise.resolve(null);
        return analyzeBybitCoin(sym);
      });
    }
  }
  if (binance) {
    // Avoid duplicates already covered by Bybit
    const bybitSet = new Set(bybitSymbols);
    for (const sym of binanceSymbols) {
      if (bybit && bybitSet.has(sym)) continue;
      tasks.push(() => {
        if (signal?.aborted) return Promise.resolve(null);
        return analyzeBinanceCoin(sym);
      });
    }
  }

  const total = tasks.length;
  let doneCount = 0;

  const results = await pLimit(tasks, CONCURRENCY, (done) => {
    doneCount = done;
    onProgress?.(done, total);
  });

  if (signal?.aborted) return [];

  return results.filter((c): c is CoinData => c !== null && c.score > 0);
}
