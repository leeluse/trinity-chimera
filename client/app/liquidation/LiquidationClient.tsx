'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import Link from 'next/link';
import styles from './liquidation.module.css';

// ─── Types ───────────────────────────────────────────────────

interface SymbolState {
  symbol: string;
  price: number;
  volume24h: number;
  change24h: number;
  funding: number | null;
  fundingNext: number | null;
  oi: number | null;
  oiUsd: number | null;
  oiHistory: Array<{ ts: number; oi: number; oiUsd: number }>;
  oiChange1h: number | null;
  lsRatio: number | null;
  liqHistory: Array<{ ts: number; side: string; qty: number; price: number; value: number }>;
  liqValue1min: number;
  liqValue5min: number;
  baseline: { mean: number; stdev: number; n: number };
  baselineBuckets: number[];
  bucketStart: number;
  currentBucket: number;
  ignited: boolean;
  ignitedAt: number | null;
  ignitedSide: string | null;
  ignitedValue: number;
  ignitedSigma: number;
  lastLiqTs: number | null;
}

interface AlertItem {
  symbol: string;
  side: string;
  value: number;
  sigma: number;
  ts: number;
}

interface Config {
  symbolCount: number;
  leverage: Record<number, number>;
  maintenanceMargin: number;
  ignitionSigma: number;
  minLiqUsd: number;
  biasWeights: { funding: number; ls: number; oi: number };
  priceBands: number[];
}

interface PressureResult {
  long: [number, number, number];
  short: [number, number, number];
  maxVal: number;
}

interface ToastItem {
  id: number;
  msg: string;
  type: string;
}

// ─── Constants ───────────────────────────────────────────────

const DEFAULTS: Config = {
  symbolCount: 30,
  leverage: { 25: 0.30, 50: 0.40, 100: 0.30 },
  maintenanceMargin: 0.005,
  ignitionSigma: 3.0,
  minLiqUsd: 100000,
  biasWeights: { funding: 0.4, ls: 0.3, oi: 0.3 },
  priceBands: [0.01, 0.02, 0.05],
};

const LIQ_WINDOW_MS = 5 * 60 * 1000;
const RENDER_THROTTLE_MS = 1000;
const OI_POLL_MS = 30 * 1000;
const LS_POLL_MS = 60 * 1000;

// ─── Utilities ───────────────────────────────────────────────

function fmtPrice(p: number | null): string {
  if (p == null || !isFinite(p)) return '--';
  if (p >= 1000) return p.toLocaleString('en-US', { maximumFractionDigits: 1 });
  if (p >= 10) return p.toFixed(2);
  if (p >= 1) return p.toFixed(3);
  if (p >= 0.01) return p.toFixed(4);
  return p.toFixed(6);
}

function fmtUsd(v: number): string {
  if (!v || !isFinite(v)) return '$0';
  if (v >= 1e9) return '$' + (v / 1e9).toFixed(2) + 'B';
  if (v >= 1e6) return '$' + (v / 1e6).toFixed(2) + 'M';
  if (v >= 1e3) return '$' + (v / 1e3).toFixed(1) + 'K';
  return '$' + Math.round(v);
}

function fmtPct(v: number | null, decimals = 2): string {
  if (v == null || !isFinite(v)) return '--';
  const sign = v > 0 ? '+' : '';
  return sign + v.toFixed(decimals) + '%';
}

function fmtTimeAgo(ts: number | null): string {
  if (!ts) return '--';
  const d = (Date.now() - ts) / 1000;
  if (d < 60) return Math.round(d) + 's 전';
  if (d < 3600) return Math.round(d / 60) + 'm 전';
  return Math.round(d / 3600) + 'h 전';
}

// ─── Calculations ─────────────────────────────────────────────

function calculatePressureMap(s: SymbolState, cfg: Config): PressureResult | null {
  if (!s.oiUsd || !s.price) return null;
  const oiUsd = s.oiUsd;

  let longRatio = 0.5, shortRatio = 0.5;
  if (s.lsRatio && isFinite(s.lsRatio) && s.lsRatio > 0) {
    longRatio = s.lsRatio / (1 + s.lsRatio);
    shortRatio = 1 / (1 + s.lsRatio);
  }
  const longOI = oiUsd * longRatio;
  const shortOI = oiUsd * shortRatio;

  const wSum = cfg.leverage[25] + cfg.leverage[50] + cfg.leverage[100];
  const w25 = cfg.leverage[25] / wSum;
  const w50 = cfg.leverage[50] / wSum;
  const w100 = cfg.leverage[100] / wSum;

  const mmr = cfg.maintenanceMargin;
  const liqPct: Record<number, number> = {
    25: (1 / 25) - mmr,
    50: (1 / 50) - mmr,
    100: (1 / 100) - mmr,
  };

  const bands = cfg.priceBands;
  const result: PressureResult = { long: [0, 0, 0], short: [0, 0, 0], maxVal: 0 };

  const addToBand = (arr: [number, number, number], pct: number, value: number) => {
    for (let i = 0; i < bands.length; i++) {
      if (pct <= bands[i]) { arr[i] += value; return; }
    }
    arr[bands.length - 1] += value;
  };

  addToBand(result.long, liqPct[100], longOI * w100);
  addToBand(result.long, liqPct[50], longOI * w50);
  addToBand(result.long, liqPct[25], longOI * w25);
  addToBand(result.short, liqPct[100], shortOI * w100);
  addToBand(result.short, liqPct[50], shortOI * w50);
  addToBand(result.short, liqPct[25], shortOI * w25);

  result.maxVal = Math.max(...result.long, ...result.short);
  return result;
}

