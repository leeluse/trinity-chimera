// Crime Pump Hunter V5 — shared types, mock data, helpers

// ─── Signal System ───────────────────────────────────────
export type SignalType =
  | "PRE_IGNITION"
  | "IGNITION"
  | "STAGE_UP"
  | "FUEL_MAX"
  | "SCORE_SPIKE"
  | "EXIT_ALERT"
  | "TRAP_ALERT";

export type SignalPriority = "P0" | "P1" | "P2";

export interface CrimeSignal {
  id: string;           // `${symbol}:${type}:${timestamp}`
  type: SignalType;
  priority: SignalPriority;
  symbol: string;
  exchange: "BYBIT" | "BINANCE";
  message: string;      // "PRE_IGNITION 진입  score 187  연료 91"
  timestamp: number;    // Date.now()
  score: number;
  stage: string;
}

export type ScanStatus = "idle" | "scanning" | "complete" | "error";

export interface ScanProgress {
  current: number;
  total: number;
  estimatedSecondsLeft: number;
}

export interface DcaStep {
  entry: number;
  size_pct: number;
  note: string;
}

export interface RiskProfile {
  entry_score: number;
  dump_trap_risk: string;
  dump_trap_reasons: string[];
  recommended_leverage: number;
  max_safe_leverage: number;
  position_size_usd: number;
  entry_zone_low: number;
  entry_zone_high: number;
  stop_loss: number;
  target_1: number;
  target_2: number;
  target_3: number;
  risk_reward: number;
  liq_cluster_above: number;
  liq_cluster_below: number;
  liq_above_usd: number;
  liq_below_usd: number;
  atr_pct: number;
  dca_plan: DcaStep[];
}

export interface ExitAlert {
  should_exit: boolean;
  urgency: string;
  exit_reasons: string[];
  exit_score: number;
}

export interface FundingHistory {
  rates: number[];
  velocity: number;
  trend: "RISING" | "FALLING" | "FLAT";
}

export interface CoinData {
  symbol: string;
  score: number;
  score_reasons: string[];
  pump_stage: string;
  confidence: number;
  squeeze_fuel: number;
  funding_rate: number;
  oi_change_pct_1h: number;
  oi_change_pct_4h: number;
  oi_change_pct_24h: number;
  long_ratio: number;
  short_ratio: number;
  top_long_ratio: number;
  top_short_ratio: number;
  taker_buy_ratio: number;
  taker_sell_ratio: number;
  book_imbalance: number;
  mark_index_diff_pct: number;
  price: number;
  price_change_1h: number;
  price_change_4h: number;
  price_change_24h: number;
  volume_24h: number;
  volume_change_pct: number;
  atr_pct: number;
  funding_history: FundingHistory;
  risk: RiskProfile;
  exit_alert: ExitAlert;
}

