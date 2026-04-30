// Crime Pump Hunter V5 — scoring engine (TypeScript port of crime.py)

import type { CoinData, RiskProfile, ExitAlert, FundingHistory } from "../crimeData";

// ─── Constants ───────────────────────────────────────────
const MEGA_PUMP_SHORT_RATIO_MIN = 62.0;
const MEGA_PUMP_FUNDING_VEL     = -0.005;
const MEGA_PUMP_OI_1H_MIN       = 8.0;
const MEGA_PUMP_COIL_OI_24H     = 35.0;

const DUMP_TRAP_PRICE_RISE_24H  = 15.0;
const DUMP_TRAP_FUNDING_POS     = 0.15;
const DUMP_TRAP_OI_REVERSAL     = -10.0;

const MAX_LEVERAGE         = 10;
const RISK_PER_TRADE_PCT   = 2.0;
const DEFAULT_CAPITAL_USD  = 1000;

const W: Record<string, number> = {
  funding_extreme:        35,
  funding_negative:       15,
  funding_very_neg:       25,
  oi_spike:               40,
  oi_growth:              20,
  oi_surge_1h:            25,
  oi_surge_4h:            15,
  ls_ratio_short:         35,
  ls_ratio_mid:           15,
  top_trader_short:       30,
  top_trader_diverge:     25,
  taker_buy_dominant:     30,
  taker_sell_dominant:    20,
  orderbook_bid_heavy:    25,
  orderbook_ask_heavy:    15,
  volume_spike:           30,
  volume_extreme:         20,
  price_momentum_1h:      20,
  price_compression:      20,
  mark_discount:          20,
  signature_accumulation: 40,
  signature_spring:       35,
  signature_ignition:     50,
  funding_velocity_up:    20,
  funding_velocity_down:  25,
  oi_reversal_warning:   -30,
  vol_exhaustion:        -25,
  whale_exit_signal:     -40,
  coil_extreme:           55,
  squeeze_fuel_max:       45,
  pre_ignition:           60,
  oi_early_surge:         20,
  taker_flip:             30,
  orderbook_thin_ask:     35,
  funding_extreme_v6:     40,
};

// ─── ATR ─────────────────────────────────────────────────
export function calculateAtr(klines: string[][]): number {
  if (klines.length < 15) return 0;
  const trs: number[] = [];
  for (let i = 1; i < klines.length; i++) {
    const h  = parseFloat(klines[i][2]);
    const l  = parseFloat(klines[i][3]);
    const pc = parseFloat(klines[i - 1][4]);
    trs.push(Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc)));
  }
  const last14 = trs.slice(-14);
  return last14.reduce((a, b) => a + b, 0) / last14.length;
}

// ─── Squeeze Fuel ─────────────────────────────────────────
export function calcSqueezeFuel(coin: Partial<CoinData>): number {
  let fuel = 0;
  fuel += Math.max(0, Math.min(25, ((coin.short_ratio ?? 50) - 50) * 1.25));
  fuel += Math.max(0, Math.min(30, Math.abs(Math.min(coin.funding_rate ?? 0, 0)) * 60));
  fuel += Math.max(0, Math.min(20, Math.max(coin.oi_change_pct_1h ?? 0, 0) * 0.87));
  if (Math.abs(coin.price_change_24h ?? 99) < 3) fuel += 10;
  if ((coin.taker_buy_ratio ?? 0) >= 58) fuel += 15;
  const imb = coin.book_imbalance ?? 1;
  if (imb >= 2.0) fuel += Math.min(10, (imb - 2.0) * 5);
  return Math.min(100, fuel);
}

