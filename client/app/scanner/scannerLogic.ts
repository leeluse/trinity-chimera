export const CONFIG = {
  API_BASE: 'https://fapi.binance.com',
  BTC_SYMBOL: 'BTCUSDT',
  ETH_SYMBOL: 'ETHUSDT',
  MIN_QUOTE_VOLUME: 2_000_000,
  PHASE1_TOP_N: 70,
  BATCH_SIZE: 15,
  BATCH_DELAY_MS: 300,
  TOP_N_DISPLAY: 50,
  AUTO_REFRESH_MS: 120000,
};

export const MODE_WEIGHTS: Record<string, Record<string, number>> = {
  'DAY': { momentum: 0.15, volume: 0.20, breakout: 0.10, compression: 0.15, funding: 0.10, oi: 0.15, capitulation: 0.05, early: 0.10 },
  'SWING': { momentum: 0.25, volume: 0.10, breakout: 0.20, compression: 0.10, funding: 0.10, oi: 0.10, capitulation: 0.05, early: 0.10 },
  'CONTRA': { momentum: 0.0, volume: 0.10, breakout: 0.05, compression: 0.05, funding: 0.30, oi: 0.15, capitulation: 0.35, early: 0.0 },
};

export const PERSIST_MAX = 5;
export const PERSIST_KEY = 'nahonja_scanner_history';

// Formatting utilities
export const fmt = {
  price: (v: number | null) => {
    if (v == null) return '—';
    const n = Number(v);
    if (n >= 1000) return n.toLocaleString('en-US', { maximumFractionDigits: 2 });
    if (n >= 1) return n.toFixed(3);
    if (n >= 0.01) return n.toFixed(4);
    if (n >= 0.0001) return n.toFixed(6);
    return n.toExponential(2);
  },
  pct: (v: number | null, decimals = 2) => {
    if (v == null || isNaN(v)) return '—';
    const n = Number(v);
    const s = n.toFixed(decimals);
    return (n >= 0 ? '+' : '') + s + '%';
  },
  multiplier: (v: number | null, decimals = 1) => {
    if (v == null || isNaN(v)) return '—';
    return Number(v).toFixed(decimals) + 'x';
  },
  time: (date: Date) => {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  }
};

const SECTOR_MAP: Record<string, string[]> = {
  'AI/BigData': ['TAO', 'RENDER', 'FET', 'AGIX', 'OCEAN', 'WLD', 'ARKM', 'IQ', 'PHB', 'GRT', 'RNDR', 'NFP', 'AI'],
  'Meme': ['DOGE', 'SHIB', 'PEPE', 'WIF', 'BONK', 'FLOKI', 'MEME', 'BOME', 'MYRO', 'TURBO', 'PEOPLE'],
  'RWA': ['ONDO', 'MKR', 'LINK', 'SNX', 'POLYX', 'TRU', 'PENDLE', 'OM', 'CFG', 'TOKEN'],
  'DePin': ['FIL', 'MOBILE', 'IOTX', 'AR', 'HNT', 'ICP', 'HONEY', 'AKT'],
  'L1/L2': ['BTC', 'ETH', 'SOL', 'AVAX', 'OP', 'ARB', 'SEI', 'SUI', 'APT', 'TIA', 'INJ', 'MATIC', 'ADA', 'DOT'],
  'DeFi': ['UNI', 'AAVE', 'MKR', 'RUNE', 'CRV', 'CVX', 'LDO', 'SSV', 'RPL', 'COMP', 'SNX', 'CAKE'],
  'GameFi': ['GALA', 'IMX', 'ILV', 'SAND', 'MANA', 'BEAMX', 'PIXEL', 'PORTAL', 'BIGTIME', 'AXS', 'YGG'],
  'SolanaECO': ['SOL', 'JUP', 'JTO', 'PYTH', 'RAY', 'FIDA', 'BONK', 'WIF', 'BOME'],
  'BRC20/BTC': ['ORDI', 'SATS', 'STX', 'BADGER', 'RIF']
};

