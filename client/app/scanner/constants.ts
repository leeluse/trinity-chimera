export const CONFIG = {
  API_BASE: "https://fapi.binance.com",
  TOP_N_DISPLAY: 40,
  PHASE1_TOP_N: 70,
  MAX_SYMBOLS: 400,
  AUTO_REFRESH_MS: 120000,
  BATCH_SIZE: 12,
  BATCH_DELAY_MS: 250,
  MIN_QUOTE_VOLUME: 5_000_000,
  BTC_SYMBOL: "BTCUSDT",
  ETH_SYMBOL: "ETHUSDT",
};

export const SECTORS: Record<string, string> = {
  BTCUSDT: "L1", ETHUSDT: "L1", SOLUSDT: "L1", AVAXUSDT: "L1",
  BNBUSDT: "L1", ADAUSDT: "L1", NEARUSDT: "L1", APTUSDT: "L1",
  SUIUSDT: "L1", TIAUSDT: "L1", SEIUSDT: "L1", INJUSDT: "L1",
  ATOMUSDT: "L1", DOTUSDT: "L1", TRXUSDT: "L1", XRPUSDT: "L1",
  TONUSDT: "L1", FTMUSDT: "L1", KASUSDT: "L1", ICPUSDT: "L1",
  ARBUSDT: "L2", OPUSDT: "L2", MATICUSDT: "L2", STRKUSDT: "L2",
  IMXUSDT: "L2", METISUSDT: "L2", MANTAUSDT: "L2", BLASTUSDT: "L2",
  FETUSDT: "AI", AGIXUSDT: "AI", RENDERUSDT: "AI", RNDRUSDT: "AI",
  WLDUSDT: "AI", TAOUSDT: "AI", OCEANUSDT: "AI", ARKMUSDT: "AI",
  DOGEUSDT: "MEME", SHIBUSDT: "MEME", PEPEUSDT: "MEME", WIFUSDT: "MEME",
  BONKUSDT: "MEME", FLOKIUSDT: "MEME", MEMEUSDT: "MEME", BOMEUSDT: "MEME",
  UNIUSDT: "DEFI", AAVEUSDT: "DEFI", MKRUSDT: "DEFI", CRVUSDT: "DEFI",
  COMPUSDT: "DEFI", SUSHIUSDT: "DEFI", SNXUSDT: "DEFI", LDOUSDT: "DEFI",
  PENDLEUSDT: "DEFI", GMXUSDT: "DEFI", JUPUSDT: "DEFI", ENAUSDT: "DEFI",
  ONDOUSDT: "RWA", POLYXUSDT: "RWA", RSRUSDT: "RWA",
  GALAUSDT: "GAME", APEUSDT: "GAME", AXSUSDT: "GAME", SANDUSDT: "GAME",
  MANAUSDT: "GAME", ILVUSDT: "GAME", GMTUSDT: "GAME", MAGICUSDT: "GAME",
  HNTUSDT: "DEPIN", AKTUSDT: "DEPIN", FILUSDT: "DEPIN", ARUSDT: "DEPIN",
  LINKUSDT: "INFRA", GRTUSDT: "INFRA", QNTUSDT: "INFRA", RUNEUSDT: "INFRA",
};

export const MODE_WEIGHTS: Record<string, Record<string, number>> = {
  momentum:    { momentum: 1.8, volume: 1.4, breakout: 0.9, compression: 0.4, funding: 0.5, oi: 0.6, capitulation: 0.3, early: 1.3 },
  breakout:    { momentum: 0.8, volume: 1.2, breakout: 1.8, compression: 1.3, funding: 0.5, oi: 0.8, capitulation: 0.4, early: 1.0 },
  reversal:    { momentum: 0.2, volume: 0.8, breakout: 0.4, compression: 0.5, funding: 1.0, oi: 0.8, capitulation: 1.8, early: 0.3 },
  compression: { momentum: 0.4, volume: 0.7, breakout: 1.0, compression: 2.0, funding: 0.6, oi: 0.8, capitulation: 0.3, early: 0.8 },
};

export const SIGNAL_META: { key: string; emoji: string; name: string; color: string }[] = [
  { key: "momentum",     emoji: "🚀", name: "모멘텀",     color: "var(--accent-blue)" },
  { key: "volume",       emoji: "🔥", name: "거래량",     color: "var(--accent-pink)" },
  { key: "breakout",     emoji: "💎", name: "브레이크아웃", color: "var(--accent-teal)" },
  { key: "compression",  emoji: "🎯", name: "압축",       color: "var(--accent-orange)" },
  { key: "funding",      emoji: "⚡", name: "펀딩",       color: "var(--accent-purple)" },
  { key: "oi",           emoji: "🧲", name: "OI",         color: "var(--accent-blue)" },
  { key: "capitulation", emoji: "💀", name: "청산",       color: "var(--accent-red)" },
  { key: "early",        emoji: "🌊", name: "조기",       color: "var(--accent-teal)" },
  { key: "flow",         emoji: "🌀", name: "플로우",     color: "var(--accent-cyan)" },
  { key: "volSurge",     emoji: "📈", name: "거래량급등",  color: "var(--accent-orange)" },
];
