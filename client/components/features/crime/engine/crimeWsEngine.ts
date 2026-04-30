// Crime Pump Hunter V5 — WebSocket-based engine
// Binance WS로 전체 심볼 실시간 수신 → 상위 35개만 REST 보완 스캔

import type { CoinData } from "../crimeData";
import {
  getBinanceOI, getBinanceLSRatio, getBinanceFundingHistory,
  getBinanceOrderbook, getBinanceTakerFlow, getBinanceKlines,
} from "./binanceApi";
import { scoreCoin, calculateAtr } from "./scoring";

// ─── 타입 ─────────────────────────────────────────────────
interface LiveData {
  price: number;
  vol24h: number;
  pc24h: number;
  fundingRate: number;
  markPrice: number;
  indexPrice: number;
}

export type WsStatus = "idle" | "connecting" | "live" | "scanning" | "error";

export interface WsEngineCallbacks {
  onStatus:   (s: WsStatus, msg?: string) => void;
  onProgress: (done: number, total: number) => void;
  onResults:  (coins: CoinData[]) => void;
}

// ─── 상수 ─────────────────────────────────────────────────
const TOP_N            = 35;   // REST 스캔할 최상위 후보 수
const CONCURRENCY      = 4;    // REST 동시 요청 수
const SCAN_INTERVAL_MS = 5 * 60 * 1000; // 5분
const FIRST_SCAN_MS    = 12_000;        // WS 데이터 충분히 모인 후 첫 스캔

