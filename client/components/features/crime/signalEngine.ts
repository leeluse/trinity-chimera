// Crime Signal Engine — cooldown + detection

import { CoinData, CrimeSignal, SignalType, SignalPriority } from "./crimeData";

// ─── Cooldowns (ms) ──────────────────────────────────────
const COOLDOWNS: Record<SignalType, number> = {
  PRE_IGNITION: 30 * 60 * 1000,
  IGNITION:     20 * 60 * 1000,
  STAGE_UP:     45 * 60 * 1000,
  FUEL_MAX:     60 * 60 * 1000,
  SCORE_SPIKE:  30 * 60 * 1000,
  EXIT_ALERT:   15 * 60 * 1000,
  TRAP_ALERT:   40 * 60 * 1000,
};

const PRIORITY: Record<SignalType, SignalPriority> = {
  PRE_IGNITION: "P0",
  IGNITION:     "P0",
  STAGE_UP:     "P1",
  FUEL_MAX:     "P1",
  SCORE_SPIKE:  "P1",
  EXIT_ALERT:   "P1",
  TRAP_ALERT:   "P2",
};

const LS_KEY = "crime_signal_cooldowns";

function loadCooldowns(): Record<string, number> {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) ?? "{}");
  } catch {
    return {};
  }
}

function saveCooldowns(map: Record<string, number>) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(map));
  } catch {}
}

function cooldownKey(symbol: string, type: SignalType): string {
  return `${symbol}:${type}`;
}

function isOnCooldown(symbol: string, type: SignalType, map: Record<string, number>): boolean {
  const last = map[cooldownKey(symbol, type)];
  if (!last) return false;
  return Date.now() - last < COOLDOWNS[type];
}

function markFired(symbol: string, type: SignalType, map: Record<string, number>): void {
  map[cooldownKey(symbol, type)] = Date.now();
}

// ─── Signal generation ───────────────────────────────────
export function detectSignals(
  current: CoinData[],
  previous: CoinData[] | null,
  exchange: "BYBIT" | "BINANCE" = "BYBIT"
): CrimeSignal[] {
  const signals: CrimeSignal[] = [];
  const now = Date.now();
  const cdMap = loadCooldowns();

  // first scan — no diff signals
  if (!previous) {
    saveCooldowns(cdMap);
    return signals;
  }

  const prevMap = new Map(previous.map((c) => [c.symbol, c]));

  for (const coin of current) {
    const prev = prevMap.get(coin.symbol);

    const fire = (type: SignalType, message: string) => {
      if (isOnCooldown(coin.symbol, type, cdMap)) return;
      markFired(coin.symbol, type, cdMap);
      signals.push({
        id: `${coin.symbol}:${type}:${now}`,
        type,
        priority: PRIORITY[type],
        symbol: coin.symbol,
        exchange,
        message,
        timestamp: now,
        score: coin.score,
        stage: coin.pump_stage,
      });
    };

    // PRE_IGNITION / IGNITION — stage just entered
    if (coin.pump_stage.includes("PRE_IGNITION") && (!prev || !prev.pump_stage.includes("PRE_IGNITION"))) {
      fire("PRE_IGNITION", `PRE_IGNITION 진입  score ${coin.score}  연료 ${coin.squeeze_fuel}`);
    } else if (coin.pump_stage.includes("IGNITION") && (!prev || !prev.pump_stage.includes("IGNITION"))) {
      fire("IGNITION", `IGNITION 감지  score ${coin.score}  연료 ${coin.squeeze_fuel}`);
    }

    // STAGE_UP — any upward stage transition
    if (prev) {
      const stageRank: Record<string, number> = {
        "NEUTRAL": 0, "DISTRIBUTE": 0,
        "ACCUMULATE": 1, "SPRING": 2, "PRE_IGNITION": 3, "IGNITION": 4,
      };
      const rankOf = (s: string) => {
        for (const [k, v] of Object.entries(stageRank)) if (s.includes(k)) return v;
        return 0;
      };
      if (rankOf(coin.pump_stage) > rankOf(prev.pump_stage)) {
        fire("STAGE_UP", `${prev.pump_stage} → ${coin.pump_stage}  score ${coin.score}`);
      }
    }

    // FUEL_MAX — squeeze_fuel crossed 80
    if (coin.squeeze_fuel >= 80 && (!prev || prev.squeeze_fuel < 80)) {
      fire("FUEL_MAX", `스퀴즈 연료 80 돌파  ${prev?.squeeze_fuel ?? "?"}→${coin.squeeze_fuel}`);
    }

    // SCORE_SPIKE — +40 in one scan
    if (prev && coin.score - prev.score >= 40) {
      fire("SCORE_SPIKE", `점수 급등 +${coin.score - prev.score}pt  (${prev.score}→${coin.score})`);
    }

    // EXIT_ALERT — urgency escalated to URGENT or EMERGENCY
    const urgency = coin.exit_alert.urgency;
    if (urgency.includes("URGENT") || urgency.includes("EMERGENCY")) {
      const prevUrgency = prev?.exit_alert.urgency ?? "HOLD";
      if (!prevUrgency.includes("URGENT") && !prevUrgency.includes("EMERGENCY")) {
        fire("EXIT_ALERT", `탈출 경보 ${urgency}  score ${coin.exit_alert.exit_score}`);
      }
    }

    // TRAP_ALERT — trap risk escalated to HIGH or CRITICAL
    const trap = coin.risk.dump_trap_risk;
    if (trap.includes("HIGH") || trap.includes("CRITICAL")) {
      const prevTrap = prev?.risk.dump_trap_risk ?? "LOW";
      if (!prevTrap.includes("HIGH") && !prevTrap.includes("CRITICAL")) {
        fire("TRAP_ALERT", `덤프 트랩 ${trap.split(" ")[0]}  ${coin.pump_stage}`);
      }
    }
  }

  saveCooldowns(cdMap);

  // P0 first, then P1, P2
  return signals.sort((a, b) => a.priority.localeCompare(b.priority));
}

export function clearCooldowns() {
  try { localStorage.removeItem(LS_KEY); } catch {}
}