function calculateBias(s: SymbolState, cfg: Config): number | null {
  let fundingScore: number | null = null;
  if (s.funding != null) {
    fundingScore = -Math.max(-100, Math.min(100, s.funding * 100000));
  }

  let lsScore: number | null = null;
  if (s.lsRatio != null && isFinite(s.lsRatio)) {
    lsScore = -Math.max(-100, Math.min(100, (s.lsRatio - 1) * 100));
  }

  let oiScore: number | null = null;
  if (s.oiChange1h != null && s.change24h != null) {
    const oiMag = Math.max(-100, Math.min(100, s.oiChange1h * 10));
    if (oiMag > 0) {
      oiScore = s.change24h > 0 ? -Math.abs(oiMag) : Math.abs(oiMag);
    } else {
      oiScore = oiMag * 0.3;
    }
  }

  const weights = cfg.biasWeights;
  const entries = [
    [fundingScore, weights.funding],
    [lsScore, weights.ls],
    [oiScore, weights.oi],
  ].filter(([v]) => v != null) as [number, number][];

  if (entries.length === 0) return null;
  const totalW = entries.reduce((a, [, w]) => a + w, 0);
  const sum = entries.reduce((a, [v, w]) => a + v * w, 0);
  return Math.max(-100, Math.min(100, sum / totalW));
}

function makeEmptySymbol(t: { symbol: string; lastPrice: string; quoteVolume: string; priceChangePercent: string }): SymbolState {
  return {
    symbol: t.symbol,
    price: parseFloat(t.lastPrice),
    volume24h: parseFloat(t.quoteVolume),
    change24h: parseFloat(t.priceChangePercent),
    funding: null, fundingNext: null,
    oi: null, oiUsd: null,
    oiHistory: [], oiChange1h: null,
    lsRatio: null,
    liqHistory: [],
    liqValue1min: 0, liqValue5min: 0,
    baseline: { mean: 0, stdev: 0, n: 0 },
    baselineBuckets: [],
    bucketStart: Date.now(),
    currentBucket: 0,
    ignited: false, ignitedAt: null, ignitedSide: null,
    ignitedValue: 0, ignitedSigma: 0, lastLiqTs: null,
  };
}

// ─── Sub-components ───────────────────────────────────────────

interface SymbolCardProps {
  s: SymbolState;
  config: Config;
}