export const CRIME_TARGETS: CoinData[] = [
  {
    symbol: "PEPEUSDT",
    score: 187,
    pump_stage: "💥 PRE_IGNITION",
    confidence: 0.92,
    squeeze_fuel: 91,
    funding_rate: -0.482,
    oi_change_pct_1h: 11.4,
    oi_change_pct_4h: 29.1,
    oi_change_pct_24h: 54.2,
    long_ratio: 33.8,
    short_ratio: 66.2,
    top_long_ratio: 37.4,
    top_short_ratio: 62.6,
    taker_buy_ratio: 63.1,
    taker_sell_ratio: 36.9,
    book_imbalance: 4.28,
    mark_index_diff_pct: -2.14,
    price: 0.00001424,
    price_change_1h: 0.9,
    price_change_4h: 1.3,
    price_change_24h: 2.1,
    volume_24h: 291000000,
    volume_change_pct: 198,
    atr_pct: 6.4,
    score_reasons: [
      "🔴펀딩-0.482%",
      "🔴OI24h+54%",
      "🔴숏66.2%",
      "🔴탑숏62.6%",
      "🟢매수체결63%",
      "🔴Ask극소x4.3",
      "💀매집시그니처",
      "⚡스퀴즈MAX",
      "💥PRE점화",
      "🌀코일극한",
    ],
    funding_history: {
      rates: [-0.21, -0.28, -0.35, -0.39, -0.43, -0.46, -0.482],
      velocity: -0.0385,
      trend: "FALLING",
    },
    risk: {
      entry_score: 84,
      dump_trap_risk: "LOW 🟢",
      dump_trap_reasons: [],
      recommended_leverage: 5,
      max_safe_leverage: 8,
      position_size_usd: 400,
      entry_zone_low: 0.00001417,
      entry_zone_high: 0.00001431,
      stop_loss: 0.00001289,
      target_1: 0.00001559,
      target_2: 0.00001694,
      target_3: 0.00001916,
      risk_reward: 2.92,
      liq_cluster_above: 0.0000178,
      liq_cluster_below: 0.0000118,
      liq_above_usd: 13400000,
      liq_below_usd: 3100000,
      atr_pct: 6.4,
      dca_plan: [
        { entry: 0.0000142, size_pct: 40, note: "시장가 1차" },
        { entry: 0.00001398, size_pct: 35, note: "-1.5% 지정가 2차" },
        { entry: 0.00001377, size_pct: 25, note: "-3.0% 지정가 3차" },
      ],
    },
    exit_alert: { should_exit: false, urgency: "HOLD 🟢", exit_reasons: [], exit_score: 6 },
  },
  {
    symbol: "WIFUSDT",
    score: 162,
    pump_stage: "⚡ SPRING",
    confidence: 0.84,
    squeeze_fuel: 77,
    funding_rate: -0.341,
    oi_change_pct_1h: 9.2,
    oi_change_pct_4h: 22.8,
    oi_change_pct_24h: 41.5,
    long_ratio: 36.4,
    short_ratio: 63.6,
    top_long_ratio: 40.2,
    top_short_ratio: 59.8,
    taker_buy_ratio: 58.7,
    taker_sell_ratio: 41.3,
    book_imbalance: 3.12,
    mark_index_diff_pct: -1.82,
    price: 2.3841,
    price_change_1h: 0.3,
    price_change_4h: 0.7,
    price_change_24h: 1.4,
    volume_24h: 48200000,
    volume_change_pct: 128,
    atr_pct: 4.9,
    score_reasons: [
      "🔴펀딩-0.341%",
      "🔴OI24h+41%",
      "🔴숏63.6%",
      "🟢매수체결59%",
      "🔴Ask극소x3.1",
      "💀매집시그니처",
      "⚡스퀴즈MAX",
      "⚡스프링압축",
    ],
    funding_history: {
      rates: [-0.14, -0.19, -0.24, -0.28, -0.31, -0.34, -0.341],
      velocity: -0.0288,
      trend: "FALLING",
    },
    risk: {
      entry_score: 76,
      dump_trap_risk: "LOW 🟢",
      dump_trap_reasons: [],
      recommended_leverage: 6,
      max_safe_leverage: 10,
      position_size_usd: 480,
      entry_zone_low: 2.372,
      entry_zone_high: 2.396,
      stop_loss: 2.209,
      target_1: 2.559,
      target_2: 2.734,
      target_3: 3.064,
      risk_reward: 2.41,
      liq_cluster_above: 2.84,
      liq_cluster_below: 1.98,
      liq_above_usd: 7200000,
      liq_below_usd: 2400000,
      atr_pct: 4.9,
      dca_plan: [
        { entry: 2.384, size_pct: 40, note: "시장가 1차" },
        { entry: 2.348, size_pct: 35, note: "-1.5% 지정가 2차" },
        { entry: 2.313, size_pct: 25, note: "-3.0% 지정가 3차" },
      ],
    },
    exit_alert: { should_exit: false, urgency: "HOLD 🟢", exit_reasons: [], exit_score: 12 },
  },
  {
    symbol: "BONKUSDT",
    score: 148,
    pump_stage: "🔥 IGNITION",
    confidence: 0.78,
    squeeze_fuel: 68,
    funding_rate: -0.198,
    oi_change_pct_1h: 16.8,
    oi_change_pct_4h: 31.2,
    oi_change_pct_24h: 38.9,
    long_ratio: 38.1,
    short_ratio: 61.9,
    top_long_ratio: 42.3,
    top_short_ratio: 57.7,
    taker_buy_ratio: 64.8,
    taker_sell_ratio: 35.2,
    book_imbalance: 2.74,
    mark_index_diff_pct: -1.44,
    price: 0.0000243,
    price_change_1h: 4.2,
    price_change_4h: 7.8,
    price_change_24h: 3.1,
    volume_24h: 184000000,
    volume_change_pct: 321,
    atr_pct: 7.2,
    score_reasons: [
      "🔴펀딩-0.198%",
      "🔴OI1h+17%",
      "🔴OI24h+39%",
      "🔴숏61.9%",
      "🟢매수체결65%",
      "🔴거래량+321%",
      "🟡1h+4.2%",
      "☠️점화시그니처",
    ],
    funding_history: {
      rates: [-0.08, -0.11, -0.14, -0.16, -0.18, -0.19, -0.198],
      velocity: -0.0182,
      trend: "FALLING",
    },
    risk: {
      entry_score: 68,
      dump_trap_risk: "MEDIUM 🟠",
      dump_trap_reasons: ["🟠4h+7.8% 단기 과열"],
      recommended_leverage: 4,
      max_safe_leverage: 7,
      position_size_usd: 320,
      entry_zone_low: 0.00002418,
      entry_zone_high: 0.00002442,
      stop_loss: 0.00002178,
      target_1: 0.00002672,
      target_2: 0.00002921,
      target_3: 0.0000330,
      risk_reward: 2.18,
      liq_cluster_above: 0.0000298,
      liq_cluster_below: 0.0000192,
      liq_above_usd: 9800000,
      liq_below_usd: 1900000,
      atr_pct: 7.2,
      dca_plan: [
        { entry: 0.0000243, size_pct: 40, note: "시장가 1차" },
        { entry: 0.0000239, size_pct: 35, note: "-1.5% 지정가 2차" },
        { entry: 0.0000236, size_pct: 25, note: "-3.0% 지정가 3차" },
      ],
    },
    exit_alert: {
      should_exit: false,
      urgency: "WATCH 👀",
      exit_reasons: ["📈펀딩 빠른 상승 → 탈출 준비"],
      exit_score: 28,
    },
  },
  {
    symbol: "FLOKIUSDT",
    score: 124,
    pump_stage: "🟢 ACCUMULATE",
    confidence: 0.71,
    squeeze_fuel: 58,
    funding_rate: -0.274,
    oi_change_pct_1h: 6.4,
    oi_change_pct_4h: 18.1,
    oi_change_pct_24h: 32.4,
    long_ratio: 41.2,
    short_ratio: 58.8,
    top_long_ratio: 43.8,
    top_short_ratio: 56.2,
    taker_buy_ratio: 56.2,
    taker_sell_ratio: 43.8,
    book_imbalance: 2.18,
    mark_index_diff_pct: -0.88,
    price: 0.0001847,
    price_change_1h: -0.4,
    price_change_4h: 0.8,
    price_change_24h: 1.2,
    volume_24h: 62400000,
    volume_change_pct: 84,
    atr_pct: 5.1,
    score_reasons: [
      "🔴펀딩-0.274%",
      "🟠OI24h+32%",
      "🟠숏58.8%",
      "💀매집시그니처",
      "📉펀딩가속↓-0.0241",
    ],
    funding_history: {
      rates: [-0.12, -0.16, -0.19, -0.22, -0.24, -0.26, -0.274],
      velocity: -0.0241,
      trend: "FALLING",
    },
    risk: {
      entry_score: 71,
      dump_trap_risk: "LOW 🟢",
      dump_trap_reasons: [],
      recommended_leverage: 7,
      max_safe_leverage: 10,
      position_size_usd: 560,
      entry_zone_low: 0.00018396,
      entry_zone_high: 0.00018544,
      stop_loss: 0.00016971,
      target_1: 0.00020239,
      target_2: 0.00021631,
      target_3: 0.00024108,
      risk_reward: 2.52,
      liq_cluster_above: 0.000224,
      liq_cluster_below: 0.000152,
      liq_above_usd: 4200000,
      liq_below_usd: 1100000,
      atr_pct: 5.1,
      dca_plan: [
        { entry: 0.0001847, size_pct: 40, note: "시장가 1차" },
        { entry: 0.0001819, size_pct: 35, note: "-1.5% 지정가 2차" },
        { entry: 0.0001791, size_pct: 25, note: "-3.0% 지정가 3차" },
      ],
    },
    exit_alert: { should_exit: false, urgency: "HOLD 🟢", exit_reasons: [], exit_score: 9 },
  },
  {
    symbol: "MEWUSDT",
    score: 108,
    pump_stage: "⚡ SPRING",
    confidence: 0.65,
    squeeze_fuel: 51,
    funding_rate: -0.192,
    oi_change_pct_1h: 8.9,
    oi_change_pct_4h: 21.4,
    oi_change_pct_24h: 44.8,
    long_ratio: 40.4,
    short_ratio: 59.6,
    top_long_ratio: 42.1,
    top_short_ratio: 57.9,
    taker_buy_ratio: 55.4,
    taker_sell_ratio: 44.6,
    book_imbalance: 1.94,
    mark_index_diff_pct: -1.12,
    price: 0.008412,
    price_change_1h: 0.2,
    price_change_4h: 0.5,
    price_change_24h: 0.9,
    volume_24h: 29800000,
    volume_change_pct: 67,
    atr_pct: 5.8,
    score_reasons: [
      "🔴펀딩-0.192%",
      "🟠OI24h+45%",
      "🟠숏59.6%",
      "⚡스프링압축",
      "💀매집시그니처",
    ],
    funding_history: {
      rates: [-0.08, -0.11, -0.13, -0.15, -0.17, -0.18, -0.192],
      velocity: -0.0164,
      trend: "FALLING",
    },
    risk: {
      entry_score: 64,
      dump_trap_risk: "LOW 🟢",
      dump_trap_reasons: [],
      recommended_leverage: 8,
      max_safe_leverage: 10,
      position_size_usd: 640,
      entry_zone_low: 0.008370,
      entry_zone_high: 0.008454,
      stop_loss: 0.007924,
      target_1: 0.008900,
      target_2: 0.009388,
      target_3: 0.010420,
      risk_reward: 1.97,
      liq_cluster_above: 0.01024,
      liq_cluster_below: 0.00712,
      liq_above_usd: 2800000,
      liq_below_usd: 800000,
      atr_pct: 5.8,
      dca_plan: [
        { entry: 0.008412, size_pct: 40, note: "시장가 1차" },
        { entry: 0.008286, size_pct: 35, note: "-1.5% 지정가 2차" },
        { entry: 0.008160, size_pct: 25, note: "-3.0% 지정가 3차" },
      ],
    },
    exit_alert: { should_exit: false, urgency: "HOLD 🟢", exit_reasons: [], exit_score: 14 },
  },
  {
    symbol: "ORDIUSDT",
    score: 92,
    pump_stage: "🟢 ACCUMULATE",
    confidence: 0.58,
    squeeze_fuel: 44,
    funding_rate: -0.154,
    oi_change_pct_1h: 4.8,
    oi_change_pct_4h: 14.2,
    oi_change_pct_24h: 27.1,
    long_ratio: 43.2,
    short_ratio: 56.8,
    top_long_ratio: 44.9,
    top_short_ratio: 55.1,
    taker_buy_ratio: 54.2,
    taker_sell_ratio: 45.8,
    book_imbalance: 1.72,
    mark_index_diff_pct: -0.64,
    price: 24.82,
    price_change_1h: -0.8,
    price_change_4h: 0.4,
    price_change_24h: -1.2,
    volume_24h: 18400000,
    volume_change_pct: 42,
    atr_pct: 4.4,
    score_reasons: [
      "🟠펀딩-0.154%",
      "🟠OI24h+27%",
      "🟠숏56.8%",
      "💀매집시그니처",
    ],
    funding_history: {
      rates: [-0.07, -0.09, -0.11, -0.12, -0.13, -0.14, -0.154],
      velocity: -0.0128,
      trend: "FALLING",
    },
    risk: {
      entry_score: 58,
      dump_trap_risk: "LOW 🟢",
      dump_trap_reasons: [],
      recommended_leverage: 9,
      max_safe_leverage: 10,
      position_size_usd: 720,
      entry_zone_low: 24.70,
      entry_zone_high: 24.94,
      stop_loss: 23.73,
      target_1: 25.91,
      target_2: 27.00,
      target_3: 28.90,
      risk_reward: 1.72,
      liq_cluster_above: 28.4,
      liq_cluster_below: 20.8,
      liq_above_usd: 1800000,
      liq_below_usd: 600000,
      atr_pct: 4.4,
      dca_plan: [
        { entry: 24.82, size_pct: 40, note: "시장가 1차" },
        { entry: 24.45, size_pct: 35, note: "-1.5% 지정가 2차" },
        { entry: 24.08, size_pct: 25, note: "-3.0% 지정가 3차" },
      ],
    },
    exit_alert: { should_exit: false, urgency: "HOLD 🟢", exit_reasons: [], exit_score: 18 },
  },
  {
    symbol: "NEIROUSDT",
    score: 78,
    pump_stage: "🟢 ACCUMULATE",
    confidence: 0.52,
    squeeze_fuel: 36,
    funding_rate: -0.128,
    oi_change_pct_1h: 3.4,
    oi_change_pct_4h: 11.8,
    oi_change_pct_24h: 22.4,
    long_ratio: 45.1,
    short_ratio: 54.9,
    top_long_ratio: 46.8,
    top_short_ratio: 53.2,
    taker_buy_ratio: 52.8,
    taker_sell_ratio: 47.2,
    book_imbalance: 1.48,
    mark_index_diff_pct: -0.41,
    price: 0.0421,
    price_change_1h: 0.1,
    price_change_4h: -0.3,
    price_change_24h: -0.8,
    volume_24h: 8200000,
    volume_change_pct: 28,
    atr_pct: 3.9,
    score_reasons: [
      "🟠펀딩-0.128%",
      "🟠OI24h+22%",
      "🟠숏54.9%",
    ],
    funding_history: {
      rates: [-0.05, -0.07, -0.09, -0.10, -0.11, -0.12, -0.128],
      velocity: -0.0104,
      trend: "FALLING",
    },
    risk: {
      entry_score: 52,
      dump_trap_risk: "LOW 🟢",
      dump_trap_reasons: [],
      recommended_leverage: 10,
      max_safe_leverage: 10,
      position_size_usd: 800,
      entry_zone_low: 0.04189,
      entry_zone_high: 0.04231,
      stop_loss: 0.039468,
      target_1: 0.044732,
      target_2: 0.047364,
      target_3: 0.052300,
      risk_reward: 1.58,
      liq_cluster_above: 0.0498,
      liq_cluster_below: 0.0342,
      liq_above_usd: 920000,
      liq_below_usd: 280000,
      atr_pct: 3.9,
      dca_plan: [
        { entry: 0.0421, size_pct: 40, note: "시장가 1차" },
        { entry: 0.04147, size_pct: 35, note: "-1.5% 지정가 2차" },
        { entry: 0.04084, size_pct: 25, note: "-3.0% 지정가 3차" },
      ],
    },
    exit_alert: { should_exit: false, urgency: "HOLD 🟢", exit_reasons: [], exit_score: 11 },
  },
];