// ─── 유틸 ─────────────────────────────────────────────────
async function pLimit<T>(
  tasks: (() => Promise<T>)[],
  limit: number,
  onProgress?: (done: number, total: number) => void,
): Promise<T[]> {
  const results: T[] = new Array(tasks.length);
  let idx = 0, done = 0;
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

// WS 데이터만으로 빠른 사전 점수 (펀딩비 + 마크/인덱스 괴리)
function preScore(d: LiveData): number {
  const fr  = d.fundingRate;
  const mid = d.indexPrice > 0 ? (d.markPrice - d.indexPrice) / d.indexPrice * 100 : 0;
  let score = 0;
  if      (fr < -0.5) score += 60;
  else if (fr < -0.3) score += 40;
  else if (fr < -0.1) score += 20;
  if (Math.abs(d.pc24h) < 3 && fr < -0.1) score += 15; // 가격 압축
  if (mid < -2) score += 20;
  return score;
}

// 상위 후보 REST 전체 분석
async function analyzeFull(symbol: string, live: LiveData): Promise<CoinData | null> {
  try {
    const [oi, ls, funding, book, taker, klines] = await Promise.all([
      getBinanceOI(symbol),
      getBinanceLSRatio(symbol),
      getBinanceFundingHistory(symbol),
      getBinanceOrderbook(symbol),
      getBinanceTakerFlow(symbol),
      getBinanceKlines(symbol),
    ]);

    const price  = live.price;
    if (price <= 0) return null;

    const mid    = live.indexPrice > 0
      ? (live.markPrice - live.indexPrice) / live.indexPrice * 100
      : 0;

    let pc1h = 0, pc4h = 0, volChangePct = 0;
    const bk = klines as number[][];
    if (bk.length >= 2) {
      const nowClose = bk[0][4];
      const open1h   = bk[1][1];
      pc1h = open1h > 0 ? (nowClose - open1h) / open1h * 100 : 0;
      if (bk.length >= 5) {
        const open4h = bk[4][1];
        pc4h = open4h > 0 ? (nowClose - open4h) / open4h * 100 : 0;
      }
      const recentVol = bk[0][7];
      const pastVols  = bk.slice(1).map((k) => k[7]);
      const avgVol    = pastVols.reduce((a, b) => a + b, 0) / (pastVols.length || 1);
      volChangePct    = avgVol > 0 ? (recentVol - avgVol) / avgVol * 100 : 0;
    }

    const strKlines = bk.map((k) => k.map(String));
    const atr       = calculateAtr(strKlines);
    const atrPct    = price > 0 ? (atr / price) * 100 : 0;

    return scoreCoin({
      symbol,
      funding_rate:         live.fundingRate,
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
      mark_index_diff_pct:  mid,
      price,
      price_change_1h:      pc1h,
      price_change_4h:      pc4h,
      price_change_24h:     live.pc24h,
      volume_24h:           live.vol24h,
      volume_change_pct:    volChangePct,
      atr_pct:              atrPct,
      funding_history:      funding,
    });
  } catch {
    return null;
  }
}

// ─── WS 엔진 클래스 ────────────────────────────────────────
export class CrimeWsEngine {
  private liveData    = new Map<string, LiveData>();
  private tickerWs:   WebSocket | null = null;
  private markWs:     WebSocket | null = null;
  private scanTimer:  ReturnType<typeof setTimeout> | null = null;
  private reconnTimer: ReturnType<typeof setTimeout> | null = null;
  private stopped     = false;
  private wsReady     = false;

  constructor(private cb: WsEngineCallbacks) {}

  // ── 시작 ──────────────────────────────────────────────
  start() {
    this.stopped  = false;
    this.wsReady  = false;
    this.cb.onStatus("connecting");
    this.connectWs();
    // WS 데이터가 채워질 시간을 준 후 첫 스캔
    this.scanTimer = setTimeout(() => this.runScan(), FIRST_SCAN_MS);
  }

  // ── 정지 ──────────────────────────────────────────────
  stop() {
    this.stopped = true;
    this.tickerWs?.close();
    this.markWs?.close();
    this.tickerWs  = null;
    this.markWs    = null;
    if (this.scanTimer)  clearTimeout(this.scanTimer);
    if (this.reconnTimer) clearTimeout(this.reconnTimer);
    this.cb.onStatus("idle");
  }

  get symbolCount() { return this.liveData.size; }

  // ── WebSocket 연결 ─────────────────────────────────────
  private connectWs() {
    // 1. miniTicker: 가격 / 거래량 / 24h 변화율
    const tw = new WebSocket("wss://fstream.binance.com/ws/!miniTicker@arr");
    tw.onmessage = (ev) => {
      try {
        const list = JSON.parse(ev.data as string) as Array<{
          s: string; c: string; o: string; q: string;
        }>;
        for (const item of list) {
          if (!item.s.endsWith("USDT")) continue;
          const existing = this.liveData.get(item.s) ?? newEmpty();
          const close = parseFloat(item.c);
          const open  = parseFloat(item.o);
          this.liveData.set(item.s, {
            ...existing,
            price:  close,
            vol24h: parseFloat(item.q),
            pc24h:  open > 0 ? (close - open) / open * 100 : 0,
          });
        }
        if (!this.wsReady && this.liveData.size > 50) {
          this.wsReady = true;
          this.cb.onStatus("live");
        }
      } catch { /* 파싱 실패 무시 */ }
    };
    tw.onerror = () => this.scheduleReconnect();
    tw.onclose = () => { if (!this.stopped) this.scheduleReconnect(); };
    this.tickerWs = tw;

    // 2. markPrice: 펀딩비 / 마크가격 / 인덱스가격
    const mw = new WebSocket("wss://fstream.binance.com/ws/!markPrice@arr@1s");
    mw.onmessage = (ev) => {
      try {
        const list = JSON.parse(ev.data as string) as Array<{
          s: string; p: string; i: string; r: string;
        }>;
        for (const item of list) {
          if (!item.s.endsWith("USDT")) continue;
          const existing = this.liveData.get(item.s) ?? newEmpty();
          this.liveData.set(item.s, {
            ...existing,
            fundingRate: parseFloat(item.r) * 100,
            markPrice:   parseFloat(item.p),
            indexPrice:  parseFloat(item.i),
          });
        }
      } catch { /* 파싱 실패 무시 */ }
    };
    mw.onerror = () => {}; // markPrice WS 오류는 ticker WS가 커버
    this.markWs = mw;
  }

  private scheduleReconnect() {
    if (this.stopped) return;
    this.cb.onStatus("error", "WS 연결 끊김 — 재연결 중...");
    this.reconnTimer = setTimeout(() => {
      if (!this.stopped) {
        this.wsReady = false;
        this.connectWs();
      }
    }, 3_000);
  }

  // ── REST 보완 스캔 ─────────────────────────────────────
  private async runScan() {
    if (this.stopped) return;

    // 사전 점수로 상위 N개 추출
    const candidates = Array.from(this.liveData.entries())
      .map(([sym, data]) => ({ sym, ps: preScore(data), data }))
      .sort((a, b) => b.ps - a.ps)
      .slice(0, TOP_N);

    if (candidates.length === 0) {
      this.scheduleNextScan();
      return;
    }

    this.cb.onStatus("scanning");
    this.cb.onProgress(0, candidates.length);

    const tasks = candidates.map(({ sym, data }) => async () => {
      if (this.stopped) return null;
      return analyzeFull(sym, data);
    });

    const raw = await pLimit(tasks, CONCURRENCY, (done) => {
      this.cb.onProgress(done, candidates.length);
    });

    if (this.stopped) return;

    const coins = raw.filter((c): c is CoinData => c !== null && c.score > 0);
    if (coins.length > 0) this.cb.onResults(coins);

    this.cb.onStatus("live");
    this.scheduleNextScan();
  }

  private scheduleNextScan() {
    if (this.stopped) return;
    this.scanTimer = setTimeout(() => this.runScan(), SCAN_INTERVAL_MS);
  }
}

function newEmpty(): LiveData {
  return { price: 0, vol24h: 0, pc24h: 0, fundingRate: 0, markPrice: 0, indexPrice: 0 };
}
