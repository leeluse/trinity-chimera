import { create } from "zustand";
import { CoinData, CrimeSignal, ScanStatus, ScanProgress, CRIME_TARGETS } from "@/components/features/crime/crimeData";
import { detectSignals } from "@/components/features/crime/signalEngine";
import { CrimeWsEngine, WsStatus } from "@/components/features/crime/engine/crimeWsEngine";

// WS 엔진 인스턴스 — 스토어 외부에서 관리 (리렌더 방지)
let _engine: CrimeWsEngine | null = null;

interface CrimeState {
  // 스캔 상태
  status:            ScanStatus;
  wsStatus:          WsStatus;       // WS 연결 세부 상태
  wsSymbolCount:     number;         // WS로 수신된 심볼 수
  errorMessage:      string;
  scanCooldownUntil: number;
  progress:          ScanProgress;
  binanceEnabled:    boolean;
  bybitEnabled:      boolean;
  results:           CoinData[];
  previousResults:   CoinData[] | null;
  nextScanIn:        number;
  lastScanAt:        string;

  // 시그널
  signals:  CrimeSignal[];
  p0Banner: CrimeSignal | null;

  // 선택
  selectedSymbol: string | null;

  // 액션
  toggleBybit:   () => void;
  toggleBinance: () => void;
  startEngine:   () => void;
  stopEngine:    () => void;
  setProgress:   (p: ScanProgress) => void;
  setResults:    (coins: CoinData[]) => void;
  dismissBanner: () => void;
  selectSymbol:  (symbol: string | null) => void;
  tickCountdown: () => void;

  // 하위 호환 (UI에서 runScan / stopScan 호출)
  runScan:     () => void;
  stopScan:    () => void;
  runMockScan: () => Promise<void>;
}

const SCAN_INTERVAL_SEC = 300;

export const useCrimeStore = create<CrimeState>((set, get) => ({
  status:            "idle",
  wsStatus:          "idle",
  wsSymbolCount:     0,
  errorMessage:      "",
  scanCooldownUntil: 0,
  progress:          { current: 0, total: 0, estimatedSecondsLeft: 0 },
  binanceEnabled:    true,
  bybitEnabled:      true,
  results:           [],
  previousResults:   null,
  nextScanIn:        0,
  lastScanAt:        "",
  signals:           [],
  p0Banner:          null,
  selectedSymbol:    null,

  toggleBybit:   () => set((s) => ({ bybitEnabled: !s.bybitEnabled })),
  toggleBinance: () => set((s) => ({ binanceEnabled: !s.binanceEnabled })),

  // ── WS 엔진 시작 ─────────────────────────────────────────
  startEngine: () => {
    if (_engine) {
      _engine.stop();
      _engine = null;
    }

    _engine = new CrimeWsEngine({
      onStatus: (ws, msg) => {
        const scanStatus: ScanStatus =
          ws === "scanning"    ? "scanning"
          : ws === "error"     ? "error"
          : ws === "live"      ? "complete"
          : ws === "connecting" ? "scanning"
          : "idle";

        set({
          wsStatus:     ws,
          errorMessage: msg ?? "",
          status:       scanStatus,
          ...(ws === "live" && { nextScanIn: SCAN_INTERVAL_SEC }),
        });
      },
      onProgress: (done, total) => {
        const remaining = Math.round(((total - done) / Math.max(total, 1)) * 90);
        set({ progress: { current: done, total, estimatedSecondsLeft: remaining } });
      },
      onResults: (coins) => {
        get().setResults(coins);
      },
    });

    set({
      status:       "scanning",
      wsStatus:     "connecting",
      errorMessage: "",
      progress:     { current: 0, total: 0, estimatedSecondsLeft: 0 },
    });
    _engine.start();
  },

  // ── WS 엔진 정지 ─────────────────────────────────────────
  stopEngine: () => {
    _engine?.stop();
    _engine = null;
    set({ status: "idle", wsStatus: "idle", nextScanIn: 0, wsSymbolCount: 0 });
  },

  // ── 결과 처리 (시그널 감지 포함) ──────────────────────────
  setResults: (coins) => {
    const { previousResults, signals: prevSignals } = get();
    const ranked = [...coins].sort((a, b) => b.score - a.score);

    const newSignals = detectSignals(ranked, previousResults);
    const latestP0   = newSignals.find((s) => s.priority === "P0") ?? null;

    if (latestP0 && typeof document !== "undefined") {
      document.title = `🔴 ${latestP0.symbol} ${latestP0.type} — Crime Hunter`;
    }

    const now = new Date();
    const utc = now.toISOString().slice(11, 16) + " UTC";

    set({
      results:         ranked,
      previousResults: ranked,
      status:          "complete",
      lastScanAt:      utc,
      nextScanIn:      SCAN_INTERVAL_SEC,
      signals:         [...newSignals, ...prevSignals].slice(0, 50),
      p0Banner:        latestP0 ?? get().p0Banner,
    });
  },

  dismissBanner: () => {
    if (typeof document !== "undefined") document.title = "Crime Hunter — V5";
    set({ p0Banner: null });
  },

  selectSymbol: (symbol) => set({ selectedSymbol: symbol }),

  setProgress: (p) => set({ progress: p }),

  tickCountdown: () =>
    set((s) => {
      if (s.nextScanIn <= 0) return {};
      return { nextScanIn: s.nextScanIn - 1 };
    }),

  // ── 하위 호환 래퍼 ────────────────────────────────────────
  runScan:  () => get().startEngine(),
  stopScan: () => get().stopEngine(),

  runMockScan: async () => {
    const { setProgress, setResults, status } = get();
    if (status === "scanning") return;

    set({ status: "scanning", progress: { current: 0, total: 284, estimatedSecondsLeft: 45 } });

    const total = 284;
    const steps = [40, 80, 120, 160, 200, 240, 284];
    for (const step of steps) {
      await new Promise((r) => setTimeout(r, 600));
      if (get().status !== "scanning") return;
      const remaining = Math.round(((total - step) / total) * 45);
      setProgress({ current: step, total, estimatedSecondsLeft: remaining });
    }

    await new Promise((r) => setTimeout(r, 400));
    if (get().status !== "scanning") return;

    const varied = CRIME_TARGETS.map((c) => ({
      ...c,
      score:            c.score + Math.round((Math.random() - 0.4) * 15),
      squeeze_fuel:     Math.min(100, Math.max(0, c.squeeze_fuel + Math.round((Math.random() - 0.3) * 8))),
      funding_rate:     +(c.funding_rate + (Math.random() - 0.5) * 0.02).toFixed(4),
      oi_change_pct_1h: +(c.oi_change_pct_1h + (Math.random() - 0.4) * 2).toFixed(1),
    }));

    setResults(varied);
  },
}));
