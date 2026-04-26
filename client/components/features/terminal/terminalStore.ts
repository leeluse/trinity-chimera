import { create } from 'zustand';

import type { HunterRow, HunterRegime } from './hunterRuntime';

export interface HunterAlert {
  sym: string;
  full: string;
  stage: number;
  dir: number;
  ts: number;
}

export interface TerminalResult {
  symbol: string;
  pricePct: number;
  alphaScore: number;
  verdict: string;
  vClass: string;
  allSigs: any[];
  note: string;
  setupTag: string;
  wyckoffScore: number;
  vwapScore: number;
  rsScore: number;
  mtfScore: number;
  cvdScore: number;
  realLiqScore: number;
  bbScore: number;
  atrScore: number;
  brkScore: number;
  flowScore: number;
  surgeScore: number;
  momScore: number;
  kimchiScore: number;
  fr: number;
  oiChangePct: number;
  oiVals: number[];
  currentPrice: number | null;
  extremeFR: boolean;
  layers: any;
}

export interface GlobalMetrics {
  fearGreed: number;
  fearGreedLabel: string;
  usdKrw: number;
  btcTx: number;
  btcTxLabel: string;
  mempoolFees: number;
  mempoolFeesLabel: string;
  globalShortLiq: string;
  globalLongLiq: string;
  wsStatus: 'LIVE' | 'OFF' | 'CONNECTING';
}

export interface SummaryStats {
  strongBull: number;
  bull: number;
  neutral: number;
  bear: number;
  strongBear: number;
  total: number;
  wyckoff: number;
  mtf: number;
  squeeze: number;
  liquidation: number;
}

interface TerminalState {
  // Data
  results: TerminalResult[];
  filteredResults: TerminalResult[];
  globalMetrics: GlobalMetrics;
  summaryStats: SummaryStats;

  // UI State
  isRunning: boolean;
  progress: number;
  statusMessage: string;
  activeFilter: string;
  searchQuery: string;
  selectedSymbol: string | null;
  sort: { col: keyof TerminalResult | string; dir: number };
  engineApi: any | null;
  hunterRows: HunterRow[];
  hunterRegime: HunterRegime | null;
  hunterAlert: HunterAlert | null;

  // Actions
  setResults: (results: TerminalResult[]) => void;
  updateGlobalMetrics: (metrics: Partial<GlobalMetrics>) => void;
  updateStatus: (progress: number, message: string) => void;
  updateSummaryStats: (stats: Partial<SummaryStats>) => void;
  setIsRunning: (isRunning: boolean) => void;
  setFilter: (filter: string) => void;
  setSearchQuery: (query: string) => void;
  setSort: (col: string, dir?: number) => void;
  setSelectedSymbol: (symbol: string | null) => void;
  setEngineApi: (api: any) => void;
  setHunterRows: (rows: HunterRow[]) => void;
  setHunterRegime: (regime: HunterRegime) => void;
  setHunterAlert: (alert: HunterAlert | null) => void;
  
  // Computed
  applyFilters: () => void;
}

export const useTerminalStore = create<TerminalState>((set, get) => ({
  results: [],
  filteredResults: [],
  globalMetrics: {
    fearGreed: 50,
    fearGreedLabel: '—',
    usdKrw: 1350,
    btcTx: 0,
    btcTxLabel: '—',
    mempoolFees: 0,
    mempoolFeesLabel: '—',
    globalShortLiq: '$0K',
    globalLongLiq: '$0K',
    wsStatus: 'CONNECTING',
  },
  summaryStats: {
    strongBull: 0, bull: 0, neutral: 0, bear: 0, strongBear: 0,
    total: 0, wyckoff: 0, mtf: 0, squeeze: 0, liquidation: 0,
  },
  isRunning: false,
  progress: 0,
  statusMessage: 'System Standby',
  activeFilter: 'ALL',
  searchQuery: '',
  selectedSymbol: null,
  sort: { col: 'alphaScore', dir: -1 },
  engineApi: null,
  hunterRows: [],
  hunterRegime: null,
  hunterAlert: null,

  setResults: (results) => {
    set({ results });
    get().applyFilters();
  },

  updateGlobalMetrics: (metrics) => set((state) => ({
    globalMetrics: { ...state.globalMetrics, ...metrics }
  })),

  updateStatus: (progress, message) => set({ progress, statusMessage: message }),

  updateSummaryStats: (stats) => set((state) => ({
    summaryStats: { ...state.summaryStats, ...stats }
  })),

  setIsRunning: (isRunning) => set({ isRunning }),

  setFilter: (activeFilter) => {
    set({ activeFilter });
    get().applyFilters();
  },

  setSearchQuery: (searchQuery) => {
    set({ searchQuery });
    get().applyFilters();
  },

  setSort: (col, dir) => {
    const currentSort = get().sort;
    const direction = dir !== undefined ? dir : (currentSort.col === col ? currentSort.dir * -1 : -1);
    set({ sort: { col, dir: direction } });
    get().applyFilters();
  },

  setSelectedSymbol: (selectedSymbol) => set({ selectedSymbol }),

  setHunterRows: (hunterRows) => set({ hunterRows }),
  setHunterRegime: (hunterRegime) => set({ hunterRegime }),
  setHunterAlert: (hunterAlert) => set({ hunterAlert }),

  applyFilters: () => {
    const { results, activeFilter, searchQuery, sort } = get();
    
    let filtered = [...results];
    
    // Filter by setupTag
    if (activeFilter !== 'ALL') {
      filtered = filtered.filter(r => r.setupTag === activeFilter);
    }
    
    // Filter by search query
    if (searchQuery) {
      const q = searchQuery.toLowerCase().trim();
      filtered = filtered.filter(r => r.symbol.toLowerCase().includes(q));
    }
    
    // Sort
    const { col, dir } = sort;
    filtered.sort((a, b) => {
      let av = (a as any)[col] ?? 0;
      let bv = (b as any)[col] ?? 0;
      
      if (typeof av === 'string') {
        av = av.toLowerCase();
        bv = bv.toLowerCase();
      }
      
      if (av < bv) return dir;
      if (av > bv) return -dir;
      return 0;
    });
    
    set({ filteredResults: filtered });
  },

  setEngineApi: (engineApi) => set({ engineApi }),
}));