// ─── Pump Stage ───────────────────────────────────────────
export function classifyPumpStage(coin: Partial<CoinData>): string {
  const fr   = coin.funding_rate ?? 0;
  const oi1h = coin.oi_change_pct_1h ?? 0;
  const oi4h = coin.oi_change_pct_4h ?? 0;
  const oi24 = coin.oi_change_pct_24h ?? 0;
  const sr   = coin.short_ratio ?? 50;
  const pc1  = coin.price_change_1h ?? 0;
  const pc4  = coin.price_change_4h ?? 0;
  const pc24 = coin.price_change_24h ?? 0;
  const vcp  = coin.volume_change_pct ?? 0;
  const tbr  = coin.taker_buy_ratio ?? 50;

  const isNegFunding   = fr < -0.05;
  const isDeepNeg      = fr < -0.20;
  const isOIGrowing    = oi24 > 10;
  const isOISurging    = oi1h > 10 || oi4h > 20;
  const isOIEarly      = oi1h > MEGA_PUMP_OI_1H_MIN;
  const isPriceFlat    = Math.abs(pc24) < 3;
  const isPricePumping = pc1 > 3 || pc4 > 5;
  const isVolSpike     = vcp > 150;
  const isVolLow       = vcp < -20;
  const isShortHeavy   = sr > 55;
  const isShortExtreme = sr > MEGA_PUMP_SHORT_RATIO_MIN;
  const isTakerBuying  = tbr >= 58;

  if (isNegFunding && isOISurging && isVolSpike && isShortHeavy) return "🔥 IGNITION";
  if (isPricePumping && isVolSpike && isShortHeavy)              return "🔥 IGNITION";

  if (isPriceFlat && isDeepNeg && isShortExtreme && isOIEarly && isTakerBuying) return "💥 PRE_IGNITION";
  if (isPriceFlat && isDeepNeg && isShortExtreme && oi4h > 15)                  return "💥 PRE_IGNITION";

  if (isPriceFlat && isOIGrowing && isVolLow && isNegFunding)         return "⚡ SPRING";
  if (isPriceFlat && isOISurging && Math.abs(pc1) < 2)                return "⚡ SPRING";
  if (isNegFunding && isOIGrowing && !isPricePumping)                 return "🟢 ACCUMULATE";
  if (isNegFunding && isShortHeavy)                                   return "🟢 ACCUMULATE";
  if (fr > 0.05 && pc24 > 10)                                         return "⚪ DISTRIBUTE";
  return "⬜ NEUTRAL";
}