export function getSector(symbol: string) {
  for (const [sector, tokens] of Object.entries(SECTOR_MAP)) {
    if (tokens.some(t => symbol === `${t}USDT`)) return sector;
  }
  return '—';
}

export const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

export async function fetchJson(url: string, retries = 2) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const r = await fetch(url);
      if (r.status === 429) {
        await sleep(1000 * (attempt + 1));
        continue;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (e) {
      if (attempt === retries) throw e;
      await sleep(300 * (attempt + 1));
    }
  }
}

export async function batchFetch<T, R>(items: T[], mapper: (item: T) => Promise<R>, batchSize = CONFIG.BATCH_SIZE, delayMs = CONFIG.BATCH_DELAY_MS, onProgress?: (done: number, total: number) => void) {
  const results: R[] = [];
  for (let i = 0; i < items.length; i += batchSize) {
    const slice = items.slice(i, i + batchSize);
    const batch = await Promise.all(slice.map(item => mapper(item).catch(() => null as any)));
    results.push(...batch);
    if (onProgress) onProgress(Math.min(i + batchSize, items.length), items.length);
    if (i + batchSize < items.length) await sleep(delayMs);
  }
  return results.filter(Boolean);
}

// Technical Indicators
export function calcRSI(closes: number[], period = 14) {
  if (closes.length <= period) return 50;
  let gains = 0, losses = 0;
  for (let i = 1; i <= period; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff > 0) gains += diff; else losses -= diff;
  }
  let avgGain = gains / period, avgLoss = losses / period;
  for (let i = period + 1; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff > 0) {
      avgGain = (avgGain * (period - 1) + diff) / period;
      avgLoss = (avgLoss * (period - 1)) / period;
    } else {
      avgGain = (avgGain * (period - 1)) / period;
      avgLoss = (avgLoss * (period - 1) + (-diff)) / period;
    }
  }
  if (avgLoss === 0) return 100;
  const rs = avgGain / avgLoss;
  return 100 - (100 / (1 + rs));
}

export function calcBBWidth(closes: number[], period = 20, mult = 2) {
  if (closes.length < period) return null;
  const recent = closes.slice(-period);
  const mean = recent.reduce((a, b) => a + b, 0) / period;
  const variance = recent.reduce((a, b) => a + (b - mean) ** 2, 0) / period;
  const stddev = Math.sqrt(variance);
  return ((mean + mult * stddev) - (mean - mult * stddev)) / mean;
}

// Signals
export function sigMomentum(token: any, btc: any) {
  const rs24 = token.change24 - btc.change24;
  const rs7d = (token.change7d || 0) - (btc.change7d || 0);
  let s = 0;
  s += Math.max(0, Math.min(50, rs24 * 5));
  s += Math.max(0, Math.min(40, rs7d * 2));
  if (token.change24 < -2) s *= 0.3;
  return { score: Math.max(0, Math.min(100, s)), note: `RS24:${rs24.toFixed(1)} RS7:${rs7d.toFixed(1)}` };
}

export function sigVolume(token: any) {
  if (!token.volRatio || token.volRatio < 1) return { score: 0 };
  const s = Math.min(100, Math.log2(token.volRatio) * 35);
  return { score: Math.max(0, s), note: `${token.volRatio.toFixed(2)}x` };
}

export function sigBreakout(token: any) {
  if (!token.dailyCloses || token.dailyCloses.length < 15) return { score: 0 };
  const high30 = Math.max(...token.dailyCloses.slice(-30));
  const distance = (high30 - token.price) / high30;
  if (distance > 0.15) return { score: 0, note: `far (${(distance * 100).toFixed(1)}% below)` };
  let s = Math.max(0, 60 - distance * 400);
  if (token.volRatio && token.volRatio > 1.3) s += Math.min(40, (token.volRatio - 1) * 30);
  return { score: Math.max(0, Math.min(100, s)), note: `${(distance * 100).toFixed(1)}% below 30d high` };
}