// helpers
export function fmtPrice(p: number): string {
  if (p <= 0) return "—";
  if (p >= 100) return `$${p.toFixed(2)}`;
  if (p >= 1) return `$${p.toFixed(4)}`;
  if (p >= 0.01) return `$${p.toFixed(6)}`;
  if (p >= 0.0001) return `$${p.toFixed(8)}`;
  return `$${p.toExponential(3)}`;
}

export function fmtVol(n: number): string {
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

export function stageColor(stage: string) {
  if (stage.includes("PRE_IGNITION"))
    return { dot: "bg-pink-400", text: "text-pink-300", border: "border-pink-500/35", bg: "bg-pink-500/10", glow: "shadow-[0_0_8px_rgba(244,114,182,0.2)]" };
  if (stage.includes("IGNITION"))
    return { dot: "bg-fuchsia-400", text: "text-fuchsia-300", border: "border-fuchsia-500/35", bg: "bg-fuchsia-500/10", glow: "shadow-[0_0_8px_rgba(217,70,239,0.2)]" };
  if (stage.includes("SPRING"))
    return { dot: "bg-violet-400", text: "text-violet-300", border: "border-violet-500/30", bg: "bg-violet-500/10", glow: "" };
  if (stage.includes("ACCUMULATE"))
    return { dot: "bg-purple-400", text: "text-purple-300", border: "border-purple-500/30", bg: "bg-purple-500/10", glow: "" };
  if (stage.includes("DISTRIBUTE"))
    return { dot: "bg-white/20", text: "text-white/35", border: "border-white/10", bg: "bg-white/[0.03]", glow: "" };
  return { dot: "bg-white/15", text: "text-white/25", border: "border-white/[0.07]", bg: "bg-white/[0.02]", glow: "" };
}

export function trapColor(risk: string) {
  if (risk.includes("CRITICAL")) return "text-pink-400";
  if (risk.includes("HIGH"))     return "text-fuchsia-400";
  if (risk.includes("MEDIUM"))   return "text-purple-400";
  return "text-white/40";
}

export function scoreDanger(score: number) {
  if (score >= 150) return { label: "☠️ CRITICAL", cls: "text-pink-400",    barCls: "from-pink-500 to-fuchsia-400" };
  if (score >= 100) return { label: "🔴 DANGER",   cls: "text-fuchsia-400", barCls: "from-fuchsia-600 to-purple-400" };
  if (score >= 70)  return { label: "🟠 HIGH",     cls: "text-purple-400",  barCls: "from-purple-600 to-violet-400" };
  return                   { label: "🟡 WATCH",    cls: "text-violet-400",  barCls: "from-violet-700 to-purple-500" };
}