// ─── V4 + V6 Score ────────────────────────────────────────
export function calculateScoreV4(coin: CoinData): CoinData {
  const c = { ...coin, score: coin.score ?? 0, score_reasons: [...(coin.score_reasons ?? [])] };

  const fr  = c.funding_rate;
  const sr  = c.short_ratio;
  const tsr = c.top_short_ratio;
  const tlr = c.top_long_ratio;
  const tbr = c.taker_buy_ratio;
  const tv  = c.taker_sell_ratio;
  const imb = c.book_imbalance;
  const vcp = c.volume_change_pct;
  const pc1 = c.price_change_1h;
  const pc24 = c.price_change_24h;
  const oi1h = c.oi_change_pct_1h;
  const oi4h = c.oi_change_pct_4h;
  const oi24 = c.oi_change_pct_24h;
  const mid  = c.mark_index_diff_pct;

  const add = (key: string, reason: string) => {
    c.score += W[key]; c.score_reasons.push(reason);
  };

  if      (fr < -0.5)  add("funding_extreme",  `🔴펀딩${fr.toFixed(3)}%`);
  else if (fr < -0.3)  add("funding_very_neg",  `🔴펀딩${fr.toFixed(3)}%`);
  else if (fr < -0.1)  add("funding_negative",  `🟠펀딩${fr.toFixed(3)}%`);

  if      (oi24 >= 50) add("oi_spike",    `🔴OI24h+${oi24.toFixed(0)}%`);
  else if (oi24 >= 20) add("oi_growth",   `🟠OI24h+${oi24.toFixed(0)}%`);
  if      (oi1h >= 15) add("oi_surge_1h", `🔴OI1h+${oi1h.toFixed(0)}%`);
  if      (oi4h >= 25) add("oi_surge_4h", `🟠OI4h+${oi4h.toFixed(0)}%`);

  if      (sr >= 60) add("ls_ratio_short", `🔴숏${sr.toFixed(1)}%`);
  else if (sr >= 55) add("ls_ratio_mid",   `🟠숏${sr.toFixed(1)}%`);
  if      (tsr >= 60) add("top_trader_short", `🔴탑숏${tsr.toFixed(1)}%`);
  if (tlr > 55 && sr > 55) add("top_trader_diverge", "🟣괴리");

  if      (tbr >= 60) add("taker_buy_dominant",  `🟢매수체결${tbr.toFixed(0)}%`);
  else if (tv  >= 60) add("taker_sell_dominant", `🔵매도체결${tv.toFixed(0)}%`);

  if      (imb >= 2.0) add("orderbook_bid_heavy", `🟢Bid벽x${imb.toFixed(1)}`);
  else if (imb <= 0.5) add("orderbook_ask_heavy", `🔵Ask벽x${(1 / imb).toFixed(1)}`);

  if      (vcp >= 400) add("volume_extreme", `🔴거래량+${vcp.toFixed(0)}%`);
  else if (vcp >= 200) add("volume_spike",   `🟠거래량+${vcp.toFixed(0)}%`);

  if (Math.abs(pc1) >= 5) add("price_momentum_1h", `🟡1h${pc1 >= 0 ? "+" : ""}${pc1.toFixed(1)}%`);
  if (Math.abs(pc24) < 2 && oi24 > 15) add("price_compression", "⚡스프링압축");
  if (mid < -2) add("mark_discount", `🟣마크할인${mid.toFixed(1)}%`);

  // 복합 시그니처
  const hasNeg    = fr < -0.1;
  const hasDeep   = fr < -0.20;
  const hasOI15   = oi24 > 15;
  const hasShort  = sr > 55;
  const hasShortX = sr > MEGA_PUMP_SHORT_RATIO_MIN;
  const hasVol    = vcp > 150;
  const isFlat    = Math.abs(pc24) < 3;
  const hasEarly  = oi1h > MEGA_PUMP_OI_1H_MIN;
  const hasBuy    = tbr >= 58;

  if (hasNeg && hasOI15 && hasShort)              add("signature_accumulation", "💀매집시그니처");
  if (isFlat && oi24 > 25 && vcp < 50)            add("signature_spring",       "💀스프링시그니처");
  if (hasNeg && hasOI15 && hasVol && hasShort)    add("signature_ignition",     "☠️점화시그니처");

  // V6
  if (isFlat && hasDeep && hasShortX && oi24 > MEGA_PUMP_COIL_OI_24H)
    add("coil_extreme",     "🌀코일극한");
  if (hasDeep && hasShortX && hasEarly)
    add("squeeze_fuel_max", "⚡스퀴즈MAX");
  if (isFlat && hasBuy && hasDeep && hasEarly)
    add("pre_ignition",     "💥PRE점화");
  if (MEGA_PUMP_OI_1H_MIN <= oi1h && oi1h < 15)
    add("oi_early_surge",   `🟡OI조기+${oi1h.toFixed(0)}%`);
  if (isFlat && hasBuy && hasNeg)
    add("taker_flip",       `🟢매집체결${tbr.toFixed(0)}%`);
  if (imb >= 3.0)
    add("orderbook_thin_ask", `🔴Ask극소x${imb.toFixed(1)}`);

  c.pump_stage = classifyPumpStage(c);
  c.squeeze_fuel = calcSqueezeFuel(c);
  return c;
}

// ─── V5 Funding Velocity ──────────────────────────────────
export function applyFundingVelocityScore(coin: CoinData): CoinData {
  const c  = { ...coin, score: coin.score, score_reasons: [...coin.score_reasons] };
  const fh = c.funding_history;

  if (fh.velocity < MEGA_PUMP_FUNDING_VEL && c.funding_rate < 0) {
    c.score += W["funding_velocity_down"];
    c.score_reasons.push(`📉펀딩가속↓${fh.velocity.toFixed(4)}`);
    if (fh.velocity < -0.03 && c.funding_rate < -0.15) {
      c.score += W["funding_extreme_v6"];
      c.score_reasons.push(`🔴펀딩극단가속${fh.velocity.toFixed(4)}`);
    }
  } else if (fh.trend === "RISING" && fh.velocity > 0.02) {
    c.score += W["funding_velocity_up"];
    c.score_reasons.push(`📈펀딩전환↑${fh.velocity.toFixed(4)}`);
  }
  return c;
}

