export interface Ticker {
  symbol: string;
  price: number;
  change24: number;
  change7d?: number;
  change1h?: number;
  change4h?: number;
  quoteVolume: number;
  high24: number;
  low24: number;
  funding: number | null;
  volRatio?: number;
  oiChange24?: number;
  dailyCloses?: number[];
  hourlyCloses?: number[];
}

export interface Signal {
  score: number;
  note?: string;
}

export interface Candidate extends Ticker {
  score: number;
  signals: Record<string, Signal>;
  strongCount: number;
  pumpFlagged: boolean;
  narrativeMult: number;
  sector: string;
}

export interface SectorData {
  tokens: string[];
  sum24: number;
  sum7d: number;
  count: number;
  avg24: number;
  avg7d: number;
  momentum: number;
}