export function sigCompression(token: any) {
  if (!token.hourlyCloses || token.hourlyCloses.length < 40) return { score: 0 };
  const widths = [];
  for (let i = 20; i < token.hourlyCloses.length; i++) {
    const w = calcBBWidth(token.hourlyCloses.slice(0, i + 1), 20);
    if (w != null) widths.push(w);
  }
  if (widths.length < 10) return { score: 0 };
  const current = widths[widths.length - 1];
  const sorted = [...widths].sort((a, b) => a - b);
  const rank = sorted.indexOf(current);
  const pct = rank / (sorted.length - 1);
  let s = Math.max(0, 100 - pct * 250);

  const recent = token.hourlyCloses.slice(-24);
  const rHigh = Math.max(...recent);
  const rLow = Math.min(...recent);
  const rangePct = (rHigh - rLow) / ((rHigh + rLow) / 2);
  const isTrending = Math.abs(token.change24 || 0) > 4;
  if (isTrending) s *= 0.3;
  if (rangePct > 0.10) s *= 0.6;

  return { score: s, note: `BB ${(pct * 100).toFixed(0)}%ile · 범위 ${(rangePct * 100).toFixed(1)}%` };
}

export function sigFunding(token: any) {
  if (token.funding == null) return { score: 0 };
  const abs = Math.abs(token.funding);
  const s = Math.min(100, abs * 70000);
  const dir = token.funding > 0 ? '롱 과열' : '숏 과열';
  return { score: s, note: `${(token.funding * 100).toFixed(4)}% ${dir}` };
}

export function sigOI(token: any) {
  if (token.oiChange24 == null) return { score: 0 };
  const price24 = token.change24;
  const oi24 = token.oiChange24;
  let s = 0, note = '';
  const bigOI = oi24 > 15;
  const flatPrice = Math.abs(price24) < 3;
  if (bigOI && flatPrice) { s = 75; note = `OI +${oi24.toFixed(1)}% (축적)`; }
  else if (oi24 > 20 && price24 < -2) { s = 70; note = `OI +${oi24.toFixed(1)}% 숏 빌드업`; }
  else if (oi24 > 10 && price24 > 3) { s = 35; note = `OI +${oi24.toFixed(1)}% 트렌드 확정`; }
  else if (oi24 < -10 && price24 > 3) { s = 40; note = `OI ${oi24.toFixed(1)}% 랠리(차익)`; }
  else if (Math.abs(oi24) > 8) { s = Math.min(60, Math.abs(oi24) * 3); note = `OI ${oi24 > 0 ? '+' : ''}${oi24.toFixed(1)}%`; }
  return { score: Math.max(0, Math.min(100, s)), note };
}

export function sigCapitulation(token: any) {
  if (!token.hourlyCloses || token.hourlyCloses.length < 24) return { score: 0 };
  const rsi = calcRSI(token.hourlyCloses, 14);
  let biggestDrop = 0;
  for (let i = 1; i < token.hourlyCloses.length; i++) {
    const d = (token.hourlyCloses[i] - token.hourlyCloses[i - 1]) / token.hourlyCloses[i - 1];
    if (d < biggestDrop) biggestDrop = d;
  }
  const recent = token.hourlyCloses.slice(-6);
  const recentLow = Math.min(...recent);
  const bounceFromLow = (token.price - recentLow) / recentLow;
  let s = 0;
  if (rsi < 35 && biggestDrop < -0.05) {
    s = 40;
    s += Math.min(30, (35 - rsi) * 2);
    if (bounceFromLow > 0 && bounceFromLow < 0.04) s += 20;
    if (token.funding != null && token.funding < -0.0002) s += 10;
  }
  return { score: Math.max(0, Math.min(100, s)), note: `RSI ${rsi.toFixed(0)}, 수직낙폭 ${(biggestDrop * 100).toFixed(1)}%` };
}

export function sigEarly(token: any) {
  if (!token.change1h || token.change24 == null) return { score: 0 };
  const h1 = token.change1h;
  const h4 = token.change4h || 0;
  const h24 = token.change24;
  let s = 0;
  if (h1 > 1.5 && h24 < 6) s += Math.min(40, h1 * 15);
  if (h4 > 1 && h4 < 10) s += Math.min(30, h4 * 6);
  if (token.volRatio && token.volRatio > 1.3) s += 20;
  if (h24 > 15) s *= 0.2;
  return { score: Math.max(0, Math.min(100, s)), note: `1h ${h1.toFixed(1)}% / 4h ${h4.toFixed(1)}%` };
}