// ─── Dump Trap ────────────────────────────────────────────
export function detectDumpTrap(coin: CoinData): { rp: Partial<RiskProfile>; trapScore: number } {
  let trapScore = 0;
  const reasons: string[] = [];

  if (coin.price_change_24h > DUMP_TRAP_PRICE_RISE_24H) {
    trapScore += 30; reasons.push(`🚨24h+${coin.price_change_24h.toFixed(1)}% 이미 급등`);
  }
  if (coin.price_change_4h > 8) {
    trapScore += 20; reasons.push(`🚨4h+${coin.price_change_4h.toFixed(1)}% 단기 과열`);
  }
  if (coin.funding_rate > DUMP_TRAP_FUNDING_POS) {
    trapScore += 25; reasons.push(`🚨펀딩비 양전환(${coin.funding_rate >= 0 ? "+" : ""}${coin.funding_rate.toFixed(3)}%) → 분배 신호`);
  } else if (coin.funding_rate > 0.05) {
    trapScore += 10; reasons.push(`🟠펀딩비 상승 중(${coin.funding_rate >= 0 ? "+" : ""}${coin.funding_rate.toFixed(3)}%)`);
  }
  if (coin.funding_history.trend === "RISING" && coin.funding_rate > -0.05) {
    trapScore += 15; reasons.push("🚨펀딩비 상승 가속 → 세력 이탈 임박");
  }
  if (coin.oi_change_pct_1h < DUMP_TRAP_OI_REVERSAL) {
    trapScore += 25; reasons.push(`🚨OI 1h${coin.oi_change_pct_1h.toFixed(1)}% 급감 → 청산 중`);
  } else if (coin.oi_change_pct_24h < -5 && coin.price_change_24h > 10) {
    trapScore += 20; reasons.push("🚨가격↑ + OI↓ 다이버전스 → 분배 확정");
  }
  if (coin.volume_change_pct < -50 && coin.price_change_24h > 10) {
    trapScore += 20; reasons.push(`🚨거래량 고갈(${coin.volume_change_pct.toFixed(0)}%) → 펌프 종료`);
  }
  if (coin.top_short_ratio > 60 && coin.long_ratio > 55) {
    trapScore += 30; reasons.push(`🚨탑숏${coin.top_short_ratio.toFixed(0)}% + 일반롱${coin.long_ratio.toFixed(0)}% → 세력 이탈`);
  }
  if (coin.pump_stage === "⚪ DISTRIBUTE") {
    trapScore += 35; reasons.push("🚨DISTRIBUTION 단계 → 절대 롱 금지");
  }

  let dump_trap_risk: string;
  if      (trapScore >= 80) dump_trap_risk = "CRITICAL 🔴🔴🔴";
  else if (trapScore >= 50) dump_trap_risk = "HIGH 🔴🔴";
  else if (trapScore >= 25) dump_trap_risk = "MEDIUM 🟠";
  else                      dump_trap_risk = "LOW 🟢";

  return { rp: { dump_trap_risk, dump_trap_reasons: reasons }, trapScore };
}