function SymbolCard({ s, config }: SymbolCardProps) {
  const pm = calculatePressureMap(s, config);
  const bias = calculateBias(s, config);
  const changeClass = s.change24h > 0 ? '#22c55e' : s.change24h < 0 ? '#ef4444' : '#a0a0a8';
  const changeSign = s.change24h > 0 ? '+' : '';

  // Pressure bar
  let pressureContent: React.ReactNode;
  if (pm && pm.maxVal > 0) {
    const norm = (v: number) => pm.maxVal > 0 ? (v / pm.maxVal) * 100 : 0;
    const l5 = norm(pm.long[2]), l2 = norm(pm.long[1]), l1 = norm(pm.long[0]);
    const s1 = norm(pm.short[0]), s2 = norm(pm.short[1]), s5 = norm(pm.short[2]);
    pressureContent = (
      <div className={styles.pressureBar}>
        <div className={styles.pressureSideLong}>
          <div className={styles.pressureTick}><div className={styles.pressureFillLong} style={{ height: `${l5}%` }} /></div>
          <div className={styles.pressureTick}><div className={styles.pressureFillLong} style={{ height: `${l2}%` }} /></div>
          <div className={styles.pressureTick}><div className={styles.pressureFillLong} style={{ height: `${l1}%` }} /></div>
        </div>
        <div className={styles.pressureCenterLine} />
        <div className={styles.pressureSideShort}>
          <div className={styles.pressureTick}><div className={styles.pressureFillShort} style={{ height: `${s1}%` }} /></div>
          <div className={styles.pressureTick}><div className={styles.pressureFillShort} style={{ height: `${s2}%` }} /></div>
          <div className={styles.pressureTick}><div className={styles.pressureFillShort} style={{ height: `${s5}%` }} /></div>
        </div>
      </div>
    );
  } else {
    pressureContent = (
      <div className={styles.pressureBar}>
        <div style={{ color: '#40404a', fontSize: 10, margin: 'auto' }}>OI 데이터 대기 중</div>
      </div>
    );
  }

  // Bias bar
  let biasBar: React.ReactNode = null;
  if (bias != null) {
    const absBias = Math.abs(bias);
    const biasColor = bias < 0 ? '#ef4444' : '#22c55e';
    const biasLeft = bias < 0 ? (50 - absBias / 2) : 50;
    biasBar = (
      <div className={styles.biasBar}>
        <div className={styles.biasFill} style={{ left: `${biasLeft}%`, width: `${absBias / 2}%`, background: biasColor }} />
        <div className={styles.biasCenter} />
      </div>
    );
  }

  const biasValueClass = bias == null ? styles.metricDim : (bias < -20 ? styles.metricNeg : (bias > 20 ? styles.metricPos : ''));
  const biasText = bias == null ? '--' : (bias > 0 ? '+' : '') + bias.toFixed(0);
  const fundingClass = s.funding == null ? styles.metricDim : (s.funding > 0 ? styles.metricNeg : (s.funding < 0 ? styles.metricPos : ''));
  const fundingText = s.funding == null ? '--' : (s.funding * 100).toFixed(4) + '%';
  const lsClass = s.lsRatio == null ? styles.metricDim : (s.lsRatio > 1.2 ? styles.metricNeg : (s.lsRatio < 0.8 ? styles.metricPos : ''));
  const lsText = s.lsRatio == null ? '--' : s.lsRatio.toFixed(2);
  const oiChangeClass = s.oiChange1h == null ? styles.metricDim : (s.oiChange1h > 0 ? styles.metricPos : styles.metricNeg);
  const ignitionText = s.ignited ? `🔥 ${s.ignitedSide?.toUpperCase()} ${s.ignitedSigma.toFixed(1)}σ` : 'QUIET';
  const ignitionClass = s.ignited ? styles.metricWarn : styles.metricDim;

  return (
    <div className={`${styles.symbolCard} ${s.ignited ? styles.symbolCardIgnited : ''}`}>
      <div className="flex items-baseline justify-between mb-2.5">
        <div style={{ fontWeight: 700, fontSize: 14, letterSpacing: '0.3px' }}>
          {s.symbol.replace('USDT', '')}
          <span style={{ color: '#40404a', fontSize: 10 }}>/USDT</span>
        </div>
        <div>
          <span style={{ fontSize: 13, fontWeight: 600 }}>{fmtPrice(s.price)}</span>
          <span style={{ fontSize: 10, marginLeft: 6, color: changeClass }}>
            {changeSign}{s.change24h?.toFixed(2) ?? '--'}%
          </span>
        </div>
      </div>

      <div style={{ margin: '10px 0', padding: '8px 0' }}>
        <div className="flex justify-between" style={{ fontSize: 9, color: '#60606a', letterSpacing: 1, textTransform: 'uppercase', marginBottom: 4 }}>
          <span style={{ color: '#ef4444' }}>◄ LONG LIQ ZONE</span>
          <span style={{ color: '#22c55e' }}>SHORT LIQ ZONE ►</span>
        </div>
        {pressureContent}
        <div className="flex justify-between" style={{ fontSize: 9, color: '#40404a', marginTop: 3 }}>
          {['-5%', '-2%', '-1%', '+1%', '+2%', '+5%'].map(l => (
            <span key={l} style={{ flex: 1, textAlign: 'center' }}>{l}</span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-y-1.5 gap-x-3 mt-2.5 pt-2.5" style={{ borderTop: '1px dashed #25252b' }}>
        <div className="flex justify-between items-baseline">
          <span className={styles.metricLabel}>Bias</span>
          <span className={`${styles.metricValue} ${biasValueClass}`}>{biasText}</span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className={styles.metricLabel}>Ignition</span>
          <span className={`${styles.metricValue} ${ignitionClass}`}>{ignitionText}</span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className={styles.metricLabel}>Funding</span>
          <span className={`${styles.metricValue} ${fundingClass}`}>{fundingText}</span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className={styles.metricLabel}>L/S Ratio</span>
          <span className={`${styles.metricValue} ${lsClass}`}>{lsText}</span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className={styles.metricLabel}>1h OI</span>
          <span className={`${styles.metricValue} ${oiChangeClass}`}>{fmtPct(s.oiChange1h)}</span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className={styles.metricLabel}>Liq 5m</span>
          <span className={styles.metricValue}>{fmtUsd(s.liqValue5min || 0)}</span>
        </div>
      </div>
      {biasBar}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────

export default function LiquidationClient() {
  const symbolsRef = useRef<Map<string, SymbolState>>(new Map());
  const trackedRef = useRef<string[]>([]);
  const alertsRef = useRef<AlertItem[]>([]);
  const statsRef = useRef({ liqCount: 0, liqValueTotal: 0, reconnects: 0 });
  const liqWsRef = useRef<WebSocket | null>(null);
  const markWsRef = useRef<WebSocket | null>(null);
  const renderPendingRef = useRef(false);
  const lastRenderTsRef = useRef(0);

  const [renderTick, setRenderTick] = useState(0);
  const [config, setConfig] = useState<Config>(JSON.parse(JSON.stringify(DEFAULTS)));
  const [wsStatus, setWsStatus] = useState<'connecting' | 'live' | 'error'>('connecting');
  const [wsStatusText, setWsStatusText] = useState('연결 중...');
  const [showSettings, setShowSettings] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [sortBy, setSortBy] = useState('ignition');
  const [filterBy, setFilterBy] = useState('all');
  const [symbolCount, setSymbolCount] = useState(30);
  const [lastUpdate, setLastUpdate] = useState('--');
  const [sbOiUpdate, setSbOiUpdate] = useState('--');
  const [sbLsUpdate, setSbLsUpdate] = useState('--');
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  // Settings form refs
  const cfgLev25Ref = useRef<HTMLInputElement>(null);
  const cfgLev50Ref = useRef<HTMLInputElement>(null);
  const cfgLev100Ref = useRef<HTMLInputElement>(null);
  const cfgSigmaRef = useRef<HTMLInputElement>(null);
  const cfgMinLiqRef = useRef<HTMLInputElement>(null);
  const cfgWFundRef = useRef<HTMLInputElement>(null);
  const cfgWLSRef = useRef<HTMLInputElement>(null);
  const cfgWOIRef = useRef<HTMLInputElement>(null);

  const addToast = useCallback((msg: string, type = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, msg, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4500);
  }, []);

  const scheduleRender = useCallback(() => {
    if (renderPendingRef.current) return;
    renderPendingRef.current = true;
    const wait = Math.max(0, RENDER_THROTTLE_MS - (Date.now() - lastRenderTsRef.current));
    setTimeout(() => {
      renderPendingRef.current = false;
      lastRenderTsRef.current = Date.now();
      setRenderTick(t => t + 1);
      setLastUpdate(new Date().toLocaleTimeString('ko-KR', { hour12: false }));
    }, wait);
  }, []);

  // ─── Ignition logic ──────────────────────────────────────────

  const checkIgnition = useCallback((s: SymbolState, cfg: Config) => {
    const now = Date.now();
    const elapsed = now - s.bucketStart;
    if (elapsed >= 60000) {
      s.baselineBuckets.push(s.currentBucket);
      if (s.baselineBuckets.length > 60) s.baselineBuckets.shift();
      if (s.baselineBuckets.length >= 5) {
        const vals = s.baselineBuckets;
        const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
        const stdev = Math.sqrt(vals.reduce((a, v) => a + (v - mean) ** 2, 0) / vals.length);
        s.baseline = { mean, stdev, n: vals.length };
      }
      s.currentBucket = 0;
      s.bucketStart = now;
    }

    const cutoff = now - 60000;
    let longVal = 0, shortVal = 0;
    s.liqHistory.forEach(l => {
      if (l.ts < cutoff) return;
      if (l.side === 'SELL') longVal += l.value;
      else if (l.side === 'BUY') shortVal += l.value;
    });
    const totalRecent = longVal + shortVal;
    s.currentBucket = totalRecent;
    s.liqValue1min = totalRecent;
    s.liqValue5min = s.liqHistory.reduce((a, l) => a + l.value, 0);

    if (s.baseline.n < 5) return;
    const { mean, stdev } = s.baseline;
    const effectiveStdev = Math.max(stdev, mean * 0.3, 1000);
    const z = (totalRecent - mean) / effectiveStdev;

    if (z >= cfg.ignitionSigma && totalRecent >= cfg.minLiqUsd) {
      const side = longVal > shortVal ? 'long' : 'short';
      const val = longVal > shortVal ? longVal : shortVal;
      if (!s.ignited) {
        s.ignited = true;
        s.ignitedAt = now;
        s.ignitedSide = side;
        s.ignitedValue = val;
        s.ignitedSigma = z;
        const alert: AlertItem = { symbol: s.symbol, side, value: val, sigma: z, ts: now };
        alertsRef.current = [alert, ...alertsRef.current.filter(a => a.symbol !== s.symbol)].slice(0, 20);
        addToast(`🚨 ${s.symbol} ${side.toUpperCase()} 청산 급증 · ${fmtUsd(val)} · ${z.toFixed(1)}σ`, 'error');
      } else {
        s.ignitedValue = val;
        s.ignitedSigma = Math.max(s.ignitedSigma, z);
      }
    } else if (s.ignited && s.ignitedAt && (now - s.ignitedAt) > 3 * 60 * 1000) {
      s.ignited = false;
    }
  }, [addToast]);

  // ─── REST polling ─────────────────────────────────────────────

  const pollOI = useCallback(async () => {
    const syms = trackedRef.current.slice();
    for (let i = 0; i < syms.length; i += 10) {
      const batch = syms.slice(i, i + 10);
      await Promise.all(batch.map(async (sym) => {
        try {
          const res = await fetch(`https://fapi.binance.com/fapi/v1/openInterest?symbol=${sym}`);
          if (!res.ok) return;
          const data = await res.json();
          const s = symbolsRef.current.get(sym);
          if (!s) return;
          const oi = parseFloat(data.openInterest);
          s.oi = oi;
          s.oiUsd = oi * (s.price || 0);
          s.oiHistory.push({ ts: Date.now(), oi, oiUsd: s.oiUsd });
          if (s.oiHistory.length > 48) s.oiHistory.shift();
          const oneHourAgo = Date.now() - 3600000;
          const old = s.oiHistory.find(h => h.ts >= oneHourAgo);
          if (old && old.oi > 0) s.oiChange1h = ((s.oi - old.oi) / old.oi) * 100;
        } catch { /* continue */ }
      }));
      await new Promise(r => setTimeout(r, 200));
    }
    setSbOiUpdate(new Date().toLocaleTimeString('ko-KR', { hour12: false }));
    scheduleRender();
  }, [scheduleRender]);

  const pollLS = useCallback(async () => {
    const syms = trackedRef.current.slice();
    for (let i = 0; i < syms.length; i += 10) {
      const batch = syms.slice(i, i + 10);
      await Promise.all(batch.map(async (sym) => {
        try {
          const res = await fetch(
            `https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol=${sym}&period=5m&limit=1`
          );
          if (!res.ok) return;
          const arr = await res.json();
          if (!Array.isArray(arr) || arr.length === 0) return;
          const s = symbolsRef.current.get(sym);
          if (s) s.lsRatio = parseFloat(arr[0].longShortRatio);
        } catch { /* continue */ }
      }));
      await new Promise(r => setTimeout(r, 200));
    }
    setSbLsUpdate(new Date().toLocaleTimeString('ko-KR', { hour12: false }));
    scheduleRender();
  }, [scheduleRender]);

  // ─── Symbol discovery ─────────────────────────────────────────

  const discoverTopSymbols = useCallback(async (count: number) => {
    setWsStatus('connecting');
    setWsStatusText('심볼 목록 조회 중...');
    try {
      const res = await fetch('https://fapi.binance.com/fapi/v1/ticker/24hr');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const tickers = await res.json() as Array<{ symbol: string; quoteVolume: string; lastPrice: string; priceChangePercent: string }>;
      const filtered = tickers
        .filter(t => t.symbol.endsWith('USDT') && !t.symbol.includes('_') &&
          !/^(USDC|TUSD|BUSD|FDUSD|DAI|USTC)USDT$/.test(t.symbol))
        .sort((a, b) => parseFloat(b.quoteVolume) - parseFloat(a.quoteVolume));
      const top = filtered.slice(0, count);
      top.forEach(t => {
        if (!symbolsRef.current.has(t.symbol)) {
          symbolsRef.current.set(t.symbol, makeEmptySymbol(t));
        } else {
          const s = symbolsRef.current.get(t.symbol)!;
          s.price = parseFloat(t.lastPrice);
          s.volume24h = parseFloat(t.quoteVolume);
          s.change24h = parseFloat(t.priceChangePercent);
        }
      });
      trackedRef.current = top.map(t => t.symbol);
      return trackedRef.current;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      addToast('심볼 목록 조회 실패: ' + msg, 'error');
      setWsStatus('error');
      setWsStatusText('심볼 조회 실패');
      return [];
    }
  }, [addToast]);

  // ─── WebSocket connections ────────────────────────────────────

  const connectLiqWs = useCallback((cfg: Config) => {
    if (liqWsRef.current) try { liqWsRef.current.close(); } catch { /* ignore */ }
    const ws = new WebSocket('wss://fstream.binance.com/ws/!forceOrder@arr');
    liqWsRef.current = ws;
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (!msg.o) return;
        const o = msg.o;
        const s = symbolsRef.current.get(o.s);
        if (!s) return;
        const qty = parseFloat(o.q);
        const price = parseFloat(o.ap || o.p);
        const value = qty * price;
        const ts = o.T || Date.now();
        s.liqHistory.push({ ts, side: o.S, qty, price, value });
        s.lastLiqTs = ts;
        statsRef.current.liqCount++;
        statsRef.current.liqValueTotal += value;
        const cutoff = Date.now() - LIQ_WINDOW_MS;
        s.liqHistory = s.liqHistory.filter(l => l.ts >= cutoff);
        checkIgnition(s, cfg);
        scheduleRender();
      } catch { /* ignore */ }
    };
    ws.onerror = () => { /* handled in onclose */ };
    ws.onclose = () => {
      statsRef.current.reconnects++;
      setTimeout(() => connectLiqWs(cfg), 3000);
    };
  }, [checkIgnition, scheduleRender]);

  const connectMarkWs = useCallback(() => {
    if (markWsRef.current) try { markWsRef.current.close(); } catch { /* ignore */ }
    const ws = new WebSocket('wss://fstream.binance.com/ws/!markPrice@arr@1s');
    markWsRef.current = ws;
    ws.onopen = () => { setWsStatus('live'); setWsStatusText('LIVE · 데이터 수신 중'); };
    ws.onmessage = (evt) => {
      try {
        const arr = JSON.parse(evt.data);
        if (!Array.isArray(arr)) return;
        arr.forEach(m => {
          const s = symbolsRef.current.get(m.s);
          if (!s) return;
          s.price = parseFloat(m.p);
          s.funding = parseFloat(m.r);
          s.fundingNext = m.T;
        });
        scheduleRender();
      } catch { /* ignore */ }
    };
    ws.onerror = () => { /* handled in onclose */ };
    ws.onclose = () => {
      setWsStatus('connecting');
      setWsStatusText('재연결 중...');
      setTimeout(connectMarkWs, 3000);
    };
  }, [scheduleRender]);

  // ─── Initialization ───────────────────────────────────────────

  useEffect(() => {
    const cfg = JSON.parse(JSON.stringify(DEFAULTS)) as Config;
    let oiTimer: ReturnType<typeof setInterval>;
    let lsTimer: ReturnType<typeof setInterval>;
    let baselineTimer: ReturnType<typeof setInterval>;

    const init = async () => {
      await discoverTopSymbols(cfg.symbolCount);
      if (trackedRef.current.length === 0) { setWsStatus('error'); setWsStatusText('초기화 실패'); return; }
      setWsStatusText('OI / L/S 비율 조회 중...');
      await Promise.all([pollOI(), pollLS()]);
      connectLiqWs(cfg);
      connectMarkWs();
      oiTimer = setInterval(pollOI, OI_POLL_MS);
      lsTimer = setInterval(pollLS, LS_POLL_MS);
      baselineTimer = setInterval(() => {
        symbolsRef.current.forEach(s => checkIgnition(s, cfg));
        scheduleRender();
      }, 10000);
      scheduleRender();
    };

    init().catch(err => {
      addToast('초기화 실패: ' + (err?.message ?? err), 'error');
      setWsStatus('error');
      setWsStatusText('실패 — 새로고침 필요');
    });

    return () => {
      clearInterval(oiTimer);
      clearInterval(lsTimer);
      clearInterval(baselineTimer);
      try { liqWsRef.current?.close(); } catch { /* ignore */ }
      try { markWsRef.current?.close(); } catch { /* ignore */ }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─── Symbol count change ──────────────────────────────────────

  const handleSymbolCountChange = useCallback(async (count: number) => {
    setSymbolCount(count);
    await discoverTopSymbols(count);
    scheduleRender();
  }, [discoverTopSymbols, scheduleRender]);

  // ─── Settings ────────────────────────────────────────────────

  const applySettingsToForm = useCallback((cfg: Config) => {
    if (cfgLev25Ref.current) cfgLev25Ref.current.value = String(cfg.leverage[25]);
    if (cfgLev50Ref.current) cfgLev50Ref.current.value = String(cfg.leverage[50]);
    if (cfgLev100Ref.current) cfgLev100Ref.current.value = String(cfg.leverage[100]);
    if (cfgSigmaRef.current) cfgSigmaRef.current.value = String(cfg.ignitionSigma);
    if (cfgMinLiqRef.current) cfgMinLiqRef.current.value = String(cfg.minLiqUsd);
    if (cfgWFundRef.current) cfgWFundRef.current.value = String(cfg.biasWeights.funding);
    if (cfgWLSRef.current) cfgWLSRef.current.value = String(cfg.biasWeights.ls);
    if (cfgWOIRef.current) cfgWOIRef.current.value = String(cfg.biasWeights.oi);
  }, []);

  const saveSettings = useCallback(() => {
    const newCfg: Config = {
      ...config,
      leverage: {
        25: parseFloat(cfgLev25Ref.current?.value || '0.3'),
        50: parseFloat(cfgLev50Ref.current?.value || '0.4'),
        100: parseFloat(cfgLev100Ref.current?.value || '0.3'),
      },
      ignitionSigma: parseFloat(cfgSigmaRef.current?.value || '3.0'),
      minLiqUsd: parseFloat(cfgMinLiqRef.current?.value || '100000'),
      biasWeights: {
        funding: parseFloat(cfgWFundRef.current?.value || '0.4'),
        ls: parseFloat(cfgWLSRef.current?.value || '0.3'),
        oi: parseFloat(cfgWOIRef.current?.value || '0.3'),
      },
    };
    setConfig(newCfg);
    setShowSettings(false);
    addToast('설정 저장됨', 'success');
    scheduleRender();
  }, [config, addToast, scheduleRender]);

  const resetDefaults = useCallback(() => {
    const defaults = JSON.parse(JSON.stringify(DEFAULTS)) as Config;
    setConfig(defaults);
    applySettingsToForm(defaults);
    addToast('기본값으로 복원됨', 'success');
  }, [applySettingsToForm, addToast]);

  // ─── Render helpers ───────────────────────────────────────────

  const getFilteredSorted = () => {
    let syms = trackedRef.current.slice();

    // filter
    if (filterBy === 'ignited') {
      syms = syms.filter(sym => symbolsRef.current.get(sym)?.ignited);
    } else if (filterBy === 'strong_bias') {
      syms = syms.filter(sym => {
        const b = calculateBias(symbolsRef.current.get(sym)!, config);
        return b != null && Math.abs(b) >= 60;
      });
    }

    // sort
    switch (sortBy) {
      case 'ignition':
        syms.sort((a, b) => {
          const ai = symbolsRef.current.get(a)?.ignited ? 1 : 0;
          const bi = symbolsRef.current.get(b)?.ignited ? 1 : 0;
          if (ai !== bi) return bi - ai;
          const ab = Math.abs(calculateBias(symbolsRef.current.get(a)!, config) || 0);
          const bb = Math.abs(calculateBias(symbolsRef.current.get(b)!, config) || 0);
          return bb - ab;
        });
        break;
      case 'bias_abs':
        syms.sort((a, b) => Math.abs(calculateBias(symbolsRef.current.get(b)!, config) || 0) - Math.abs(calculateBias(symbolsRef.current.get(a)!, config) || 0));
        break;
      case 'bias_neg':
        syms.sort((a, b) => (calculateBias(symbolsRef.current.get(a)!, config) || 0) - (calculateBias(symbolsRef.current.get(b)!, config) || 0));
        break;
      case 'bias_pos':
        syms.sort((a, b) => (calculateBias(symbolsRef.current.get(b)!, config) || 0) - (calculateBias(symbolsRef.current.get(a)!, config) || 0));
        break;
      case 'oi_change':
        syms.sort((a, b) => Math.abs(symbolsRef.current.get(b)?.oiChange1h || 0) - Math.abs(symbolsRef.current.get(a)?.oiChange1h || 0));
        break;
      case 'volume':
        syms.sort((a, b) => (symbolsRef.current.get(b)?.volume24h || 0) - (symbolsRef.current.get(a)?.volume24h || 0));
        break;
      case 'symbol':
        syms.sort();
        break;
    }
    return syms;
  };

  // Alert cleanup
  const activeAlerts = alertsRef.current.filter(a => {
    const cutoff = Date.now() - LIQ_WINDOW_MS;
    if (a.ts < cutoff) return false;
    const s = symbolsRef.current.get(a.symbol);
    return s?.ignited;
  });

  const displaySymbols = getFilteredSorted();

  // Stats
  let totalLiqValue = 0;
  symbolsRef.current.forEach(s => { totalLiqValue += s.liqValue5min || 0; });

  const dotClass = wsStatus === 'live' ? styles.statusDotLive : wsStatus === 'error' ? styles.statusDotError : styles.statusDotConnecting;

  // ─── Render ───────────────────────────────────────────────────

  return (
    <div className={styles.wrap}>
      {/* Header */}
      <header className={styles.header}>
        <div className="flex items-center gap-3">
          <div className={styles.brandMark}>L</div>
          <div>
            <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.5px' }}>LIQUIDATION PRESSURE MAP</span>
            <span style={{ color: '#60606a', fontSize: 10, fontWeight: 400, marginLeft: 6 }}>v1.0</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className={styles.btn}
            style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}
          >
            ← 대시보드
          </Link>
          <div className={styles.statusIndicator}>
            <span className={`${styles.statusDot} ${dotClass}`} />
            <span style={{ color: '#a0a0a8' }}>{wsStatusText}</span>
          </div>
          <button className={styles.btn} onClick={() => { applySettingsToForm(config); setShowSettings(true); }}>⚙ 설정</button>
          <button className={styles.btn} onClick={() => setShowHelp(true)}>? 도움말</button>
        </div>
      </header>

      {/* Ignition Alerts */}
      <section className={styles.alertsSection}>
        <div className={styles.sectionTitle}>
          🚨 IGNITION ALERTS
          <span className={`${styles.count} ${activeAlerts.length > 0 ? styles.countHot : ''}`}>
            {activeAlerts.length}
          </span>
          <span style={{ marginLeft: 'auto', color: '#40404a', fontSize: 10 }}>연쇄 청산 감지 · 지난 5분</span>
        </div>
        <div className="flex flex-wrap gap-2" style={{ minHeight: 40 }}>
          {activeAlerts.length === 0 ? (
            <div style={{ color: '#40404a', fontSize: 11, padding: '12px 0', fontStyle: 'italic' }}>
              대기 중 · 청산 급증 감지 시 여기에 표시
            </div>
          ) : activeAlerts.map(a => (
            <div key={a.symbol} className={`${styles.alertCard} ${a.side === 'long' ? styles.alertCardLongLiq : styles.alertCardShortLiq}`}>
              <div style={{ fontWeight: 700, fontSize: 13 }}>{a.symbol}</div>
              <div className={a.side === 'long' ? styles.alertTypeLong : styles.alertTypeShort}>
                {a.side === 'long' ? 'LONG LIQ' : 'SHORT SQUEEZE'}
              </div>
              <div className="flex flex-col gap-0.5 ml-auto">
                <div style={{ fontSize: 13, fontWeight: 600 }}>{fmtUsd(a.value)}</div>
                <div style={{ fontSize: 10, color: '#60606a' }}>
                  {fmtTimeAgo(a.ts)} · <span style={{ color: '#f59e0b', fontWeight: 600 }}>{a.sigma.toFixed(1)}σ</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Toolbar */}
      <section className={styles.toolbar}>
        <div className="flex items-center gap-1.5">
          <span className={styles.toolLabel}>심볼수</span>
          <select className={styles.toolSelect} value={symbolCount} onChange={e => handleSymbolCountChange(parseInt(e.target.value))}>
            <option value={20}>Top 20</option>
            <option value={30}>Top 30</option>
            <option value={50}>Top 50</option>
          </select>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={styles.toolLabel}>정렬</span>
          <select className={styles.toolSelect} value={sortBy} onChange={e => setSortBy(e.target.value)}>
            <option value="ignition">Ignition 우선</option>
            <option value="bias_abs">Bias 강도</option>
            <option value="bias_neg">Long 과밀 (하락 위험)</option>
            <option value="bias_pos">Short 과밀 (상승 위험)</option>
            <option value="oi_change">OI 변화율</option>
            <option value="volume">24h 거래량</option>
            <option value="symbol">심볼명</option>
          </select>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={styles.toolLabel}>필터</span>
          <select className={styles.toolSelect} value={filterBy} onChange={e => setFilterBy(e.target.value)}>
            <option value="all">전체</option>
            <option value="ignited">Ignited만</option>
            <option value="strong_bias">강한 Bias만 (|60|+)</option>
          </select>
        </div>
        <div className="flex items-center gap-1.5 ml-auto">
          <span className={styles.toolLabel}>업데이트</span>
          <span style={{ fontSize: 11, color: '#a0a0a8' }}>{lastUpdate}</span>
        </div>
      </section>

      {/* Symbol Grid */}
      <section style={{ padding: '12px 20px 40px 20px' }}>
        {displaySymbols.length === 0 ? (
          <div style={{ color: '#40404a', fontStyle: 'italic', fontSize: 11, textAlign: 'center', padding: 40 }}>
            {trackedRef.current.length === 0
              ? <><span className={styles.spin} /> Binance Futures 데이터 로딩 중...</>
              : '조건에 맞는 심볼 없음'}
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 10 }}>
            {displaySymbols.map(sym => {
              const s = symbolsRef.current.get(sym);
              if (!s) return null;
              return <SymbolCard key={sym} s={s} config={config} />;
            })}
          </div>
        )}
      </section>

      {/* Status Bar */}
      <div className={styles.statusBar}>
        <div className="flex gap-1.5">
          <span style={{ color: '#40404a' }}>심볼:</span>
          <span style={{ color: '#a0a0a8', fontWeight: 600 }}>{trackedRef.current.length}</span>
        </div>
        <div className="flex gap-1.5">
          <span style={{ color: '#40404a' }}>청산 수신:</span>
          <span style={{ color: '#a0a0a8', fontWeight: 600 }}>{statsRef.current.liqCount}</span>
        </div>
        <div className="flex gap-1.5">
          <span style={{ color: '#40404a' }}>청산액 (5분):</span>
          <span style={{ color: '#a0a0a8', fontWeight: 600 }}>{fmtUsd(totalLiqValue)}</span>
        </div>
        <div className="flex gap-1.5">
          <span style={{ color: '#40404a' }}>OI 갱신:</span>
          <span style={{ color: '#a0a0a8', fontWeight: 600 }}>{sbOiUpdate}</span>
        </div>
        <div className="flex gap-1.5">
          <span style={{ color: '#40404a' }}>L/S 갱신:</span>
          <span style={{ color: '#a0a0a8', fontWeight: 600 }}>{sbLsUpdate}</span>
        </div>
        <div className="flex gap-1.5">
          <span style={{ color: '#40404a' }}>재연결:</span>
          <span style={{ color: '#a0a0a8', fontWeight: 600 }}>{statsRef.current.reconnects}</span>
        </div>
      </div>

      {/* Settings Modal */}
      {showSettings && (
        <div
          className="fixed inset-0 z-[1000] flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
          onClick={e => { if (e.target === e.currentTarget) setShowSettings(false); }}
        >
          <div className={styles.modal}>
            <div className={styles.modalTitle}>⚙ Pressure Map 설정</div>

            <div style={{ marginBottom: 16 }}>
              <div className={styles.modalSectionHead}>
                레버리지 티어 가중치
                <span className={styles.helpIcon} title="포지션 레버리지 분포 추정. 합계 불일치 시 자동 정규화.">?</span>
              </div>
              {[['cfgLev25', '25x 가중치', cfgLev25Ref, '0.30'],
                ['cfgLev50', '50x 가중치', cfgLev50Ref, '0.40'],
                ['cfgLev100', '100x 가중치', cfgLev100Ref, '0.30']].map(([, label, ref, def]) => (
                <div key={label as string} className={styles.configRow}>
                  <label>{label as string}</label>
                  <input ref={ref as React.RefObject<HTMLInputElement>} type="number" className={styles.configInput}
                    min={0} max={1} step={0.05} defaultValue={def as string} />
                </div>
              ))}
            </div>

            <div style={{ marginBottom: 16 }}>
              <div className={styles.modalSectionHead}>Ignition 임계값</div>
              <div className={styles.configRow}>
                <label>σ 배수 (3.0 = 평균 대비 3σ 초과 시 경보)</label>
                <input ref={cfgSigmaRef} type="number" className={styles.configInput} min={1.5} max={5} step={0.1} defaultValue="3.0" />
              </div>
              <div className={styles.configRow}>
                <label>최소 청산액 (USD)</label>
                <input ref={cfgMinLiqRef} type="number" className={styles.configInput} min={10000} max={10000000} step={10000} defaultValue="100000" />
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <div className={styles.modalSectionHead}>Direction Bias 가중치</div>
              {[['Funding Rate 가중치', cfgWFundRef, '0.4'],
                ['L/S Ratio 가중치', cfgWLSRef, '0.3'],
                ['OI Delta 가중치', cfgWOIRef, '0.3']].map(([label, ref, def]) => (
                <div key={label as string} className={styles.configRow}>
                  <label>{label as string}</label>
                  <input ref={ref as React.RefObject<HTMLInputElement>} type="number" className={styles.configInput}
                    min={0} max={1} step={0.1} defaultValue={def as string} />
                </div>
              ))}
            </div>

            <div className="flex gap-2 justify-end mt-5">
              <button className={styles.btn} onClick={resetDefaults}>기본값 복원</button>
              <button className={`${styles.btn} ${styles.btnActive}`} onClick={saveSettings}>저장 & 닫기</button>
            </div>
          </div>
        </div>
      )}

      {/* Help Modal */}
      {showHelp && (
        <div
          className="fixed inset-0 z-[1000] flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
          onClick={e => { if (e.target === e.currentTarget) setShowHelp(false); }}
        >
          <div className={styles.modal}>
            <div className={styles.modalTitle}>📖 Liquidation Pressure Map 사용법</div>

            <div style={{ marginBottom: 16 }}>
              <div className={styles.modalSectionHead}>이 도구가 하는 일</div>
              <p className={styles.helpText}>Binance Futures의 <b>공개 데이터</b>만으로 현재가 위/아래 어느 구간에 청산 물량이 누적돼 있는지 실시간 시각화합니다. API 키 불필요.</p>
            </div>
            <div style={{ marginBottom: 16 }}>
              <div className={styles.modalSectionHead}>Pressure Bar 읽는 법</div>
              <p className={styles.helpText}>• <span style={{ color: '#ef4444' }}>빨간 바 (왼쪽)</span> = 롱 청산 물량 · 가격 하락 시 터짐</p>
              <p className={styles.helpText}>• <span style={{ color: '#22c55e' }}>초록 바 (오른쪽)</span> = 숏 청산 물량 · 가격 상승 시 터짐</p>
              <p className={styles.helpText}>• ±1%, ±2%, ±5% 세 구간으로 분류</p>
            </div>
            <div style={{ marginBottom: 16 }}>
              <div className={styles.modalSectionHead}>Direction Bias 해석</div>
              <p className={styles.helpText}>• <span style={{ color: '#ef4444' }}>음수</span> = 롱 과밀 → 하락 시 연쇄 청산 위험</p>
              <p className={styles.helpText}>• <span style={{ color: '#22c55e' }}>양수</span> = 숏 과밀 → 숏 스퀴즈 위험</p>
              <p className={styles.helpText}>• |60| 이상이면 강한 신호</p>
            </div>
            <div style={{ marginBottom: 16 }}>
              <div className={styles.modalSectionHead}>Ignition Alert</div>
              <p className={styles.helpText}>청산 속도가 해당 심볼의 평균 대비 <b>3σ 이상</b> 급증하면 발령.</p>
              <p className={styles.helpText} style={{ color: '#f59e0b' }}>⚠ 이 경보가 뜨면 V16/Alpha Hunter 진입 신호를 확인하고 Pressure Bar로 타겟을 설정하세요.</p>
            </div>
            <div style={{ marginBottom: 16 }}>
              <div className={styles.modalSectionHead}>권장 사용 흐름</div>
              <p className={styles.helpText}>1. <b>Alpha Terminal</b>로 구조적 세팅 스크리닝</p>
              <p className={styles.helpText}>2. <b>V16 Alpha Hunter</b>로 진입 트리거 탐지</p>
              <p className={styles.helpText}>3. <b>이 도구</b>로 타겟 가격 + 손절가 확인</p>
            </div>

            <div className="flex justify-end">
              <button className={`${styles.btn} ${styles.btnActive}`} onClick={() => setShowHelp(false)}>닫기</button>
            </div>
          </div>
        </div>
      )}

      {/* Toasts */}
      <div className="fixed bottom-10 right-5 flex flex-col gap-2 z-[2000]" style={{ pointerEvents: 'none' }}>
        {toasts.map(t => (
          <div key={t.id} className={`${styles.toast} ${t.type === 'error' ? styles.toastError : t.type === 'success' ? styles.toastSuccess : ''}`}>
            {t.msg}
          </div>
        ))}
      </div>
    </div>
  );
}
