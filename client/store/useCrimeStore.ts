import { create } from "zustand";
import { CoinData, CrimeSignal, ScanStatus, ScanProgress, CRIME_TARGETS } from "@/components/features/crime/crimeData";
import { detectSignals } from "@/components/features/crime/signalEngine";
import { runFullScan } from "@/components/features/crime/engine/crimeEngine";

// AbortController reference kept outside store to cancel in-flight scans
let scanAbortController: AbortController | null = null;

interface CrimeState {
  // scan
  status: ScanStatus;
  progress: ScanProgress;
  bybitEnabled: boolean;
  binanceEnabled: boolean;
  results: CoinData[];          // ranked by score desc
  previousResults: CoinData[] | null;
  nextScanIn: number;           // seconds until next auto scan
  lastScanAt: string;           // "04:28 UTC"

  // signals
  signals: CrimeSignal[];       // most recent first, max 50
  p0Banner: CrimeSignal | null; // latest P0 signal (null = dismissed)

  // selection (from left table)
  selectedSymbol: string | null;

  // actions
  toggleBybit: () => void;
  toggleBinance: () => void;
  startScan: () => void;
  stopScan: () => void;
  setProgress: (p: ScanProgress) => void;
  setResults: (coins: CoinData[]) => void;
  dismissBanner: () => void;
  selectSymbol: (symbol: string | null) => void;
  tickCountdown: () => void;
  runScan: () => Promise<void>;
  // kept for fallback / testing
  runMockScan: () => Promise<void>;
}

const SCAN_INTERVAL_SEC = 300; // 5 minutes

export const useCrimeStore = create<CrimeState>((set, get) => ({
  status: "idle",
  progress: { current: 0, total: 0, estimatedSecondsLeft: 0 },
  bybitEnabled: true,
  binanceEnabled: true,
  results: CRIME_TARGETS,       // start with mock data
  previousResults: null,
  nextScanIn: 0,
  lastScanAt: "",
  signals: [],
  p0Banner: null,
  selectedSymbol: null,

  toggleBybit: () => set((s) => ({ bybitEnabled: !s.bybitEnabled })),
  toggleBinance: () => set((s) => ({ binanceEnabled: !s.binanceEnabled })),

  startScan: () =>
    set({
      status: "scanning",
      progress: { current: 0, total: 0, estimatedSecondsLeft: 0 },
    }),

  stopScan: () => {
    scanAbortController?.abort();
    scanAbortController = null;
    set({ status: "idle", nextScanIn: 0 });
  },

  setProgress: (p) => set({ progress: p }),

  setResults: (coins) => {
    const { previousResults, signals: prevSignals } = get();
    const ranked = [...coins].sort((a, b) => b.score - a.score);

    // detect signals vs previous scan
    const newSignals = detectSignals(ranked, previousResults);
    const latestP0 = newSignals.find((s) => s.priority === "P0") ?? null;

    // update tab title for P0
    if (latestP0 && typeof document !== "undefined") {
      document.title = `🔴 ${latestP0.symbol} ${latestP0.type} — Crime Hunter`;
    }

    const now = new Date();
    const utc = now.toISOString().slice(11, 16) + " UTC";

    set({
      results: ranked,
      previousResults: ranked,
      status: "complete",
      nextScanIn: SCAN_INTERVAL_SEC,
      lastScanAt: utc,
      signals: [...newSignals, ...prevSignals].slice(0, 50),
      p0Banner: latestP0 ?? get().p0Banner,
    });
  },

  dismissBanner: () => {
    if (typeof document !== "undefined") {
      document.title = "Crime Hunter — V5";
    }
    set({ p0Banner: null });
  },

  selectSymbol: (symbol) => set({ selectedSymbol: symbol }),

  tickCountdown: () =>
    set((s) => {
      if (s.nextScanIn <= 0) return {};
      return { nextScanIn: s.nextScanIn - 1 };
    }),

  runScan: async () => {
    const state = get();
    if (state.status === "scanning") return;

    scanAbortController?.abort();
    scanAbortController = new AbortController();
    const { signal } = scanAbortController;

    set({ status: "scanning", progress: { current: 0, total: 0, estimatedSecondsLeft: 0 } });

    try {
      const coins = await runFullScan({
        bybit:   state.bybitEnabled,
        binance: state.binanceEnabled,
        signal,
        onProgress: (done, total) => {
          const remaining = Math.round(((total - done) / Math.max(total, 1)) * 90);
          get().setProgress({ current: done, total, estimatedSecondsLeft: remaining });
        },
      });

      if (signal.aborted) return;
      if (coins.length > 0) get().setResults(coins);
      else set({ status: "complete", nextScanIn: 300 });
    } catch {
      if (!signal.aborted) set({ status: "error" as ScanStatus });
    }
  },

  runMockScan: async () => {
    const { setProgress, setResults, status } = get();
    if (status === "scanning") return;

    set({ status: "scanning", progress: { current: 0, total: 284, estimatedSecondsLeft: 45 } });

    // 진행 시뮬레이션 (배치 단위로 점프)
    const total = 284;
    const steps = [40, 80, 120, 160, 200, 240, 284];
    for (const step of steps) {
      await new Promise((r) => setTimeout(r, 600));
      if (get().status !== "scanning") return; // stop 눌렸으면 중단
      const remaining = Math.round(((total - step) / total) * 45);
      setProgress({ current: step, total, estimatedSecondsLeft: remaining });
    }

    await new Promise((r) => setTimeout(r, 400));
    if (get().status !== "scanning") return;

    // 실제 데이터 대신 mock에 약간의 변동 추가 (스캔 결과 시뮬레이션)
    const varied = CRIME_TARGETS.map((c) => ({
      ...c,
      score: c.score + Math.round((Math.random() - 0.4) * 15),
      squeeze_fuel: Math.min(100, Math.max(0, c.squeeze_fuel + Math.round((Math.random() - 0.3) * 8))),
      funding_rate: +(c.funding_rate + (Math.random() - 0.5) * 0.02).toFixed(4),
      oi_change_pct_1h: +(c.oi_change_pct_1h + (Math.random() - 0.4) * 2).toFixed(1),
    }));

    setResults(varied);
  },
}));