export function computeSectorMomentum(tickers: any[]) {
  const bySector: Record<string, any> = {};
  tickers.forEach(t => {
    const s = getSector(t.symbol);
    if (s === '—') return;
    if (!bySector[s]) bySector[s] = { tokens: [], sum24: 0, sum7d: 0, count: 0 };
    bySector[s].tokens.push(t.symbol);
    bySector[s].sum24 += (t.change24 || 0);
    bySector[s].sum7d += (t.change7d || 0);
    bySector[s].count++;
  });
  for (const s in bySector) {
    const v = bySector[s];
    v.avg24 = v.sum24 / v.count;
    v.avg7d = v.sum7d / v.count;
    v.momentum = v.avg24 + v.avg7d * 0.4;
  }
  const ranked = Object.entries(bySector)
    .filter(([_, v]) => v.count >= 2)
    .sort((a, b) => b[1].momentum - a[1].momentum);
  return { bySector, ranked };
}

export function adaptiveWeights(mode: string, regime: string, useAdaptive: boolean) {
  const base = { ...MODE_WEIGHTS[mode] };
  if (!useAdaptive) return base;

  if (regime === 'RISK-OFF' || regime === 'WEAK') {
    base.momentum *= 0.55; base.breakout *= 0.6; base.early *= 0.5;
    base.capitulation *= 1.6; base.funding *= 1.35; base.oi *= 1.15; base.compression *= 1.2;
  } else if (regime === 'RISK-ON') {
    base.momentum *= 1.25; base.breakout *= 1.2; base.early *= 1.35;
    base.volume *= 1.15; base.capitulation *= 0.4;
  } else if (regime === 'BROAD') {
    base.momentum *= 1.1; base.breakout *= 1.1;
  }
  return base;
}

export function computeComposite(token: any, btc: any, mode: string, regimeLabel: string, regimeAdaptive: boolean, topSectors: Set<string>, botSectors: Set<string>) {
  const signals = {
    momentum: sigMomentum(token, btc),
    volume: sigVolume(token),
    breakout: sigBreakout(token),
    compression: sigCompression(token),
    funding: sigFunding(token),
    oi: sigOI(token),
    capitulation: sigCapitulation(token),
    early: sigEarly(token),
  };

  let pumpFlagged = false;
  if (token.change24 > 25) {
    signals.momentum.score *= 0.25;
    signals.breakout.score *= 0.25;
    signals.early.score *= 0.10;
    pumpFlagged = true;
  } else if (token.change24 < -25) {
    signals.capitulation.score = Math.min(100, signals.capitulation.score * 1.3);
  }

  const weights = adaptiveWeights(mode, regimeLabel, regimeAdaptive);
  let weightedSum = 0, totalWeight = 0;
  for (const k in signals) {
    weightedSum += (signals as any)[k].score * (weights as any)[k];
    totalWeight += (weights as any)[k] * 100;
  }
  let composite = totalWeight > 0 ? (weightedSum / totalWeight) * 100 : 0;

  const strong = Object.values(signals).filter(s => s.score > 50).length;
  if (strong >= 4) composite *= 1.30;
  else if (strong >= 3) composite *= 1.20;
  else if (strong >= 2) composite *= 1.10;

  if (signals.momentum.score > 60 && signals.capitulation.score > 60) composite *= 0.7;

  const sector = getSector(token.symbol);
  let narrativeMult = 1.0;
  if (sector !== '—') {
    if (topSectors.has(sector)) narrativeMult = 1.15;
    else if (botSectors.has(sector)) narrativeMult = 0.90;
  }
  composite *= narrativeMult;

  return {
    score: Math.max(0, Math.min(100, composite)),
    signals,
    strongCount: strong,
    pumpFlagged,
    narrativeMult,
    sector,
  };
}
