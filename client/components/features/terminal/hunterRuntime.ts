/* eslint-disable */

export type HunterSortMode = 'total' | 'cross' | 'sqz' | 'whale';

export interface HunterWsState {
  bn: boolean;
  okx: boolean;
  bybit: boolean;
  bitget: boolean;
}

export interface HunterSummary {
  snipers: number;
  s2plus: number;
  s1: number;
  bias: string;
  pre: number;
}

export interface HunterRegime {
  ready: boolean;
  btcAltDelta: number;
  avgFunding: number;
  oiExpansionRate: number;
  longFlowRatio: number;
}

export interface HunterSignalTag {
  n: string;
  d: number;
  cat: 'setup' | 'trigger' | 'momentum';
}

export interface HunterRow {
  sym: string;
  full: string;
  price: number;
  score: number;
  stage: number;
  latchDir: number;
  latchRatio: number;
  cvd: number;
  mult: number;
  chg9: number | null;
  regimeMult: number;
  setupCount: number;
  sig: HunterSignalTag[];
  aGradeCount: number;
  aGradeDir: number;
  aGradeActive: boolean;
  pinned: boolean;
}

export interface HunterPreSignal {
  sym: string;
  type: string;
  dir: number;
  ts: number;
  title: string;
  desc: string;
  score: number;
}

export interface HunterLeaderboardItem {
  sym: string;
  total: number;
  scoreSum: number;
  absSum: number;
  tags: Record<string, number>;
  stage: number;
  aGradeCount: number;
  aGradeDir: number;
}

export interface HunterRuntimeSnapshot {
  running: boolean;
  muted: boolean;
  focusMode: boolean;
  frozen: boolean;
  sortMode: HunterSortMode;
  statusText: string;
  ws: HunterWsState;
  summary: HunterSummary;
  regime: HunterRegime;
  rows: HunterRow[];
  preSignals: HunterPreSignal[];
  leaderboard: HunterLeaderboardItem[];
  updatedAt: number;
}

export interface HunterRuntimeApi {
  startSystem: () => Promise<void>;
  stopSystem: () => void;
  toggleMute: () => void;
  toggleFocus: () => void;
  toggleFreeze: () => void;
  setSort: (mode: HunterSortMode) => void;
  togglePin: (sym: string) => void;
}

const C = {
  radarVel: 2.5,
  radarMinVol: 30000,
  minQuoteVol: 500000,
  maxSnipers: 25,
  velStreak: 3,

  absWindow: 10,
  crossMs: 3000,
  alertCD: 5000,

  fundingExt: 0.0005,
  fundingExtStrong: 0.0007,
  miExt: 0.001,
  oiBuildPct: 0.015,
  oiBuildPriceFlat: 0.003,

  preCardMax: 40,
  preCardTtl: 600000,
  regimeThrottle: 5000,
  sortDelay: 5000,
  warmupMs: 30000,

  latchDur: { 1: 60000, 2: 45000, 3: 30000 },
  hardResetThresh: 30,
};

const TIER = {
  A: { cvdConsMin: 200000, whaleMin: 200000, spoofDrop: 0.5, cvdConsCD: 20000, label: 'A' },
  B: { cvdConsMin: 80000, whaleMin: 80000, spoofDrop: 0.6, cvdConsCD: 15000, label: 'B' },
  C: { cvdConsMin: 30000, whaleMin: 30000, spoofDrop: 0.65, cvdConsCD: 12000, label: 'C' },
};

function cloneSnapshot(s: HunterRuntimeSnapshot): HunterRuntimeSnapshot {
  return {
    ...s,
    ws: { ...s.ws },
    summary: { ...s.summary },
    regime: { ...s.regime },
    rows: s.rows.map((r) => ({ ...r, sig: r.sig.map((x) => ({ ...x })) })),
    preSignals: s.preSignals.map((p) => ({ ...p })),
    leaderboard: s.leaderboard.map((l) => ({ ...l, tags: { ...l.tags } })),
  };
}