// ─── Risk Profile ─────────────────────────────────────────
export function calculateRiskProfile(
  coin: CoinData,
  trapScore = 0,
  capitalUsd = DEFAULT_CAPITAL_USD,
): RiskProfile {
  const { rp: trap } = detectDumpTrap(coin);

  const price = coin.price;
  const atr   = coin.atr_pct > 0 ? (price * coin.atr_pct / 100) : 0;

  const atrStop  = atr > 0 ? atr * 1.5 : price * 0.03;
  const stopLoss = Math.max(price - atrStop, price * 0.85);
  const stopPct  = ((price - stopLoss) / price) * 100;

  const r = price - stopLoss;
  const t1 = price + r;
  const t2 = price + r * 2;
  const t3 = price + r * 3.5;
  const rr = stopLoss > 0 ? ((t1 + t2) / 2 - price) / (price - stopLoss) : 0;

  const baseLev = stopPct > 0 ? Math.min(100 / stopPct, MAX_LEVERAGE) : 1;
  const trapMul = trapScore >= 80 ? 0 : trapScore >= 50 ? 0.3 : trapScore >= 25 ? 0.6 : 1.0;
  const maxSafeLev    = Math.max(baseLev, 1);
  const recLev        = Math.max(baseLev * trapMul, 1);
  const maxLossUsd    = capitalUsd * RISK_PER_TRADE_PCT / 100;
  const positionSize  = stopPct > 0 ? Math.min(maxLossUsd / (stopPct / 100), capitalUsd * 0.5) : 0;

  let entryScore = 50;
  if (coin.pump_stage.includes("ACCUMULATE") || coin.pump_stage.includes("SPRING")) entryScore += 20;
  if (coin.pump_stage.includes("IGNITION"))   entryScore += 10;
  if (coin.pump_stage.includes("DISTRIBUTE")) entryScore -= 40;
  if (coin.funding_rate < -0.1)               entryScore += 15;
  if (rr > 2)  entryScore += 15;
  if (rr < 1)  entryScore -= 20;
  entryScore -= trapScore * 0.4;

  return {
    entry_score:          Math.max(0, Math.min(100, entryScore)),
    dump_trap_risk:       trap.dump_trap_risk ?? "LOW 🟢",
    dump_trap_reasons:    trap.dump_trap_reasons ?? [],
    recommended_leverage: Math.round(recLev * 10) / 10,
    max_safe_leverage:    Math.round(maxSafeLev * 10) / 10,
    position_size_usd:    Math.round(positionSize),
    entry_zone_low:       price * 0.995,
    entry_zone_high:      price * 1.005,
    stop_loss:            stopLoss,
    target_1:             t1,
    target_2:             t2,
    target_3:             t3,
    risk_reward:          Math.round(rr * 100) / 100,
    liq_cluster_above:    0,
    liq_cluster_below:    0,
    liq_above_usd:        0,
    liq_below_usd:        0,
    atr_pct:              coin.atr_pct,
    dca_plan: [
      { entry: Math.round(price * 1.000 * 1e8) / 1e8, size_pct: 40, note: "시장가 1차" },
      { entry: Math.round(price * 0.985 * 1e8) / 1e8, size_pct: 35, note: "-1.5% 지정가 2차" },
      { entry: Math.round(price * 0.970 * 1e8) / 1e8, size_pct: 25, note: "-3.0% 지정가 3차" },
    ],
  };
}

// ─── Exit Alert ───────────────────────────────────────────
export function calculateExitAlert(coin: CoinData): ExitAlert {
  let exitScore = 0;
  const reasons: string[] = [];

  if (coin.funding_rate > 0.3) {
    exitScore += 40; reasons.push(`🚨펀딩비 극양전(+${coin.funding_rate.toFixed(3)}%) → 즉시 탈출`);
  } else if (coin.funding_rate > 0.1) {
    exitScore += 25; reasons.push(`🟠펀딩비 양전(+${coin.funding_rate.toFixed(3)}%) → 일부 익절`);
  } else if (coin.funding_history.trend === "RISING" && coin.funding_rate > -0.05) {
    exitScore += 15; reasons.push("📈펀딩 빠른 상승 → 탈출 준비");
  }

  if (coin.oi_change_pct_1h < -15) {
    exitScore += 35; reasons.push(`🚨OI 1h${coin.oi_change_pct_1h.toFixed(1)}% 붕괴 → 강제청산 시작`);
  } else if (coin.oi_change_pct_1h < -8) {
    exitScore += 20; reasons.push(`🟠OI 1h${coin.oi_change_pct_1h.toFixed(1)}% 감소 → 청산 의심`);
  }
  if (coin.top_long_ratio > 65 && coin.price_change_1h > 3) {
    exitScore += 30; reasons.push(`🚨탑트레이더 롱${coin.top_long_ratio.toFixed(0)}% → 세력 매도 중`);
  }
  if (coin.volume_change_pct < -60 && coin.price_change_4h > 10) {
    exitScore += 25; reasons.push(`🚨거래량 고갈(${coin.volume_change_pct.toFixed(0)}%) → 상승 동력 소진`);
  }
  if (coin.price_change_1h < -3 && coin.taker_sell_ratio > 65) {
    exitScore += 30; reasons.push(`🚨-${Math.abs(coin.price_change_1h).toFixed(1)}% + 매도체결${coin.taker_sell_ratio.toFixed(0)}% → 추세 반전`);
  }
  if (coin.mark_index_diff_pct > 2) {
    exitScore += 15; reasons.push(`🟠마크프리미엄+${coin.mark_index_diff_pct.toFixed(2)}% → 선물 과열`);
  }

  const finalScore = Math.min(100, exitScore);
  let urgency: string;
  if      (finalScore >= 70) urgency = "EMERGENCY 🚨";
  else if (finalScore >= 45) urgency = "URGENT ⚠️";
  else if (finalScore >= 25) urgency = "WATCH 👀";
  else                       urgency = "HOLD 🟢";

  return {
    should_exit:  finalScore >= 45,
    urgency,
    exit_reasons: reasons,
    exit_score:   finalScore,
  };
}

