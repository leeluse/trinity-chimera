export const COLORS = [
  '#4acde2', // Sophisticated Aqua Blue
  '#c678dd', // One Dark Purple
  '#90d579ff', // Maven Green (NIM-ALPHA)
  '#9f7aea', // Vibrant Purple
  '#5c6370'  // One Dark Gray (Benchmark)
];

export const NAMES = ['NaN', 'NaN', 'NaN', 'NaN', 'BTC BnH'];

export const SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"];
export const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h"] as const;
export const LEVERAGES = [1, 3, 5, 10, 20];

export const HINT_MAP = {
  equity: '현재 총 평가 자산 (USDT)',
  return: '누적 일별 수익률 (%)',
  sharpe: '롤링 샤프지수 (일간 추정)',
  mdd: '누적 최대 낙폭 (MDD, 매일 갱신)',
  win: '누적 승률 % (일별 롤링)',
};