export function mountHunterRuntime(onUpdate: (snapshot: HunterRuntimeSnapshot) => void) {
  let running = false;
  let muted = false;
  let focusMode = false;
  let isFrozen = false;
  let sortMode: HunterSortMode = 'total';

  let gWs: WebSocket | null = null;
  let bnWs: WebSocket | null = null;
  let oxWs: WebSocket | null = null;
  let byWs: WebSocket | null = null;
  let bgWs: WebSocket | null = null;

  let scanIv: any = null;
  let decayIv: any = null;
  let fundIv: any = null;
  let oiIv: any = null;
  let lsrIv: any = null;
  let regimeIv: any = null;

  const M: Record<string, any> = {};
  const SD: Record<string, any> = {};
  const OI: Record<string, any> = {};
  const MI: Record<string, number> = {};
  const LSR: Record<string, any> = {};
  const FR: Record<string, number> = {};
  const P9: Record<string, number> = {};

  let sigHist: any[] = [];
  const actAlerts = new Set<string>();
  let currentTopCoins = new Set<string>();
  let currentLeaderboard: Record<string, any> = {};

  const pinnedSyms = new Set<string>();
  const aGradeState: Record<string, any> = {};
  let lastSortTime = 0;
  let displayedOrder: any[] = [];

  const preSigHistory: any[] = [];
  const preSigCooldown: Record<string, number> = {};

  let lastRegimeUpdate = 0;
  const regimeState = { btcAltDelta: 0, avgFunding: 0, ready: false };

  const ui: HunterRuntimeSnapshot = {
    running: false,
    muted: false,
    focusMode: false,
    frozen: false,
    sortMode: 'total',
    statusText: '대기중',
    ws: { bn: false, okx: false, bybit: false, bitget: false },
    summary: { snipers: 0, s2plus: 0, s1: 0, bias: '—', pre: 0 },
    regime: { ready: false, btcAltDelta: 0, avgFunding: 0, oiExpansionRate: 0, longFlowRatio: 50 },
    rows: [],
    preSignals: [],
    leaderboard: [],
    updatedAt: Date.now(),
  };

  function emit() {
    ui.running = running;
    ui.muted = muted;
    ui.focusMode = focusMode;
    ui.frozen = isFrozen;
    ui.sortMode = sortMode;
    ui.updatedAt = Date.now();
    onUpdate(cloneSnapshot(ui));
  }

  function getSymTier(sym: string) {
    const v = M[sym] ? M[sym].totalQuoteVol : 0;
    if (v > 50000000) return TIER.A;
    if (v > 10000000) return TIER.B;
    return TIER.C;
  }

  const sV = (a: any, b: any) => {
    const v = parseFloat(a) * parseFloat(b);
    return isFinite(v) ? v : 0;
  };

  function setWs(id: 'wsBn' | 'wsOkx' | 'wsByb' | 'wsBg', on: boolean) {
    if (id === 'wsBn') ui.ws.bn = on;
    if (id === 'wsOkx') ui.ws.okx = on;
    if (id === 'wsByb') ui.ws.bybit = on;
    if (id === 'wsBg') ui.ws.bitget = on;
    emit();
  }

  function playBeep(f: number) {
    if (muted) return;
    try {
      const Ctx = window.AudioContext || (window as any).webkitAudioContext;
      if (!Ctx) return;
      const c = new Ctx();
      const o = c.createOscillator();
      const g = c.createGain();
      o.connect(g);
      g.connect(c.destination);
      o.frequency.value = f;
      g.gain.value = 0.08;
      o.start();
      o.stop(c.currentTime + 0.1);
      o.onended = () => {
        try {
          void c.close();
        } catch (_e) {}
      };
    } catch (_e) {}
  }

  function clearTimer(refName: 'scanIv' | 'decayIv' | 'fundIv' | 'oiIv' | 'lsrIv' | 'regimeIv') {
    const value = { scanIv, decayIv, fundIv, oiIv, lsrIv, regimeIv }[refName];
    if (value) clearInterval(value);
    if (refName === 'scanIv') scanIv = null;
    if (refName === 'decayIv') decayIv = null;
    if (refName === 'fundIv') fundIv = null;
    if (refName === 'oiIv') oiIv = null;
    if (refName === 'lsrIv') lsrIv = null;
    if (refName === 'regimeIv') regimeIv = null;
  }

  function closeWs(ws: WebSocket | null) {
    if (!ws) return;
    try {
      ws.onopen = null;
      ws.onmessage = null;
      ws.onclose = null;
      ws.onerror = null;
      ws.close();
    } catch (_e) {}
  }

  function stopSystem() {
    running = false;
    ui.statusText = '중지됨';

    clearTimer('scanIv');
    clearTimer('decayIv');
    clearTimer('fundIv');
    clearTimer('oiIv');
    clearTimer('lsrIv');
    clearTimer('regimeIv');

    closeWs(gWs);
    closeWs(bnWs);
    closeWs(oxWs);
    closeWs(byWs);
    closeWs(bgWs);

    gWs = null;
    bnWs = null;
    oxWs = null;
    byWs = null;
    bgWs = null;

    ui.ws.bn = false;
    ui.ws.okx = false;
    ui.ws.bybit = false;
    ui.ws.bitget = false;
    emit();
  }

  async function fetch9am(sym: string) {
    try {
      const r = await fetch('https://fapi.binance.com/fapi/v1/klines?symbol=' + sym + '&interval=1d&limit=1');
      const d = await r.json();
      if (d && d[0]) P9[sym] = parseFloat(d[0][1]);
    } catch (_e) {}
  }

  function subBn(s: string) {
    if (bnWs && bnWs.readyState === 1) {
      bnWs.send(
        JSON.stringify({
          method: 'SUBSCRIBE',
          params: [s.toLowerCase() + '@aggTrade', s.toLowerCase() + '@depth10@100ms', s.toLowerCase() + '@forceOrder'],
          id: Date.now(),
        }),
      );
    }
  }

  function unBn(s: string) {
    if (bnWs && bnWs.readyState === 1) {
      bnWs.send(
        JSON.stringify({
          method: 'UNSUBSCRIBE',
          params: [s.toLowerCase() + '@aggTrade', s.toLowerCase() + '@depth10@100ms', s.toLowerCase() + '@forceOrder'],
          id: Date.now(),
        }),
      );
    }
  }

  function subOx(s: string) {
    if (oxWs && oxWs.readyState === 1) {
      oxWs.send(
        JSON.stringify({ op: 'subscribe', args: [{ channel: 'trades', instId: s.replace('USDT', '') + '-USDT-SWAP' }] }),
      );
    }
  }

  function unOx(s: string) {
    if (oxWs && oxWs.readyState === 1) {
      oxWs.send(
        JSON.stringify({ op: 'unsubscribe', args: [{ channel: 'trades', instId: s.replace('USDT', '') + '-USDT-SWAP' }] }),
      );
    }
  }

  function subBy(s: string) {
    if (byWs && byWs.readyState === 1) {
      byWs.send(JSON.stringify({ op: 'subscribe', args: ['publicTrade.' + s] }));
    }
  }

  function unBy(s: string) {
    if (byWs && byWs.readyState === 1) {
      byWs.send(JSON.stringify({ op: 'unsubscribe', args: ['publicTrade.' + s] }));
    }
  }

  function subBg(s: string) {
    if (bgWs && bgWs.readyState === 1) {
      bgWs.send(
        JSON.stringify({
          op: 'subscribe',
          args: [
            { instType: 'USDT-FUTURES', channel: 'trade', instId: s },
            { instType: 'USDT-FUTURES', channel: 'books5', instId: s },
          ],
        }),
      );
    }
  }

  function unBg(s: string) {
    if (bgWs && bgWs.readyState === 1) {
      bgWs.send(
        JSON.stringify({
          op: 'unsubscribe',
          args: [
            { instType: 'USDT-FUTURES', channel: 'trade', instId: s },
            { instType: 'USDT-FUTURES', channel: 'books5', instId: s },
          ],
        }),
      );
    }
  }

  function trackSig(sym: string, type: string, score: number) {
    const key = type + '_' + sym;
    if (actAlerts.has(key)) return;
    actAlerts.add(key);
    setTimeout(() => actAlerts.delete(key), C.alertCD);

    sigHist.push({ sym, type, time: Date.now(), score });
    if (!isFrozen) updateRank();
  }

  function onLiq(d: any) {
    const o = d?.o;
    if (!o) return;

    const sym = o.s || o.S;
    const sd = SD[sym];
    if (!sd) return;

    const now = Date.now();
    sd.recentLiq = { side: o.S, vol: sV(o.p, o.q), ts: now };
    if (o.S === 'BUY') sd.liqBuyEv.push(now);
    else sd.liqSellEv.push(now);
  }

  function checkCross(sym: string, ts: number) {
    const sd = SD[sym];
    if (!sd) return;

    const hasS =
      (sd.lastSpoofBn > 0 && Math.abs(ts - sd.lastSpoofBn) < C.crossMs) ||
      (sd.lastSpoofBg > 0 && Math.abs(ts - sd.lastSpoofBg) < C.crossMs);
    const hasA = sd.lastAbs > 0 && Math.abs(ts - sd.lastAbs) < C.crossMs;

    if (hasS && hasA) {
      sd.scores.cross = 30;
      trackSig(sym, 'cross', 85);
      playBeep(880);

      sd.protectedUntil = Date.now() + 300000;
      sd.lastSpoofBn = 0;
      sd.lastSpoofBg = 0;
      sd.lastAbs = 0;
    }
  }

  function checkAbs(sym: string) {
    const sd = SD[sym];
    if (!sd || sd.priceHist.length < C.absWindow) return;

    const m = M[sym];
    const now = Date.now();
    if (now < sd.warmupUntil) return;
    if (now - sd.lastAbs < C.alertCD) return;

    const pS = sd.priceHist[sd.priceHist.length - C.absWindow];
    const cvdN = sd.cvdBn + sd.cvdOkx + sd.cvdBybit + sd.cvdBitget;
    const ci = sd.cvdTotalHist.length - C.absWindow;
    if (ci < 0) return;
    const cvdS = sd.cvdTotalHist[ci];

    const tM = (dir: number) => (m.trend5m * dir > 0.001 ? 1.5 : m.trend5m * dir < -0.001 ? 0.5 : 1.0);

    if (m.price < pS * 0.999 && cvdN > cvdS) {
      sd.scores.abs = Math.round(25 * tM(1));
      sd.lastAbs = now;
      sd.absDir = 1;
      trackSig(sym, 'abs', sd.scores.abs);
      checkCross(sym, now);
    } else if (m.price > pS * 1.001 && cvdN < cvdS) {
      sd.scores.abs = Math.round(-25 * tM(-1));
      sd.lastAbs = now;
      sd.absDir = -1;
      trackSig(sym, 'abs', sd.scores.abs);
      checkCross(sym, now);
    }
  }

  function onTrade(d: any) {
    const sym = d.s;
    const sd = SD[sym];
    if (!sd) return;

    const vol = sV(d.p, d.q);
    const p = parseFloat(d.p);

    sd.tickVolSum += vol;
    M[sym].price = p;

    if (d.m) sd.cvdBn -= vol;
    else sd.cvdBn += vol;

    sd.tradeCount++;
    const alpha = 2 / (Math.min(sd.tradeCount, 200) + 1);
    sd.tradeVolEma = sd.tradeVolEma * (1 - alpha) + vol * alpha;

    const wMin = sd.tier ? sd.tier.whaleMin : 50000;
    if (vol >= Math.max(wMin, sd.tradeVolEma * 20)) {
      const now = Date.now();
      const isBuy = !d.m;
      sd.whaleEvents.push({ ts: now, vol, isBuy });

      if (now - sd.lastWhale > C.alertCD) {
        sd.scores.whale = (isBuy ? 1 : -1) * 20;
        sd.lastWhale = now;
        trackSig(sym, 'whale', sd.scores.whale);
        playBeep(770);
      }
    }

    checkAbs(sym);
  }

  function onDepth(d: any) {
    const sym = d.s;
    const sd = SD[sym];
    if (!sd || !d.b || !d.a) return;

    const m = M[sym];
    const now = Date.now();

    const bV = d.b.reduce((s: number, b: any) => s + sV(b[0], b[1]), 0);
    const aV = d.a.reduce((s: number, a: any) => s + sV(a[0], a[1]), 0);

    if (sd.prevBnBid > 0 && sd.prevBnAsk > 0 && now - sd.lastSpoofBn > C.alertCD) {
      const stab = sd.priceHist.length > 0 && Math.abs(m.price - sd.priceHist[sd.priceHist.length - 1]) / m.price < 0.001;
      const tM = (dir: number) => (m.trend5m * dir > 0.001 ? 1.5 : m.trend5m * dir < -0.001 ? 0.5 : 1.0);
      const drop = sd.tier ? sd.tier.spoofDrop : 0.6;

      if (bV < sd.prevBnBid * drop && stab) {
        sd.scores.spoofBn = Math.round(25 * tM(1));
        sd.lastSpoofBn = now;
        trackSig(sym, 'spoofBn', sd.scores.spoofBn);
        checkCross(sym, now);
      } else if (aV < sd.prevBnAsk * drop && stab) {
        sd.scores.spoofBn = Math.round(-25 * tM(-1));
        sd.lastSpoofBn = now;
        trackSig(sym, 'spoofBn', sd.scores.spoofBn);
        checkCross(sym, now);
      }
    }

    sd.prevBnBid = bV;
    sd.prevBnAsk = aV;
    sd.bnBidVol = bV;
    sd.bnAskVol = aV;
  }

  function openGlobal() {
    gWs = new WebSocket('wss://fstream.binance.com/market/ws/!miniTicker@arr');

    gWs.onopen = () => setWs('wsBn', true);

    gWs.onmessage = (e) => {
      try {
        JSON.parse(e.data).forEach((t: any) => {
          const m = M[t.s];
          if (m) {
            m.price = parseFloat(t.c);
            m.currentVol = parseFloat(t.q);
            m.totalQuoteVol = parseFloat(t.q);
          }
        });
      } catch (_e) {}
    };

    gWs.onclose = () => {
      setWs('wsBn', false);
      if (running) setTimeout(openGlobal, 3000);
    };

    gWs.onerror = () => {
      try {
        gWs?.close();
      } catch (_e) {}
    };
  }

  function openBnSniper() {
    bnWs = new WebSocket('wss://fstream.binance.com/stream');

    bnWs.onopen = () => {
      Object.keys(SD).forEach((k) => {
        subBn(k);
        SD[k].prevBnBid = 0;
        SD[k].prevBnAsk = 0;
      });
    };

    bnWs.onmessage = (e) => {
      try {
        const raw = JSON.parse(e.data);
        if (raw.result !== undefined) return;
        const d = raw.data || raw;

        if (d.e === 'aggTrade') onTrade(d);
        else if (d.e === 'depthUpdate' || (d.b && d.a)) onDepth(d);
        else if (d.e === 'forceOrder' || d.o) onLiq(d);
      } catch (_e) {}
    };

    bnWs.onclose = () => {
      if (running) setTimeout(openBnSniper, 3000);
    };

    bnWs.onerror = () => {
      try {
        bnWs?.close();
      } catch (_e) {}
    };
  }

  function openOkx() {
    oxWs = new WebSocket('wss://ws.okx.com/ws/v5/public');
    let pingIv: any = null;

    oxWs.onopen = () => {
      setWs('wsOkx', true);
      pingIv = setInterval(() => {
        if (oxWs?.readyState === 1) oxWs.send('ping');
      }, 20000);
      Object.keys(SD).forEach((k) => subOx(k));
    };

    oxWs.onmessage = (e) => {
      if (e.data === 'pong') return;
      try {
        const r = JSON.parse(e.data);
        if (r.data && r.arg && r.arg.channel === 'trades') {
          const sym = r.arg.instId.replace('-USDT-SWAP', 'USDT');
          const sd = SD[sym];
          if (sd) {
            r.data.forEach((t: any) => {
              const v = sV(t.sz, t.px);
              if (t.side === 'buy') sd.cvdOkx += v;
              else sd.cvdOkx -= v;
            });
          }
        }
      } catch (_e) {}
    };

    oxWs.onclose = () => {
      setWs('wsOkx', false);
      if (pingIv) clearInterval(pingIv);
      if (running) setTimeout(openOkx, 3000);
    };

    oxWs.onerror = () => {
      try {
        oxWs?.close();
      } catch (_e) {}
    };
  }

  function openBybit() {
    byWs = new WebSocket('wss://stream.bybit.com/v5/public/linear');
    let pingIv: any = null;

    byWs.onopen = () => {
      setWs('wsByb', true);
      pingIv = setInterval(() => {
        if (byWs?.readyState === 1) byWs.send(JSON.stringify({ op: 'ping' }));
      }, 20000);
      Object.keys(SD).forEach((k) => subBy(k));
    };

    byWs.onmessage = (e) => {
      try {
        const r = JSON.parse(e.data);
        if (r.topic && r.topic.startsWith('publicTrade')) {
          const sym = r.topic.split('.')[1];
          const sd = SD[sym];
          if (sd) {
            r.data.forEach((t: any) => {
              const v = sV(t.v, t.p);
              if (t.S === 'Buy') sd.cvdBybit += v;
              else sd.cvdBybit -= v;
            });
          }
        }
      } catch (_e) {}
    };

    byWs.onclose = () => {
      setWs('wsByb', false);
      if (pingIv) clearInterval(pingIv);
      if (running) setTimeout(openBybit, 3000);
    };

    byWs.onerror = () => {
      try {
        byWs?.close();
      } catch (_e) {}
    };
  }

  function openBitget() {
    bgWs = new WebSocket('wss://ws.bitget.com/v2/ws/public');
    let pingIv: any = null;

    bgWs.onopen = () => {
      setWs('wsBg', true);
      pingIv = setInterval(() => {
        if (bgWs?.readyState === 1) bgWs.send('ping');
      }, 20000);

      Object.keys(SD).forEach((k) => {
        subBg(k);
        SD[k].prevBgBid = 0;
        SD[k].prevBgAsk = 0;
      });
    };

    bgWs.onmessage = (e) => {
      if (e.data === 'pong') return;

      try {
        const r = JSON.parse(e.data);
        if (!r.data || !r.arg) return;

        const sym = r.arg.instId;
        const sd = SD[sym];
        if (!sd) return;

        if (r.arg.channel === 'trade') {
          r.data.forEach((t: any) => {
            const v = sV(t.size || t.sz, t.price || t.pr);
            if (t.side === 'buy' || t.side === 'Buy') sd.cvdBitget += v;
            else sd.cvdBitget -= v;
          });
        }

        if (r.arg.channel === 'books5') {
          const now = Date.now();
          if (now - sd.bgDepthTs < 80) return;
          sd.bgDepthTs = now;

          let bV = 0;
          let aV = 0;
          const book = r.data[0];
          if (!book) return;

          (book.bids || []).forEach((b: any) => {
            bV += sV(b[0], b[1]);
          });
          (book.asks || []).forEach((a: any) => {
            aV += sV(a[0], a[1]);
          });

          if (sd.prevBgBid > 0 && sd.prevBgAsk > 0) {
            const m = M[sym];
            const stab = sd.priceHist.length > 0 && Math.abs(m.price - sd.priceHist[sd.priceHist.length - 1]) / m.price < 0.001;
            const tM = (dir: number) => (m.trend5m * dir > 0.001 ? 1.5 : m.trend5m * dir < -0.001 ? 0.5 : 1.0);
            const drop = sd.tier ? sd.tier.spoofDrop : 0.6;

            if (bV < sd.prevBgBid * drop && stab && now - sd.lastSpoofBg > C.alertCD) {
              sd.scores.spoofBg = Math.round(20 * tM(1));
              sd.lastSpoofBg = now;
              trackSig(sym, 'spoofBg', sd.scores.spoofBg);
              checkCross(sym, now);
            } else if (aV < sd.prevBgAsk * drop && stab && now - sd.lastSpoofBg > C.alertCD) {
              sd.scores.spoofBg = Math.round(-20 * tM(-1));
              sd.lastSpoofBg = now;
              trackSig(sym, 'spoofBg', sd.scores.spoofBg);
              checkCross(sym, now);
            }
          }

          sd.prevBgBid = bV;
          sd.prevBgAsk = aV;
          sd.bgBidVol = bV;
          sd.bgAskVol = aV;
        }
      } catch (_e) {}
    };

    bgWs.onclose = () => {
      setWs('wsBg', false);
      if (pingIv) clearInterval(pingIv);
      if (running) setTimeout(openBitget, 3000);
    };

    bgWs.onerror = () => {
      try {
        bgWs?.close();
      } catch (_e) {}
    };
  }

  function getSetupState(sym: string, now: number) {
    const recent = preSigHistory.filter((p) => p.sym === sym && ['oiBuild', 'cvdCons', 'fundExt', 'miDiv'].includes(p.type) && now - p.ts < C.preCardTtl);
    if (!recent.length) return { active: false, dir: 0, count: 0, earliestTs: 0, types: [] as string[] };

    const bullTypes = new Set<string>();
    const bearTypes = new Set<string>();
    let bullEarliest = Infinity;
    let bearEarliest = Infinity;

    recent.forEach((p) => {
      if (p.dir > 0) {
        bullTypes.add(p.type);
        bullEarliest = Math.min(bullEarliest, p.ts);
      } else {
        bearTypes.add(p.type);
        bearEarliest = Math.min(bearEarliest, p.ts);
      }
    });

    const bc = bullTypes.size;
    const brc = bearTypes.size;
    const dir = bc >= brc ? 1 : -1;
    const count = Math.max(bc, brc);
    const earliestTs = dir > 0 ? bullEarliest : bearEarliest;
    const types = dir > 0 ? [...bullTypes] : [...bearTypes];

    return { active: count >= 1, dir, count, earliestTs, types };
  }

  function getRegimeMult(dir: number) {
    if (!regimeState.ready || dir === 0) return 1.0;
    let mult = 1.0;
    const d = regimeState.btcAltDelta;
    const f = regimeState.avgFunding;

    if (dir > 0) {
      if (d > 1.0) mult *= 1.3;
      else if (d < -1.0) mult *= 0.5;

      if (f > 0.03) mult *= 0.6;
      else if (f < -0.03) mult *= 1.4;
    } else {
      if (d < -1.0) mult *= 1.3;
      else if (d > 1.0) mult *= 0.5;

      if (f < -0.03) mult *= 0.6;
      else if (f > 0.03) mult *= 1.4;
    }

    return Math.max(0.3, Math.min(2.0, mult));
  }

  function calcStageScore(sd: any, sym: string, now: number) {
    const s = sd.scores;
    const setupInfo = getSetupState(sym, now);

    const setupRaw = s.oiBuild + s.cvdCons + s.funding;
    const triggerRaw = s.spoofBn + s.spoofBg + s.abs + s.whale + s.cross;
    const momentumRaw = s.tick + s.liq;
    const contextRaw = s.imb;

    const hasTrigger = Math.abs(triggerRaw) > 5;
    const hasMomentum = Math.abs(momentumRaw) > 10;
    const timePreceded = setupInfo.active && now - setupInfo.earliestTs >= 30000;

    let stage = 0;
    if (setupInfo.active) {
      stage = 1;
      if (hasTrigger && timePreceded) {
        stage = 2;
        if (hasMomentum) stage = 3;
      }
    }

    let triggerMult = 0.3;
    let momentumMult = 0.3;
    if (setupInfo.count >= 2) {
      triggerMult = 1.0;
      momentumMult = stage >= 2 ? 1.3 : 0.7;
    } else if (setupInfo.count === 1) {
      triggerMult = 0.7;
      momentumMult = stage >= 2 ? 1.0 : 0.5;
    }

    let raw = setupRaw + triggerRaw * triggerMult + momentumRaw * momentumMult + contextRaw;
    const rawDir = Math.sign(raw) || 0;
    const regimeMult = getRegimeMult(rawDir);
    raw *= regimeMult;

    const total = Math.max(-180, Math.min(180, Math.round(raw)));
    return { total, stage, setupInfo, regimeMult, rawDir };
  }

  function macroRadar() {
    for (const sym in M) {
      const m = M[sym];
      if (m.currentVol === 0) continue;

      m.priceHist300s.push(m.price);
      if (m.priceHist300s.length > 300) m.priceHist300s.shift();

      if (m.priceHist300s.length > 60) m.trend5m = (m.price - m.priceHist300s[0]) / m.priceHist300s[0];

      m.volHistory.push(m.currentVol);
      if (m.volHistory.length > 60) m.volHistory.shift();
      if (m.volHistory.length < 10) continue;

      const li = m.volHistory.length - 1;
      const v10 = m.volHistory[li] - m.volHistory[Math.max(0, li - 10)];
      const avg = ((m.volHistory[li] - m.volHistory[0]) / li) * 10;
      m.velocity = avg > 10000 ? v10 / avg : 0;

      if (m.velocity >= C.radarVel && v10 > C.radarMinVol && m.totalQuoteVol > C.minQuoteVol) m.velStreak++;
      else m.velStreak = 0;

      if (m.velStreak >= C.velStreak && !m.inSniper && Object.keys(SD).length < C.maxSnipers) promote(sym);
    }
  }

  function promote(sym: string) {
    M[sym].inSniper = true;
    const tier = getSymTier(sym);

    SD[sym] = {
      cvdBn: 0,
      cvdOkx: 0,
      cvdBybit: 0,
      cvdBitget: 0,
      cvdBnHist: [],
      cvdOxHist: [],
      cvdByHist: [],
      cvdBgHist: [],
      tickVolSum: 0,
      priceHist: [],
      tickVolHist: [],
      cvdTotalHist: [],
      bnBidVol: 0,
      bnAskVol: 0,
      prevBnBid: 0,
      prevBnAsk: 0,
      bgBidVol: 0,
      bgAskVol: 0,
      prevBgBid: 0,
      prevBgAsk: 0,
      bgDepthTs: 0,
      recentLiq: { side: '', vol: 0, ts: 0 },
      liqBuyEv: [],
      liqSellEv: [],
      whaleEvents: [],
      tradeVolEma: 5000,
      tradeCount: 0,
      absDir: 0,
      protectedUntil: 0,
      lastSpoofBn: 0,
      lastSpoofBg: 0,
      lastAbs: 0,
      lastWhale: 0,
      lastOiBuild: 0,
      lastCvdCons: 0,
      warmupUntil: Date.now() + C.warmupMs,
      tier,
      latch: { stage: 0, dir: 0, expiry: 0, maxDur: 0 },
      scores: {
        tick: 0,
        spoofBn: 0,
        spoofBg: 0,
        abs: 0,
        imb: 0,
        cross: 0,
        whale: 0,
        funding: 0,
        liq: 0,
        oiBuild: 0,
        cvdCons: 0,
        total: 0,
        stage: 0,
        latchRatio: 0,
      },
    };

    subBn(sym);
    subOx(sym);
    subBy(sym);
    subBg(sym);
    void fetch9am(sym);
    lastSortTime = 0;
  }

  function demote(sym: string) {
    unBn(sym);
    unOx(sym);
    unBy(sym);
    unBg(sym);

    delete SD[sym];
    if (M[sym]) M[sym].inSniper = false;
    delete OI[sym];

    pinnedSyms.delete(sym);
    delete aGradeState[sym];
    displayedOrder = displayedOrder.filter((x) => x.full !== sym);
  }

  function checkTripleCrown(sym: string, score: number, stage: number, latchedDir: number) {
    if (stage < 2) return 0;
    if (Math.abs(score) < 40) return 0;

    const lb = currentLeaderboard[sym];
    if (!lb || Math.abs(lb.scoreSum) < 30) return 0;
    if (Math.sign(lb.scoreSum) !== latchedDir) return 0;
    return latchedDir;
  }

  function firePreSignal(sym: string, type: string, dir: number, title: string, desc: string, score: number) {
    const key = sym + '_' + type;
    const now = Date.now();
    if (preSigCooldown[key] && now - preSigCooldown[key] < 300000) return;

    preSigCooldown[key] = now;
    preSigHistory.unshift({ sym, type, dir, ts: now, title, desc, score: score || 0 });
    if (preSigHistory.length > C.preCardMax) preSigHistory.length = C.preCardMax;

    if (!isFrozen) syncPreSignals();
  }

  function cleanPreSignals() {
    const n = Date.now();
    const l = preSigHistory.length;
    for (let i = l - 1; i >= 0; i--) {
      if (n - preSigHistory[i].ts > C.preCardTtl) preSigHistory.splice(i, 1);
    }

    if (!isFrozen && preSigHistory.length !== l) syncPreSignals();
  }

  function syncPreSignals() {
    ui.preSignals = preSigHistory.map((p) => ({ ...p })).slice(0, C.preCardMax);
    ui.summary.pre = ui.preSignals.length;
  }

  async function pollFunding() {
    try {
      const r = await fetch('https://fapi.binance.com/fapi/v1/premiumIndex');
      const arr = await r.json();

      arr.forEach((d: any) => {
        if (!d.symbol || !d.symbol.endsWith('USDT')) return;

        FR[d.symbol] = parseFloat(d.lastFundingRate);
        const mark = parseFloat(d.markPrice);
        const index = parseFloat(d.indexPrice);
        const mi = mark > 0 ? (mark - index) / index : 0;
        MI[d.symbol] = mi;

        if (Math.abs(FR[d.symbol]) > C.fundingExtStrong) {
          firePreSignal(
            d.symbol,
            'fundExt',
            FR[d.symbol] < 0 ? 1 : -1,
            '⚡ 펀딩 극단치',
            '과열 ' + (FR[d.symbol] * 100).toFixed(3) + '%',
            0,
          );
        }

        if (Math.abs(mi) > C.miExt) {
          firePreSignal(d.symbol, 'miDiv', mi < 0 ? 1 : -1, '📡 MI 괴리', '선물괴리 ' + (mi * 100).toFixed(3) + '%', 0);
        }
      });
    } catch (_e) {}
  }

  async function pollOI() {
    const syms = Object.keys(SD);
    if (!syms.length) return;

    try {
      const rs = await Promise.allSettled(
        syms.map((s) =>
          fetch('https://fapi.binance.com/fapi/v1/openInterest?symbol=' + s)
            .then((r) => r.json())
            .then((d) => ({ s, oi: parseFloat(d.openInterest) })),
        ),
      );

      rs.forEach((r: any) => {
        if (r.status === 'fulfilled' && isFinite(r.value.oi)) {
          const s = r.value.s;
          const v = r.value.oi * (M[s] ? M[s].price : 0);
          if (!OI[s]) OI[s] = { prev: 0, pctChg: 0 };
          if (OI[s].prev > 0 && v > 0) OI[s].pctChg = (v - OI[s].prev) / OI[s].prev;
          OI[s].prev = v;
        }
      });
    } catch (_e) {}
  }

  async function pollLSR() {
    const syms = Array.from(currentTopCoins).slice(0, 15);
    if (!syms.length) return;

    try {
      const rs = await Promise.allSettled(
        syms.map((s) =>
          fetch(`https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=${s}&period=5m&limit=1`)
            .then((r) => r.json())
            .then((d) => ({ s, d: Array.isArray(d) && d[0] ? d[0] : null })),
        ),
      );

      rs.forEach((r: any) => {
        if (r.status === 'fulfilled' && r.value.d) {
          LSR[r.value.s] = { longPct: parseFloat(r.value.d.longAccount) };
        }
      });
    } catch (_e) {}
  }

  function renderSummary(list: any[]) {
    const s2plus = list.filter((x) => x.stage >= 2).length;
    const s1 = list.filter((x) => x.stage === 1).length;

    ui.summary.snipers = list.length;
    ui.summary.s2plus = s2plus;
    ui.summary.s1 = s1;

    if (regimeState.ready) {
      const d = regimeState.btcAltDelta;
      if (d > 1) ui.summary.bias = '▲ ALT강세';
      else if (d < -1) ui.summary.bias = '▼ ALT약세';
      else ui.summary.bias = '— 중립';
    } else {
      ui.summary.bias = '—';
    }

    ui.summary.pre = preSigHistory.length;
  }

  function renderTable(list: any[]) {
    if (!list.length) {
      ui.rows = [];
      return;
    }

    const now = Date.now();

    if (now - lastSortTime > C.sortDelay || displayedOrder.length !== list.length) {
      const pinned = list.filter((i) => pinnedSyms.has(i.full));
      const unpinned = list.filter((i) => !pinnedSyms.has(i.full));
      const qs = (a: any, b: any) => b.stage - a.stage || Math.abs(b.score) - Math.abs(a.score);
      pinned.sort(qs);
      unpinned.sort(qs);
      displayedOrder = [...pinned, ...unpinned];
      lastSortTime = now;
    }

    const rows: HunterRow[] = [];

    displayedOrder.forEach((oItem) => {
      const item = list.find((x) => x.full === oItem.full);
      if (!item) return;

      if (focusMode && item.stage < 2 && !pinnedSyms.has(item.full)) return;

      rows.push({
        sym: item.sym,
        full: item.full,
        price: item.price,
        score: item.score,
        stage: item.stage,
        latchDir: item.latchDir,
        latchRatio: item.latchRatio,
        cvd: item.cvd,
        mult: item.mult,
        chg9: item.chg9,
        regimeMult: item.regimeMult,
        setupCount: item.setupInfo?.count || 0,
        sig: item.sig,
        aGradeCount: item.ag?.count || 0,
        aGradeDir: item.ag?.lastDir || 0,
        aGradeActive: !!item.ag?.activeNow,
        pinned: pinnedSyms.has(item.full),
      });
    });

    ui.rows = rows;
  }

  function updateRank(force = false) {
    if (isFrozen && !force) return;

    const now = Date.now();
    const cut = now - 30 * 60000;
    sigHist = sigHist.filter((s) => s.time >= cut);

    const cnt: Record<string, any> = {};
    sigHist.forEach((s) => {
      if (!cnt[s.sym]) cnt[s.sym] = { sym: s.sym, total: 0, scoreSum: 0, absSum: 0, tags: {} as Record<string, number> };

      const c = cnt[s.sym];
      c.total++;
      c.scoreSum += s.score || 0;
      c.absSum += Math.abs(s.score || 0);

      const nMap: Record<string, string> = {
        tick: '돌파',
        sqz: '스퀴즈',
        whale: '고래',
        spoofBn: '스푸핑',
        spoofBg: '스푸핑',
        abs: '흡수',
        cross: '크로스',
        funding: '펀딩',
        liq: '청산',
        oiBuild: 'OI빌드',
        cvdCons: 'CVD합의',
      };

      const tName = nMap[s.type];
      if (tName) c.tags[tName] = (c.tags[tName] || 0) + 1;
    });

    let sorted = Object.values(cnt);
    sorted.sort((a: any, b: any) => b.absSum - a.absSum || b.total - a.total);

    const top15 = sorted.slice(0, 15);
    currentTopCoins = new Set<string>();
    currentLeaderboard = {};

    const lbItems: HunterLeaderboardItem[] = top15.map((i: any) => {
      currentTopCoins.add(i.sym);
      currentLeaderboard[i.sym] = i;

      const sd = SD[i.sym];
      const ag = aGradeState[i.sym] || { count: 0, lastDir: 0 };
      return {
        sym: i.sym,
        total: i.total,
        scoreSum: i.scoreSum,
        absSum: i.absSum,
        tags: i.tags,
        stage: sd ? sd.scores.stage : 0,
        aGradeCount: ag.count || 0,
        aGradeDir: ag.lastDir || 0,
      };
    });

    ui.leaderboard = lbItems;
  }

  function renderRegime() {
    let btcChg: number | null = null;
    const altChgs: number[] = [];

    for (const sym in M) {
      const p9 = P9[sym];
      if (p9 && M[sym].price) {
        const chg = ((M[sym].price - p9) / p9) * 100;
        if (sym === 'BTCUSDT') btcChg = chg;
        else if (M[sym].inSniper) altChgs.push(chg);
      }
    }

    if (btcChg !== null && altChgs.length) {
      const d = altChgs.reduce((a, b) => a + b, 0) / altChgs.length - btcChg;
      regimeState.btcAltDelta = d;
      regimeState.ready = true;
      ui.regime.btcAltDelta = d;
      ui.regime.ready = true;
    }

    const frs = Object.keys(SD)
      .filter((s) => isFinite(FR[s]))
      .map((s) => FR[s]);
    if (frs.length) {
      const p = (frs.reduce((a, b) => a + b, 0) / frs.length) * 100;
      regimeState.avgFunding = p;
      ui.regime.avgFunding = p;
    }

    const oiEntries = Object.keys(SD).filter((s) => OI[s] && OI[s].prev > 0 && isFinite(OI[s].pctChg));
    if (oiEntries.length) {
      const r = (oiEntries.filter((s) => OI[s].pctChg > 0.005).length / oiEntries.length) * 100;
      ui.regime.oiExpansionRate = r;
    }

    const cut10 = Date.now() - 600000;
    const r10 = sigHist.filter((s) => s.time >= cut10);
    if (r10.length) {
      const pos = r10.filter((s) => s.score > 0).reduce((a, b) => a + Math.abs(b.score), 0);
      const neg = r10.filter((s) => s.score < 0).reduce((a, b) => a + Math.abs(b.score), 0);
      const tot = pos + neg || 1;
      ui.regime.longFlowRatio = (pos / tot) * 100;
    }
  }

  function decayLoop() {
    const rl: any[] = [];
    const now = Date.now();

    for (const sym in SD) {
      const sd = SD[sym];
      const m = M[sym];
      if (!m) continue;

      const s = sd.scores;
      const tier = sd.tier || TIER.C;

      sd.priceHist.push(m.price);
      sd.tickVolHist.push(sd.tickVolSum);
      const cvdT = sd.cvdBn + sd.cvdOkx + sd.cvdBybit + sd.cvdBitget;

      sd.cvdTotalHist.push(cvdT);
      sd.cvdBnHist.push(sd.cvdBn);
      sd.cvdOxHist.push(sd.cvdOkx);
      sd.cvdByHist.push(sd.cvdBybit);
      sd.cvdBgHist.push(sd.cvdBitget);

      if (sd.priceHist.length > 60) {
        sd.priceHist.shift();
        sd.tickVolHist.shift();
        sd.cvdTotalHist.shift();
        sd.cvdBnHist.shift();
        sd.cvdOxHist.shift();
        sd.cvdByHist.shift();
        sd.cvdBgHist.shift();
      }

      if (OI[sym] && OI[sym].pctChg > C.oiBuildPct && sd.priceHist.length >= 30 && now - sd.lastOiBuild > 30000 && now >= sd.warmupUntil) {
        const pChg = Math.abs(m.price - sd.priceHist[sd.priceHist.length - 30]) / sd.priceHist[sd.priceHist.length - 30];
        if (pChg < C.oiBuildPriceFlat) {
          const dir = Math.sign(cvdT - sd.cvdTotalHist[Math.max(0, sd.cvdTotalHist.length - 30)]);
          if (dir !== 0) {
            s.oiBuild = dir * 30;
            sd.lastOiBuild = now;
            trackSig(sym, 'oiBuild', s.oiBuild);
            firePreSignal(sym, 'oiBuild', dir, '🔮 OI 빌드업', '포지션 축적 · 가격 횡보', 30);
            playBeep(500);
          }
        }
      }

      const cvdCD = tier.cvdConsCD || 15000;
      if (sd.cvdBnHist.length >= 30 && now - sd.lastCvdCons > cvdCD && now >= sd.warmupUntil) {
        const sum =
          sd.cvdBn - sd.cvdBnHist[0] +
          (sd.cvdOkx - sd.cvdOxHist[0]) +
          (sd.cvdBybit - sd.cvdByHist[0]) +
          (sd.cvdBitget - sd.cvdBgHist[0]);

        if (Math.abs(sum) >= tier.cvdConsMin) {
          const dir = Math.sign(sum);
          s.cvdCons = dir * 25;
          sd.lastCvdCons = now;
          trackSig(sym, 'cvdCons', s.cvdCons);
          firePreSignal(sym, 'cvdCons', dir, '💹 CVD 합의', '4거래소 동시 체결 ' + tier.label + '급', 25);
        }
      }

      const avgV = sd.tickVolHist.reduce((a: number, b: number) => a + b, 0) / Math.max(1, sd.tickVolHist.length);
      const mult = avgV > 1000 ? sd.tickVolSum / avgV : 0;

      if (sd.tickVolHist.length >= 5 && avgV > 1000) {
        const pD = m.price - (sd.priceHist[Math.max(0, sd.priceHist.length - 5)] || m.price);
        if (mult > 6) {
          let base = pD >= 0 ? 40 : -40;
          if (now - sd.recentLiq.ts < 2000) {
            if (pD >= 0 && sd.recentLiq.side === 'BUY') {
              base = 50;
              trackSig(sym, 'sqz', base);
              playBeep(1000);
            } else if (pD < 0 && sd.recentLiq.side === 'SELL') {
              base = -50;
              trackSig(sym, 'sqz', base);
              playBeep(1000);
            } else {
              trackSig(sym, 'tick', base);
              playBeep(660);
            }
          } else {
            trackSig(sym, 'tick', base);
            playBeep(660);
          }
          s.tick = base;
          if (Math.abs(base) >= 50) sd.protectedUntil = Math.max(sd.protectedUntil, now + 300000);
        } else if (mult > 3) {
          s.tick = pD >= 0 ? 15 : -15;
        } else {
          s.tick = 0;
        }
      } else {
        s.tick = 0;
      }

      sd.tickVolSum = 0;

      const dep = sd.bnBidVol + sd.bgBidVol + sd.bnAskVol + sd.bgAskVol || 1;
      const bidPct = (sd.bnBidVol + sd.bgBidVol) / dep;
      if (bidPct > 0.7) s.imb = 15;
      else if (bidPct > 0.6) s.imb = 10;
      else if (bidPct < 0.3) s.imb = -15;
      else if (bidPct < 0.4) s.imb = -10;
      else s.imb = 0;

      sd.liqBuyEv = sd.liqBuyEv.filter((t: number) => now - t < 60000);
      sd.liqSellEv = sd.liqSellEv.filter((t: number) => now - t < 60000);
      const maxL = Math.max(sd.liqBuyEv.length, sd.liqSellEv.length);
      if (maxL >= 5) s.liq = (sd.liqBuyEv.length > sd.liqSellEv.length ? 1 : -1) * 20;
      else if (maxL >= 3) s.liq = (sd.liqBuyEv.length > sd.liqSellEv.length ? 1 : -1) * 10;
      else s.liq = 0;

      if (FR[sym] !== undefined) {
        let fS = 0;
        if (FR[sym] < -C.fundingExt) fS = 15;
        else if (FR[sym] > C.fundingExt) fS = -15;

        if (LSR[sym] && fS !== 0) {
          if (fS > 0 && LSR[sym].longPct < 0.42) fS = 25;
          else if (fS < 0 && LSR[sym].longPct > 0.58) fS = -25;
        }

        if (fS !== 0) s.funding = fS;
        else s.funding *= 0.95;
      }

      s.spoofBn *= 0.7;
      s.spoofBg *= 0.7;
      s.abs *= 0.8;
      s.cross *= 0.7;
      s.whale *= 0.85;
      s.oiBuild *= 0.9;
      s.cvdCons *= 0.8;

      ['spoofBn', 'spoofBg', 'abs', 'cross', 'whale', 'funding', 'oiBuild', 'cvdCons'].forEach((k) => {
        if (Math.abs(s[k]) < 1) s[k] = 0;
      });

      const stageResult = calcStageScore(sd, sym, now);
      const rawTotal = stageResult.total;
      const rawStage = stageResult.stage;
      const rawDir = stageResult.rawDir;

      const l = sd.latch;

      if (rawStage > 0 && l.stage > 0 && rawDir !== l.dir && Math.abs(rawTotal) >= C.hardResetThresh) {
        l.stage = rawStage;
        l.dir = rawDir;
        l.maxDur = C.latchDur[rawStage as 1 | 2 | 3];
        l.expiry = now + l.maxDur;
      } else if (rawStage >= l.stage && rawStage > 0 && (l.dir === 0 || rawDir === l.dir)) {
        l.stage = rawStage;
        l.dir = rawDir;
        l.maxDur = C.latchDur[rawStage as 1 | 2 | 3];
        l.expiry = now + l.maxDur;
      } else if (now > l.expiry) {
        l.stage = rawStage;
        l.dir = rawStage > 0 ? rawDir : 0;
        if (l.stage > 0) {
          l.maxDur = C.latchDur[rawStage as 1 | 2 | 3];
          l.expiry = now + l.maxDur;
        }
      }

      s.total = rawTotal;
      s.stage = l.stage;
      s.latchRatio = l.stage > 0 ? Math.max(0, l.expiry - now) / Math.max(1, l.maxDur) : 0;

      if (
        now > sd.protectedUntil &&
        m.velocity < 1.5 &&
        Math.abs(s.total) < 10 &&
        sd.tickVolHist.length > 20 &&
        sd.tickVolHist.slice(-15).reduce((a: number, b: number) => a + b, 0) < 10000
      ) {
        demote(sym);
        continue;
      }

      const tcDir = checkTripleCrown(sym, s.total, s.stage, l.dir);
      if (!aGradeState[sym]) aGradeState[sym] = { count: 0, lastDir: 0, lastTs: 0, activeNow: false };

      const ag = aGradeState[sym];
      if (tcDir !== 0) {
        if (ag.lastDir !== tcDir) ag.count = 1;
        else if (!ag.activeNow) ag.count++;

        ag.lastDir = tcDir;
        ag.lastTs = now;
        ag.activeNow = true;
        pinnedSyms.add(sym);
      } else {
        ag.activeNow = false;
        if (now - ag.lastTs > 30 * 60000) ag.count = 0;
      }

      const nMap: Record<string, string> = {
        tick: '돌파',
        sqz: '스퀴즈',
        whale: '고래',
        spoofBn: '스푸핑',
        spoofBg: '스푸핑',
        abs: '흡수',
        cross: '크로스',
        funding: '펀딩',
        liq: '청산',
        oiBuild: 'OI빌드',
        cvdCons: 'CVD합의',
      };

      const sgs: HunterSignalTag[] = [];
      ['oiBuild', 'cvdCons', 'funding'].forEach((k) => {
        if (Math.abs(s[k]) > 0) sgs.push({ n: nMap[k], d: Math.sign(s[k]), cat: 'setup' });
      });
      ['spoofBn', 'abs', 'cross', 'whale'].forEach((k) => {
        if (Math.abs(s[k]) > 0) sgs.push({ n: nMap[k], d: Math.sign(s[k]), cat: 'trigger' });
      });
      if (Math.abs(s.spoofBg) > 0 && Math.abs(s.spoofBn) === 0) sgs.push({ n: '스푸핑', d: Math.sign(s.spoofBg), cat: 'trigger' });
      ['tick', 'sqz', 'liq'].forEach((k) => {
        if (Math.abs(s[k]) > 0) sgs.push({ n: nMap[k], d: Math.sign(s[k]), cat: 'momentum' });
      });

      let chg9: number | null = null;
      if (P9[sym] && m.price > 0) {
        const utcH = new Date().getUTCHours();
        if (utcH >= 2) chg9 = ((m.price - P9[sym]) / P9[sym]) * 100;
      }

      rl.push({
        sym: m.symbol.replace('USDT', ''),
        full: m.symbol,
        price: m.price,
        score: s.total,
        stage: s.stage,
        latchDir: l.dir,
        latchRatio: s.latchRatio,
        cvd: cvdT,
        mult,
        chg9,
        ag,
        sig: sgs,
        setupInfo: stageResult.setupInfo,
        regimeMult: stageResult.regimeMult,
      });
    }

    if (!isFrozen) {
      renderSummary(rl);
      renderTable(rl);
      if (now - lastRegimeUpdate > C.regimeThrottle) {
        lastRegimeUpdate = now;
        renderRegime();
      }
      emit();
    }
  }

  async function startSystem() {
    if (running) return;

    running = true;
    ui.statusText = '로딩중...';
    emit();

    try {
      let fl: any[];
      try {
        const ctrl = window.AbortController ? new AbortController() : null;
        const tid = ctrl ? setTimeout(() => ctrl.abort(), 8000) : null;
        const r = await fetch('https://fapi.binance.com/fapi/v1/exchangeInfo', ctrl ? { signal: ctrl.signal } : {});
        if (tid) clearTimeout(tid);
        const data = await r.json();
        fl = data.symbols;
      } catch (_e) {
        fl = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT', 'PEPEUSDT', 'WIFUSDT', 'SUIUSDT', 'BNBUSDT', 'AVAXUSDT'].map((s) => ({
          symbol: s,
          quoteAsset: 'USDT',
          status: 'TRADING',
        }));
      }

      fl.forEach((s: any) => {
        if (s.quoteAsset === 'USDT' && s.status === 'TRADING') {
          M[s.symbol] = {
            symbol: s.symbol,
            price: 0,
            currentVol: 0,
            totalQuoteVol: 0,
            volHistory: [],
            priceHist300s: [],
            velocity: 0,
            velStreak: 0,
            trend5m: 0,
            inSniper: false,
          };
        }
      });

      ui.statusText = '정상 가동';
      emit();

      openGlobal();
      openBnSniper();
      openOkx();
      openBybit();
      openBitget();

      scanIv = setInterval(macroRadar, 1000);
      decayIv = setInterval(decayLoop, 1000);
      fundIv = setInterval(() => {
        void pollFunding();
      }, 30000);
      oiIv = setInterval(() => {
        void pollOI();
      }, 60000);
      lsrIv = setInterval(() => {
        void pollLSR();
      }, 60000);
      regimeIv = setInterval(cleanPreSignals, 10000);

      setTimeout(() => {
        void pollFunding();
      }, 5000);
      setTimeout(() => {
        void pollOI();
      }, 15000);
      setTimeout(() => {
        void pollLSR();
      }, 25000);
    } catch (e: any) {
      ui.statusText = '초기화 실패: ' + (e?.message || String(e));
      running = false;
      emit();
    }
  }

  function toggleMute() {
    muted = !muted;
    emit();
  }

  function toggleFocus() {
    focusMode = !focusMode;
    if (!isFrozen) lastSortTime = 0;
    emit();
  }

  function toggleFreeze() {
    isFrozen = !isFrozen;
    emit();
  }

  function setSort(mode: HunterSortMode) {
    sortMode = mode;
    updateRank(true);
    emit();
  }

  function togglePin(sym: string) {
    if (pinnedSyms.has(sym)) pinnedSyms.delete(sym);
    else pinnedSyms.add(sym);
    lastSortTime = 0;
    emit();
  }

  const api: HunterRuntimeApi = {
    startSystem,
    stopSystem,
    toggleMute,
    toggleFocus,
    toggleFreeze,
    setSort,
    togglePin,
  };

  emit();

  return {
    api,
    cleanup: () => {
      stopSystem();
    },
  };
}