// ─── Z-Score normalization ────────────────────────────────
export function applyZScores(coins: CoinData[]): CoinData[] {
  if (coins.length < 3) return coins;

  const fields: Array<{ key: string; getter: (c: CoinData) => number }> = [
    { key: "funding", getter: (c) => c.funding_rate },
    { key: "oi_24h",  getter: (c) => c.oi_change_pct_24h },
    { key: "oi_1h",   getter: (c) => c.oi_change_pct_1h },
    { key: "short",   getter: (c) => c.short_ratio },
    { key: "vol",     getter: (c) => c.volume_change_pct },
    { key: "taker",   getter: (c) => c.taker_buy_ratio },
  ];

  for (const { key, getter } of fields) {
    const vals = coins.map(getter);
    const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
    const stdev = Math.sqrt(vals.reduce((a, b) => a + (b - mean) ** 2, 0) / vals.length);
    if (stdev === 0) continue;
    for (let i = 0; i < coins.length; i++) {
      (coins[i] as any)[`z_${key}`] = Math.round(((vals[i] - mean) / stdev) * 100) / 100;
    }
  }

  for (const c of coins) {
    const zVals = fields.map((f) => Math.abs((c as any)[`z_${f.key}`] ?? 0));
    const extremeCount = zVals.filter((v) => v > 1.5).length;
    c.confidence = Math.min(1.0, extremeCount / 4);
  }

  return coins;
}

// ─── Full score pipeline ──────────────────────────────────
export function scoreCoin(partial: Omit<CoinData, "score" | "score_reasons" | "pump_stage" | "confidence" | "squeeze_fuel" | "risk" | "exit_alert">): CoinData {
  let coin: CoinData = {
    ...partial,
    score: 0,
    score_reasons: [],
    pump_stage: "⬜ NEUTRAL",
    confidence: 0,
    squeeze_fuel: 0,
    risk: {
      entry_score: 50, dump_trap_risk: "LOW 🟢", dump_trap_reasons: [],
      recommended_leverage: 1, max_safe_leverage: 1, position_size_usd: 0,
      entry_zone_low: 0, entry_zone_high: 0, stop_loss: 0,
      target_1: 0, target_2: 0, target_3: 0, risk_reward: 0,
      liq_cluster_above: 0, liq_cluster_below: 0, liq_above_usd: 0, liq_below_usd: 0,
      atr_pct: 0, dca_plan: [],
    },
    exit_alert: { should_exit: false, urgency: "HOLD 🟢", exit_reasons: [], exit_score: 0 },
  };

  coin = calculateScoreV4(coin);
  coin = applyFundingVelocityScore(coin);
  const { trapScore } = detectDumpTrap(coin);
  coin.risk        = calculateRiskProfile(coin, trapScore);
  coin.exit_alert  = calculateExitAlert(coin);
  return coin;
}
